"""
Fallback Rules Engine: Offline regex and keyword parser for airplane mode
or immediate fallback when LLM encounters timeouts or connectivity issues.
Supports both Russian and Kazakh languages.
"""

from dataclasses import dataclass, asdict
import re
import time
from typing import Dict, Any, List  # Any: Used for generic JSON serialization dictionary


@dataclass
class ScamSignalExtraction:
    """Structured extraction of anti-fraud and social engineering signals."""
    urgency_score: float  # Normalized score from 0.0 to 1.0 indicating artificial rush
    authority_pressure: bool  # True if mentions police, KNB, prosecutors, or bank security
    safe_account_keyword: bool  # True if mentions safe, reserve, or protected account
    third_party_instruction: bool  # True if acting on incoming phone/chat instructions
    emotional_distress: bool  # True if victim exhibits panic, fear of arrest or asset freeze
    explanation_summary: str  # Human-readable Russian summary for trusted contact
    language: str  # 'ru', 'kz', or 'other'
    source: str = "fallback"  # 'llm' or 'fallback'
    latency_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:  # Any: Primitive values for JSON serialization
        return asdict(self)


# Regular expressions for Russian and Kazakh social engineering patterns
PATTERNS_AUTHORITY: List[str] = [
    r"следовател[ьяеию]",
    r"полицейск",
    r"майор",
    r"капитан",
    r"подполковник",
    r"прокуратур[аеыу]",
    r"кнб",
    r"ұқк",
    r"мвд",
    r"іім",
    r"фсб",
    r"egov",
    r"егов",
    r"госуслуг",
    r"антикоррупцион",
    r"сыбайлас\s+жемқорлық",
    r"техподдержк",
    r"служб[аеыу]?\s+безопасност[иея]",
    r"сотрудник[аеу]?\s+(?:службы\s+безопасности\s+)?банк[аеу]",
    r"служб[аеыу]?\s+финмониторинг[аеу]?",
    r"тергеуші",
    r"қауіпсіздік\s+қызмет",
    r"банк\s+қызметкер",
    r"заң\s+орындары",
    r"қаржы\s+полициясы",
]

# Everyday words that also appear in honest payments (lawyer fee, state duty at the police).
# They signal authority pressure only together with instruction / urgency / fear in the same text.
PATTERNS_AUTHORITY_WEAK: List[str] = [
    r"полици[яиейю]",
    r"адвокат",
    r"заңгер",
    r"әділет",
    r"юстици",
    r"инспектор",
    r"надзор",
]

# Investment / crypto is a scam marker only next to a lure (guaranteed profit, dividends, wallet...).
# A bare "investment account" is a normal banking phrase.
_LURE_RU = (
    r"(?:гарантир\w*|обещ\w*|дивиденд\w*|удво\w*|пассивн\w*\s+доход|доходност\w*"
    r"|быстр\w*\s+(?:прибыл|доход)|прибыл\w*|кошел\w*|закрыт\w*\s+платформ\w*)"
)
_LURE_KZ = r"(?:кепілдік\w*|уәде\w*|қосымша\s+табыс|табыс\w*|пайда\w*|сендір\w*|дивиденд\w*|әмиян\w*)"
_INVEST = r"(?:инвест\w*|крипто\w*|брокер\w*)"
PATTERNS_INVESTMENT_LURE: List[str] = [
    _INVEST + r".{0,80}" + _LURE_RU,
    _LURE_RU + r".{0,80}" + _INVEST,
    _INVEST + r".{0,80}" + _LURE_KZ,
    _LURE_KZ + r".{0,80}" + _INVEST,
]

PATTERNS_SAFE_ACCOUNT: List[str] = [
    r"безопасн[ыйоемуаяг]{1,4}\s+счет[аеу]?",
    r"резервн[ыйоемуаяг]{1,4}\s+счет[аеу]?",
    r"страхов[ыйоемуаяг]{1,4}\s+счет[аеу]?",
    r"специальн[ыйоемуаяг]{1,4}\s+счет[аеу]?",
    r"спецсчет[аеу]?",
    r"транзитн[ыйоемуаяг]{1,4}\s+счет[аеу]?",
    r"временн[ыйоемуаяг]{1,4}\s+депозит",
    r"ячейк[аеуи]",
    r"дроп[- ]?карт",
    r"торгов\w*\s+робот",
    r"қауіпсіз\s+шот",
    r"резервтік\s+шот",
    r"сақтау\s+шоты",
    r"сақтық\s+депозит",
    r"құпия\s+шот",
    r"арнайы\s+шот",
]

PATTERNS_URGENCY: List[str] = [
    r"срочно",
    r"быстрее",
    r"прямо\s+сейчас",
    r"немедленно",
    r"до\s+конца\s+дня",
    r"сегодня\s+же",
    r"в\s+течение\s+часа",
    r"шұғыл",
    r"тез\s+арада",
    r"қазір",
    r"кешіктірмей",
    r"дереу",
]

PATTERNS_THIRD_PARTY: List[str] = [
    r"позвонил[иао]?",
    r"сказал[иао]?",
    r"велел[иао]?",
    r"попросил[иао]?",
    r"дикту[юе]т",
    r"по\s+телефону",
    r"проинструктир",
    r"убедил",
    r"куратор",
    r"айтты",
    r"тапсырды",
    r"аударт",
    r"қоңырау\s+шалды",
    r"сұрады",
    r"нұсқау",
]

PATTERNS_EMOTIONAL: List[str] = [
    r"боюсь",
    r"страшно",
    r"паника",
    r"уголовн[оеыйому]{1,3}\s+дел[оау]",
    r"арест",
    r"конфискаци",
    r"заблокиру[юе]т",
    r"блокировк[аеу]",
    r"взлом",
    r"посадят",
    r"тюрьм[аеу]",
    r"спаса[юет]",
    r"соврать",
    r"драка",
    r"авари[яиейю]",
    r"қорқамын",
    r"қорқынышты",
    r"тұтқындау",
    r"бұғатта",
    r"жалтару",
    r"өтірік",
    r"қама",
    r"қағып\s+кет",
    r"қылмыстық\s+іс",
]

# Specific Kazakh alphabet characters and frequent stop-words
KZ_MARKERS: List[str] = [r"[әіңғүұқөһ]", r"\b(ақша|шот|керек|үшін|болды|мен|сіз|жоқ)\b"]


def _normalize(text: str) -> str:
    """Lowercase and fold 'ё' into 'е' so one regex covers both spellings."""
    return text.lower().replace("ё", "е")


def detect_language(text: str) -> str:
    """Detects if text contains Kazakh markers or falls back to Russian."""
    text_lower = _normalize(text)
    for pattern in KZ_MARKERS:
        if re.search(pattern, text_lower):
            return "kz"
    return "ru"


def match_any(patterns: List[str], text: str) -> bool:
    """Helper checking if any regex pattern matches text."""
    text_lower = _normalize(text)
    for pattern in patterns:
        if re.search(pattern, text_lower):
            return True
    return False


def fallback_parse(text: str) -> ScamSignalExtraction:
    """
    Deterministic fast parsing executed in < 5ms.
    Used during offline mode or whenever LLM fails / times out.
    """
    start_time = time.time()
    lang = detect_language(text)

    has_safe_account = (
        match_any(PATTERNS_SAFE_ACCOUNT, text) or match_any(PATTERNS_INVESTMENT_LURE, text)
    )
    has_urgency = match_any(PATTERNS_URGENCY, text)
    has_third_party = match_any(PATTERNS_THIRD_PARTY, text)
    has_emotional = match_any(PATTERNS_EMOTIONAL, text)
    # Strong titles always count; everyday words count only with pressure in the same text.
    has_authority = match_any(PATTERNS_AUTHORITY, text) or (
        match_any(PATTERNS_AUTHORITY_WEAK, text)
        and (has_third_party or has_urgency or has_emotional)
    )

    # Calculate urgency score
    urgency_points = 0.0
    if has_urgency:
        urgency_points += 0.5
    if has_emotional:
        urgency_points += 0.3
    if has_authority:
        urgency_points += 0.2
    urgency_score = min(1.0, urgency_points)

    # Compose explainable Russian message for the trusted relative
    reasons: List[str] = []
    if has_safe_account:
        reasons.append("упоминание «безопасного/резервного счета»")
    if has_authority:
        reasons.append("упоминание силовых структур или 'службы безопасности'")
    if has_third_party:
        reasons.append("перевод по указанию третьих лиц по телефону")
    if has_urgency:
        reasons.append("признаки искусственной спешки")
    if has_emotional:
        reasons.append("признаки запугивания / психологического давления")

    if reasons:
        explanation = "Обнаружены признаки социальной инженерии: " + "; ".join(reasons) + "."
    else:
        explanation = "Подозрительных ключевых слов и фраз давления не обнаружено."

    elapsed_ms = (time.time() - start_time) * 1000.0

    return ScamSignalExtraction(
        urgency_score=urgency_score,
        authority_pressure=has_authority,
        safe_account_keyword=has_safe_account,
        third_party_instruction=has_third_party,
        emotional_distress=has_emotional,
        explanation_summary=explanation,
        language=lang,
        source="fallback",
        latency_ms=round(elapsed_ms, 2)
    )
