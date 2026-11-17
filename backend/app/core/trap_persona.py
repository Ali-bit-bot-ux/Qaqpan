"""
Бот-ловушка: движок диалога персоны жертвы.

Модуль генерирует ответы бота, который играет роль осторожной пожилой
женщины — потенциальной жертвы телефонного мошенника. Цель бота — вежливо
выяснить реквизиты получателя (IBAN / карта / телефон), которые требует
мошенник, и передать их аналитику. Бот никогда не отправляет деньги и не
раскрывает собственные данные.

Реализация:
1. LLM (Groq REST через urllib) со строгим JSON Schema и таймаутом.
2. Детерминированный офлайн-fallback на шаблонах, когда ключ отсутствует
   или сеть недоступна. Работает с нулевым доступом к интернету.

Секреты читаются из окружения (.env): GROQ_API_KEY, GROQ_MODEL,
LLM_TIMEOUT_SECONDS (не более 1.5 сек).
"""

import json
import logging
import math
import os
import re
import time
import urllib.error
import urllib.request
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Dict, Any, List, Tuple  # Any: JSON payload dictionaries

logger = logging.getLogger("qaqpan.trap_persona")

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MODEL = "openai/gpt-oss-20b"
DEFAULT_TIMEOUT_SECONDS = 1.5
MAX_RESPONSE_BYTES = 64 * 1024
MAX_REPLY_CHARS = 400


@dataclass
class TrapLLMTrace:
    """Shared with a worker thread; only the API can log acceptance after CAS."""
    call_id: str
    source: str = "unknown"


trap_llm_trace: ContextVar[TrapLLMTrace | None] = ContextVar("trap_llm_trace", default=None)


def _record_outcome(operation: str, source: str, started: float) -> None:
    trace = trap_llm_trace.get()
    if trace is not None:
        trace.source = source
    logger.info(
        "Trap worker call_id=%s operation=%s source=%s elapsed_ms=%.0f; not API acceptance",
        trace.call_id if trace is not None else "standalone", operation, source,
        (time.monotonic() - started) * 1000,
    )


def _decode_json(raw: str | bytes) -> Any:  # Any: untrusted JSON, validated by callers
    """Reject nonstandard constants and ambiguous duplicate object fields."""
    def reject_constant(value: str) -> None:
        raise ValueError("Nonstandard JSON constant")

    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:  # Any: JSON values
        result: dict[str, Any] = {}  # Any: JSON values
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate JSON field")
            result[key] = value
        return result

    return json.loads(raw, parse_constant=reject_constant, object_pairs_hook=unique_object)

# Role-play system prompt (Russian, per AGENTS.md documentation language).
SYSTEM_PROMPT_TEMPLATE = """Ты играешь роль пожилой осторожной женщины — потенциальной жертвы
телефонного мошенника — в диалоге с предполагаемым мошенником.
Язык диалога: {language_hint}. Всегда отвечай только на этом языке.

Твоя цель: вежливо, как немного наивная пожилая женщина, выяснить реквизиты,
куда собеседник требует перевести деньги: номер счёта (IBAN), номер карты или
номер телефона для перевода, а также ФИО получателя. Притворяйся, что плохо
слышишь и медленно записываешь, задавай уточняющие вопросы и постепенно
вытягивай реквизиты.

ЖЁСТКИЕ ЗАПРЕТЫ:
1. НИКОГДА не подтверждай перевод и не говори, что отправила деньги.
2. Не выдумывай собственные реальные персональные данные, номера карт, пароли.
3. Не переходи по ссылкам, не устанавливай приложения, не перезванивай на
   указанные собеседником номера.
4. НИКОГДА не сообщай пароли, CVV/CVC, коды из СМС, ПИН-коды.
5. Не раскрывай, что ты бот или система безопасности банка.

Отвечай коротко (до {max_chars} символов), естественно, как пожилая женщина.
Верни ТОЛЬКО валидный JSON по схеме."""

GROQ_RESPONSE_SCHEMA: Dict[str, Any] = {  # Any: standard JSON Schema
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "reply": {
            "type": "string",
            "description": "Ответ пожилой женщины на сообщение собеседника"
        }
    },
    "required": ["reply"]
}

# Offline fallback templates. They rotate so replies do not repeat verbatim.
_FALLBACK_RU: List[str] = [
    "Извините, я не совсем поняла. На какой именно счёт нужно перевести деньги? "
    "Напишите, пожалуйста, номер счёта или карты и ФИО получателя.",
    "Я хочу помочь, но мне нужно точно знать реквизиты. Подскажите, пожалуйста: "
    "номер счёта или карты, куда переводить, и имя получателя.",
    "У меня всё записывается медленно. Напишите ещё раз понятно: на какой счёт "
    "или карту перевести и на чьё имя?",
    "Хорошо, я готова оформить перевод. Напишите реквизиты: номер счёта или карты "
    "и полное имя получателя.",
    "Простите, со связью плохо. Повторите, пожалуйста: какой номер счёта или карты "
    "и кому переводить деньги?",
]

_FALLBACK_KZ: List[str] = [
    "Кешіріңіз, мен толық түсінбедім. Ақшаны нақты қай шотқа аудару керек? "
    "Шот нөмірін немесе карта нөмірін және алушының аты-жөнін жазыңызшы.",
    "Мен көмектескім келеді, бірақ реквизиттерді дәл білуім керек. Аударатын "
    "шот немесе карта нөмірін және алушының аты-жөнін айтыңызшы.",
    "Мен баяу жазып жүрмін. Тағы бір рет түсінікті жазыңыз: ақшаны қай шотқа "
    "немесе картаға аудару керек, кімнің атына?",
    "Жақсы, аударымды рәсімдеуге дайынмын. Реквизиттерді жазыңыз: шот нөмірі "
    "немесе карта нөмірі және алушының толық аты-жөні.",
    "Өтінемін, байланыс нашар естіледі. Қайталап жазыңызшы: қай шот немесе карта "
    "нөмірі және ақшаны кімге аудару керек?",
]


def sanitize_model_name(raw_model: str) -> str:
    """Allow Groq model identifiers, never URL/query fragments."""
    model = raw_model.strip()
    return model if re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9._-]{0,99}(?:/[a-zA-Z0-9][a-zA-Z0-9._-]{0,99})?", model) else DEFAULT_MODEL


def _load_settings() -> Tuple[str, str, float]:
    """Shared trap LLM settings with a finite, capped socket timeout."""
    key = os.getenv("GROQ_API_KEY", "").strip()
    model = sanitize_model_name(os.getenv("GROQ_MODEL", DEFAULT_MODEL))
    try:
        timeout = float(os.getenv("LLM_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS)))
    except ValueError:
        timeout = DEFAULT_TIMEOUT_SECONDS
    if not math.isfinite(timeout) or timeout <= 0:
        timeout = DEFAULT_TIMEOUT_SECONDS
    return key, model, min(timeout, DEFAULT_TIMEOUT_SECONDS)


def _call_groq(history: List[Tuple[str, str]], language: str, api_key: str,
               model: str, timeout: float) -> str:
    """Blocking Groq call with strict JSON Schema; raises on invalid output."""
    language_hint = "казахский" if language == "kz" else "русский"
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        language_hint=language_hint, max_chars=MAX_REPLY_CHARS
    )
    messages = [{"role": "system", "content": system_prompt}]
    for sender, text in history:
        role = "user" if sender == "SCAMMER" else "assistant"
        messages.append({"role": role, "content": text})

    payload: Dict[str, Any] = {  # Any: Groq API request specification
        "model": model,
        "messages": messages,
        "temperature": 0.7,
        "max_completion_tokens": 1024,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "victim_reply", "strict": True, "schema": GROQ_RESPONSE_SCHEMA
            }
        }
    }
    if model in {"openai/gpt-oss-20b", "openai/gpt-oss-120b"}:
        payload.update(reasoning_effort="low", include_reasoning=False)
    req = urllib.request.Request(
        GROQ_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json", "Authorization": f"Bearer {api_key}",
            "User-Agent": "Qaqpan-Trap/1.0",
        },
        method="POST"
    )

    with urllib.request.urlopen(req, timeout=min(timeout, DEFAULT_TIMEOUT_SECONDS)) as response:
        if response.status != 200:
            raise ValueError("Unexpected Groq status")
        body = response.read(MAX_RESPONSE_BYTES + 1)
        if len(body) > MAX_RESPONSE_BYTES:
            raise ValueError("LLM response too large")
        parsed = _decode_json(body)
        choice = parsed["choices"][0]
        if choice["finish_reason"] != "stop" or choice["message"].get("refusal"):
            raise ValueError("Incomplete or refused completion")
        data = _decode_json(choice["message"]["content"])
        if not isinstance(data, dict) or set(data) != {"reply"} or not isinstance(data["reply"], str):
            raise ValueError("Invalid reply shape")
        reply = data["reply"].strip()
        if not reply or len(reply) > MAX_REPLY_CHARS:
            raise ValueError("Invalid reply length")
        return reply


def _fallback_reply(history: List[Tuple[str, str]], language: str) -> str:
    """Deterministic template reply; rotates templates so no verbatim repeats."""
    bot_turns = sum(1 for sender, _ in history if sender == "BOT")
    templates = _FALLBACK_KZ if language == "kz" else _FALLBACK_RU
    return templates[bot_turns % len(templates)]


def generate_victim_reply(history: List[Tuple[str, str]], language: str) -> str:
    """
    Main entrypoint (blocking). Returns the victim persona reply in RU/KZ.

    Uses Groq when GROQ_API_KEY is configured; on timeout, network error
    or invalid JSON instantly falls back to deterministic templates.
    The reply is hard-capped at MAX_REPLY_CHARS characters.
    """
    started = time.monotonic()
    key, model, timeout = _load_settings()
    source = "template_no_key"
    if key and key != "your_groq_api_key_here":
        try:
            reply = _call_groq(history, language, key, model, timeout)
            if time.monotonic() - started > timeout:
                raise TimeoutError("Persona deadline exceeded")
            if not isinstance(reply, str) or not reply.strip() or len(reply) > MAX_REPLY_CHARS:
                raise ValueError("Invalid persona reply")
            _record_outcome("persona", "llm", started)
            return reply.strip()
        except Exception as exc:
            source = "template_timeout" if isinstance(exc, TimeoutError) else "template_error"
            logger.warning(
                "Groq persona failed error=%s http_status=%s; using offline templates",
                type(exc).__name__, exc.code if isinstance(exc, urllib.error.HTTPError) else "none",
            )
    _record_outcome("persona", source, started)
    return _fallback_reply(history, language)[:MAX_REPLY_CHARS]
