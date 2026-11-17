"""
Извлечение реквизитов получателя из сообщений мошенника.

Из каждого сообщения извлекаются реквизиты, на которые мошенник просит
перевести деньги: IBAN (Казахстан), номер банковской карты (с Luhn-проверкой)
или номер телефона для перевода. Сохраняется исходная цитата из сообщения.

Реализация:
1. LLM (Groq REST через urllib) со строгим JSON Schema {recipients: [...]}.
2. Детерминированный regex-fallback: работает офлайн, с нулевым доступом
   к сети.

Сообщения с явными признаками запроса секретов (пароль, CVV, код из СМС)
не обрабатываются экстрактором. Исходный диалог сохраняется API: использовать
только синтетические данные, не отправлять реальные секреты.
IBAN проверяется только по формату (20 символов), не по контрольной сумме,
существованию счёта или владельцу. Извлечение не доказывает мошенничество.

Секреты читаются из окружения (.env): GROQ_API_KEY, GROQ_MODEL,
LLM_TIMEOUT_SECONDS (не более 1.5 сек).
"""

import json
import logging
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List  # Any: JSON payload dictionaries

from .trap_persona import (
    _load_settings, _decode_json, _record_outcome,
    GROQ_URL, MAX_RESPONSE_BYTES, DEFAULT_TIMEOUT_SECONDS,
)

# Reuse the simple Kazakh-marker language detection from fallback_rules.
try:
    from .fallback_rules import detect_language
except ImportError:  # pragma: no cover - standalone run support
    from fallback_rules import detect_language  # type: ignore[no-redef]

logger = logging.getLogger("qaqpan.recipient_extractor")

QUOTE_MAX_CHARS = 300


class RecipientType(str, Enum):
    IBAN = "IBAN"
    CARD = "CARD"
    PHONE = "PHONE"


@dataclass(frozen=True)
class ExtractedRecipient:
    """Pydantic-friendly plain recipient record used by the API layer."""
    recipient_type: RecipientType
    value: str        # normalized value (spaces stripped)
    quote: str        # original substring from the scammer message


# --- Regex patterns (deterministic offline fallback) ---

# KZ IBAN: exactly 20 characters (country, check digits, bank, account).
# Syntax only: neither the IBAN checksum nor bank/account ownership is verified.
IBAN_RE = re.compile(
    r"(?<![A-Z0-9])KZ(?:[ \t]*[0-9]){5}(?:[ \t]*[A-Z0-9]){13}"
    r"(?![A-Z0-9]|[ \t]+[0-9])", re.IGNORECASE | re.ASCII
)

# Card candidates: 13-19 ASCII digits; do not take prefixes of longer numbers.
CARD_RE = re.compile(r"(?<!\w)[0-9](?:[ -]?[0-9]){12,18}(?!\w|[ -]?[0-9])")

# Phone syntax is shared by offline and LLM validation; parentheses must balance.
PHONE_RE = re.compile(
    r"(?<![\w+])(?:\+?7|8)[ \t-]*(?:\([0-9]{3}\)|[0-9]{3})"
    r"[ \t-]*[0-9]{3}[ \t-]*[0-9]{2}[ \t-]*[0-9]{2}(?!\w|[ \t-]*[0-9])"
)

# Explicit secret-request markers: never extract anything from such messages.
SENSITIVE_MARKERS = [
    "пароль", "cvv", "cvc", "cvn", "пин-код", "пин код",
    "код из смс", "смс-код", "смс код", "смскод",
    "код подтверждения", "одноразов", "код безопасности",
    "құпия сөз", "паролы",
]

SYSTEM_PROMPT = """Ты — модуль безопасности банка 'Қақпан'. Тебе передаётся сообщение
предполагаемого мошенника из диалога с жертвой. Извлеки реквизиты получателя денег,
которые мошенник требует указать для перевода: банковский счёт/IBAN, номер банковской
карты или номер телефона для перевода.

Правила:
1. Извлекай ТОЛЬКО реально присутствующие в тексте реквизиты. Ничего не выдумывай.
2. НИКОГДА не извлекай пароли, CVV/CVC, ПИН-коды, коды из СМС, коды подтверждения.
   Если сообщение просит такие секреты — верни пустой список recipients.
3. value — реквизит без пробелов и лишних символов; quote — точная исходная
   цитата из сообщения.
4. Типы: IBAN (счёт, начинается на KZ), CARD (номер карты), PHONE (телефон +7/8).

Верни ТОЛЬКО валидный JSON в строгом соответствии со схемой."""

GROQ_RESPONSE_SCHEMA: Dict[str, Any] = {  # Any: standard JSON Schema
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "recipients": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "type": {"type": "string", "enum": ["IBAN", "CARD", "PHONE"]},
                    "value": {"type": "string"},
                    "quote": {"type": "string"}
                },
                "required": ["type", "value", "quote"]
            }
        }
    },
    "required": ["recipients"]
}


def _contains_sensitive_request(text: str) -> bool:
    """True when the message asks for secrets (passwords, CVV, SMS codes)."""
    lowered = text.lower()
    return any(marker in lowered for marker in SENSITIVE_MARKERS)


def _luhn_ok(digits: str) -> bool:
    """Standard Luhn checksum validation for card number candidates."""
    total = 0
    for index, char in enumerate(reversed(digits)):
        digit = int(char)
        if index % 2 == 1:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return total % 10 == 0


def _candidate_spans(text: str) -> list[tuple[int, int, ExtractedRecipient]]:
    """Keep spans so substrings of IBANs/cards cannot become other recipients."""
    found: list[tuple[int, int, ExtractedRecipient]] = []
    for rtype, pattern in (
        (RecipientType.IBAN, IBAN_RE),
        (RecipientType.CARD, CARD_RE),
        (RecipientType.PHONE, PHONE_RE),
    ):
        for match in pattern.finditer(text):
            if any(match.start() < end and start < match.end() for start, end, _ in found):
                continue
            quote = match.group(0)
            if len(quote) > QUOTE_MAX_CHARS:
                continue
            value = re.sub(r"[ \t]", "", quote).upper() if rtype == RecipientType.IBAN else re.sub(r"\D", "", quote)
            if rtype == RecipientType.PHONE and len(value) == 11 and value.startswith("8"):
                value = "7" + value[1:]
            if rtype == RecipientType.CARD and (len(set(value)) == 1 or not _luhn_ok(value)):
                continue
            found.append((match.start(), match.end(), ExtractedRecipient(rtype, value, quote)))
    return found


def _extract_regex(text: str) -> List[ExtractedRecipient]:
    """Deterministic syntax candidates, not bank-verified payment recipients."""
    found: List[ExtractedRecipient] = []
    seen: set[tuple[RecipientType, str]] = set()
    for _, _, item in _candidate_spans(text):
        key = (item.recipient_type, item.value)
        if key not in seen:
            seen.add(key)
            found.append(item)
    return found


def _validate_llm_recipients(data: object, text: str) -> List[ExtractedRecipient]:
    """Treat model output as untrusted: validate shape, value, and original spans."""
    if not isinstance(data, dict) or set(data) != {"recipients"} or not isinstance(data["recipients"], list):
        raise ValueError("Invalid recipient response shape")
    if len(data["recipients"]) > 100:
        raise ValueError("Too many recipients")
    candidates = _candidate_spans(text)
    found: List[ExtractedRecipient] = []
    seen: set[tuple[RecipientType, str]] = set()
    for item in data["recipients"]:
        if not isinstance(item, dict) or set(item) != {"type", "value", "quote"}:
            raise ValueError("Invalid recipient item shape")
        if not all(isinstance(item[field], str) for field in ("type", "value", "quote")):
            raise ValueError("Recipient fields must be strings")
        rtype = RecipientType(item["type"])
        value, quote = item["value"], item["quote"]
        if not quote or len(quote) > QUOTE_MAX_CHARS or len(value) > 20:
            continue
        # The supplied quote must contain this exact candidate at an occurrence
        # in the original input, not just somewhere in a different quote.
        offset = text.find(quote)
        grounded = False
        while offset != -1:
            if any(offset <= start and end <= offset + len(quote)
                   and candidate.recipient_type == rtype and candidate.value == value
                   for start, end, candidate in candidates):
                grounded = True
                break
            offset = text.find(quote, offset + 1)
        key = (rtype, value)
        if grounded and key not in seen:
            seen.add(key)
            found.append(ExtractedRecipient(rtype, value, quote))
    return found


def _call_groq(text: str, api_key: str, model: str, timeout: float) -> List[ExtractedRecipient]:
    """Blocking Groq call; local validation still rejects invented recipients."""
    lang_hint = "казахском" if detect_language(text) == "kz" else "русском"
    payload: Dict[str, Any] = {  # Any: Groq API request specification
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Сообщение мошенника ({lang_hint} язык): \"{text}\""},
        ],
        "temperature": 0.0,
        "max_completion_tokens": 2048,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "payment_recipients", "strict": True, "schema": GROQ_RESPONSE_SCHEMA
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

    return _validate_llm_recipients(data, text)


def extract_recipients_offline(text: str) -> List[ExtractedRecipient]:
    """Local fallback with the same sensitive-request exclusion as the LLM path."""
    return [] if _contains_sensitive_request(text) else _extract_regex(text)


def extract_recipients(text: str) -> List[ExtractedRecipient]:
    """
    Main entrypoint (blocking). Extracts payment recipients from a scammer
    message. Uses Groq when configured; on timeout/network failure/invalid
    JSON instantly falls back to deterministic regex extraction. Messages
    requesting secrets yield an empty list. Never invents missing values.
    """
    started = time.monotonic()
    if _contains_sensitive_request(text):
        _record_outcome("extraction", "skipped_sensitive", started)
        return []

    key, model, timeout = _load_settings()
    source = "regex_no_key"
    if key and key != "your_groq_api_key_here":
        try:
            recipients = _call_groq(text, key, model, timeout)
            if time.monotonic() - started > timeout:
                raise TimeoutError("Extraction deadline exceeded")
            if recipients:
                _record_outcome("extraction", "llm", started)
                return recipients
            source = "regex_empty_llm"
        except Exception as exc:
            source = "regex_timeout" if isinstance(exc, TimeoutError) else "regex_error"
            logger.warning(
                "Groq extraction failed error=%s http_status=%s; using regex fallback",
                type(exc).__name__, exc.code if isinstance(exc, urllib.error.HTTPError) else "none",
            )
    recipients = _extract_regex(text)
    _record_outcome("extraction", source, started)
    return recipients
