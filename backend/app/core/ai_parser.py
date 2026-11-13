"""
AI Parser: Extraction of social engineering and anti-fraud signals
from client transaction explanation text (RU / KZ) using Google Gemini LLM.

Guarantees:
1. Strict JSON Schema output (Structured Outputs).
2. Strict timeout handling (<= 1.5 seconds per AGENTS.md).
3. Instant deterministic fallback on regex parser during offline or failure.
"""

import json
import logging
import os
import sys
import time
import urllib.error
import urllib.request
from typing import Dict, Any, Optional  # Any: Used for JSON serialized dictionaries

# Ensure imports work both standalone and when imported as a package
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "../../../"))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

try:
    from backend.app.core.fallback_rules import (
        ScamSignalExtraction,
        fallback_parse
    )
except ImportError:
    from fallback_rules import (
        ScamSignalExtraction,
        fallback_parse
    )

logger = logging.getLogger("qaqpan.ai_parser")
logging.basicConfig(level=logging.INFO)


def load_env_file(filepath: str = ".env") -> None:
    """Manual .env parser without requiring python-dotenv."""
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip().strip("\"'")
                    if key not in os.environ:
                        os.environ[key] = val


load_env_file()

# Standard prompt in Russian as required by AGENTS.md
SYSTEM_PROMPT = """Ты — специализированный модуль безопасности банка 'Қақпан' (Qaqpan Anti-Fraud).
Твоя задача — анализировать ответ клиента на вопрос 'Для чего вы переводите эти деньги?' и извлекать признаки социальной инженерии.
Клиент может отвечать на русском или казахском языке.

Признаки мошенничества:
1. authority_pressure: упоминание силовиков (следователь, полиция, КНБ, ҰҚК, МВД, прокуратура) или сотрудников безопасности банка/финмониторинга.
2. safe_account_keyword: упоминание 'безопасного счета', 'резервной ячейки', 'страхового счета', 'қауіпсіз шот'.
3. third_party_instruction: клиент переводит по указанию кого-то по телефону/мессенджеру (велели, сказали, диктуют).
4. emotional_distress: страх уголовного дела, ареста, паника, спешка.
5. urgency_score: степень навязанной спешки от 0.0 (спокойно) до 1.0 (срочно, прямо сейчас, иначе беда).
6. explanation_summary: краткое (1-2 предложения) понятное объяснение рисков на русском языке для родственника/дочери.

Верни ТОЛЬКО валидный JSON в строгом соответствии со схемой."""

GEMINI_RESPONSE_SCHEMA: Dict[str, Any] = {  # Any: JSON Schema specification object
    "type": "OBJECT",
    "properties": {
        "urgency_score": {
            "type": "NUMBER",
            "description": "Степень искусственной спешки от 0.0 до 1.0"
        },
        "authority_pressure": {
            "type": "BOOLEAN",
            "description": "Упоминание полиции, следователей, КНБ или службы безопасности"
        },
        "safe_account_keyword": {
            "type": "BOOLEAN",
            "description": "Упоминание безопасного, резервного или страхового счета"
        },
        "third_party_instruction": {
            "type": "BOOLEAN",
            "description": "Перевод выполняется по телефонному указанию посторонних лиц"
        },
        "emotional_distress": {
            "type": "BOOLEAN",
            "description": "Признаки страха, давления или паники в тексте"
        },
        "explanation_summary": {
            "type": "STRING",
            "description": "Краткое объяснение рисков на русском языке"
        },
        "language": {
            "type": "STRING",
            "enum": ["ru", "kz", "other"]
        }
    },
    "required": [
        "urgency_score",
        "authority_pressure",
        "safe_account_keyword",
        "third_party_instruction",
        "emotional_distress",
        "explanation_summary",
        "language"
    ]
}


def sanitize_model_name(raw_model: str) -> str:
    """Ensures a valid Google Gemini model identifier is passed."""
    valid_prefixes = ("gemini-", "models/gemini-")
    if not any(raw_model.startswith(p) for p in valid_prefixes) or "3.5" in raw_model:
        # Fallback to recommended fast production model if unknown model name is configured
        return "gemini-1.5-flash"
    return raw_model


def call_gemini_api(
    text: str,
    api_key: str,
    model: str = "gemini-1.5-flash",
    timeout: float = 1.5
) -> Dict[str, Any]:  # Any: Parsed JSON response payload
    """Direct REST call to Gemini API with strict timeout and JSON Schema."""
    safe_model = sanitize_model_name(model)
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{safe_model}:generateContent?key={api_key}"

    payload: Dict[str, Any] = {  # Any: Gemini API request specification
        "system_instruction": {
            "parts": [{"text": SYSTEM_PROMPT}]
        },
        "contents": [
            {
                "role": "user",
                "parts": [{"text": f"Ответ клиента: \"{text}\""}]
            }
        ],
        "generationConfig": {
            "temperature": 0.0,
            "response_mime_type": "application/json",
            "response_schema": GEMINI_RESPONSE_SCHEMA
        }
    }

    req_data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=req_data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    with urllib.request.urlopen(req, timeout=timeout) as response:
        if response.status != 200:
            raise ValueError(f"Gemini API returned status {response.status}")
        body = response.read().decode("utf-8")
        parsed = json.loads(body)
        raw_text = parsed["candidates"][0]["content"]["parts"][0]["text"]
        return json.loads(raw_text)


def parse_client_answer(text: str) -> ScamSignalExtraction:
    """
    Main entrypoint: parses client explanation text.
    If GEMINI_API_KEY is available and network succeeds within timeout, uses LLM.
    If timeout > 1.5s, offline, or network error occurs, seamlessly falls back to regex rules.
    """
    key = os.getenv("GEMINI_API_KEY", "").strip()
    raw_model = os.getenv("LLM_MODEL", "gemini-1.5-flash")
    model = sanitize_model_name(raw_model)
    timeout = float(os.getenv("LLM_TIMEOUT_SECONDS", "1.5"))

    if not key or key == "your_gemini_api_key_here":
        logger.warning("GEMINI_API_KEY is not configured. Using offline fallback.")
        return fallback_parse(text)

    start_time = time.time()
    try:
        data = call_gemini_api(text, api_key=key, model=model, timeout=timeout)
        elapsed_ms = (time.time() - start_time) * 1000.0

        return ScamSignalExtraction(
            urgency_score=float(data.get("urgency_score", 0.0)),
            authority_pressure=bool(data.get("authority_pressure", False)),
            safe_account_keyword=bool(data.get("safe_account_keyword", False)),
            third_party_instruction=bool(data.get("third_party_instruction", False)),
            emotional_distress=bool(data.get("emotional_distress", False)),
            explanation_summary=str(data.get("explanation_summary", "")),
            language=str(data.get("language", "ru")),
            source="llm",
            latency_ms=round(elapsed_ms, 2)
        )
    except Exception as exc:
        logger.warning("LLM exception/timeout (%s). Immediate switch to fallback.", exc)
        res = fallback_parse(text)
        res.latency_ms = round((time.time() - start_time) * 1000.0, 2)
        return res


if __name__ == "__main__":
    test_phrases = [
        "Мне звонил следователь майор полиции, сказал срочно перевести деньги на безопасный счет!",
        "Маған полициядан қоңырау шалды, шұғыл қауіпсіз шотқа ақша аудару керек дейді.",
        "Это внуку на день рождения на подарок, обещал отправить сегодня.",
        "Племяннице на учебу в университет за второй семестр.",
        "Сотрудник службы безопасности банка велел перевести, иначе все счета заблокируют!"
    ]

    print("=== TESTING AI PARSER (RU / KZ) ===")
    for phrase in test_phrases:
        result = parse_client_answer(phrase)
        print(f"\n[Phrase]: {phrase}")
        print(f"Source: {result.source} | Latency: {result.latency_ms} ms | Language: {result.language}")
        print(f"Signals: authority={result.authority_pressure}, safe_acc={result.safe_account_keyword}, urgency={result.urgency_score}")
        print(f"Summary: {result.explanation_summary}")
