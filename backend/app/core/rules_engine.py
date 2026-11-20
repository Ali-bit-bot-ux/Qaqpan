"""
Rules Engine: Transparent, threshold-based anti-fraud scoring.
Complies with AGENTS.md:
- No LLM 'black box' decision making.
- Explicit explainable rules with defined thresholds.
- Evaluates transactional signals + text extraction features from ai_parser.
"""

from dataclasses import dataclass, field, asdict
from enum import Enum
import os
import sys
import time
from typing import List, Dict, Any, Optional  # Any: Used for JSON serialization dictionaries

# Ensure relative imports resolve whether run as script or module
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "../../../"))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

try:
    from backend.app.core.fallback_rules import ScamSignalExtraction, mentions_family
    from backend.app.core.ai_parser import parse_client_answer
except ImportError:
    from fallback_rules import ScamSignalExtraction, mentions_family
    from ai_parser import parse_client_answer


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class NextAction(str, Enum):
    ALLOW = "ALLOW"
    ASK_QUESTION = "ASK_QUESTION"
    REQUIRE_TRUSTED_APPROVAL = "REQUIRE_TRUSTED_APPROVAL"


@dataclass
class TransactionContext:
    """Contextual metadata describing an outgoing transfer."""
    amount: float  # In KZT (tenge)
    is_new_recipient: bool  # True if recipient is not in client's address book
    transfer_hour: int  # 0 to 23
    frequency_last_hour: int = 1  # Number of outgoing transfers in the past hour
    client_typical_amount: float = 50000.0  # Client's historical typical transfer limit
    recipient_account: str = ""
    client_id: str = "client_default"


@dataclass
class TrustedAlertCard:
    """Human-friendly explainable security card for the trusted relative (e.g. daughter)."""
    title: str  # Short alarming headline (e.g. 'Высокий риск мошенничества')
    danger_summary: str  # Plain language explanation of what is happening
    evidence_bullets: List[str]  # 2-4 factual reasons why this was flagged
    recommended_action: str  # Actionable advice for the daughter
    language: str  # 'ru' or 'kz'

    def to_dict(self) -> Dict[str, Any]:  # Any: Primitives mapping
        return asdict(self)


@dataclass
class ScoringResult:
    """Comprehensive, explainable scoring outcome."""
    risk_score: float  # 0.0 to 100.0
    risk_level: RiskLevel
    action: NextAction
    triggered_rules: List[str] = field(default_factory=list)
    explanation: str = ""
    signals: Optional[ScamSignalExtraction] = None
    trusted_alert: Optional[TrustedAlertCard] = None

    def to_dict(self) -> Dict[str, Any]:  # Any: JSON-serializable dictionary
        data: Dict[str, Any] = asdict(self)  # Any: Primitives mapping
        data["risk_level"] = self.risk_level.value
        data["action"] = self.action.value
        return data


class RulesEngine:
    """
    Transparent scoring ladder:
    - Pre-answer evaluation: Initial risk based purely on transaction anomalies.
    - Post-answer evaluation: Combines transaction anomalies with AI extracted markers.
    """

    # Scoring weights and thresholds
    THRESHOLD_MEDIUM: float = 30.0
    THRESHOLD_HIGH: float = 70.0
    # Amount below this share of the client's typical transfer is a "micro-transfer".
    MICRO_TRANSFER_RATIO: float = 0.1

    @classmethod
    def evaluate_initial_transaction(cls, ctx: TransactionContext) -> ScoringResult:
        """
        Step 1: Initial scoring before any prompt is shown to client.
        Determines whether transfer completes instantly (LOW) or needs question (MEDIUM/HIGH).
        """
        score = 0.0
        rules: List[str] = []

        # 1. Unusual amount relative to typical spending
        ratio = ctx.amount / max(ctx.client_typical_amount, 1000.0)
        if ratio >= 10.0:
            score += 35.0
            rules.append(f"Сумма перевода превышает типичную в {ratio:.1f} раз")
        elif ratio >= 4.0:
            score += 20.0
            rules.append(f"Сумма перевода выше привычной в {ratio:.1f} раз")

        # 2. Absolute large amount threshold (> 500 000 KZT)
        if ctx.amount >= 500000.0:
            score += 20.0
            rules.append("Крупный перевод свыше 500 000 ₸")

        # Micro-transfers carry almost no exposure: a new recipient or the hour alone must not
        # trigger a question. Burst frequency below still counts, so splitting a theft into
        # tiny pieces cannot hide it.
        micro = ratio < cls.MICRO_TRANSFER_RATIO

        # 3. New recipient anomaly
        if ctx.is_new_recipient and not micro:
            score += 20.0
            rules.append("Перевод новому, неизвестному ранее получателю")

        # 4. Night transaction anomaly (23:00 - 06:00)
        if (ctx.transfer_hour >= 23 or ctx.transfer_hour <= 6) and not micro:
            score += 15.0
            rules.append("Нетипичное ночное время проведения операции")

        # 5. Smurfing / Rapid transfers anomaly
        if ctx.frequency_last_hour >= 3:
            score += 30.0
            rules.append(f"Признаки дробления сумм: {ctx.frequency_last_hour} переводов за последний час")
        elif ctx.frequency_last_hour >= 2:
            score += 15.0
            rules.append("Повторный перевод в течение одного часа")

        # Clamp score to [0, 100]
        score = min(100.0, max(0.0, score))

        # Map to Risk Level & Action
        if score >= cls.THRESHOLD_HIGH:
            level = RiskLevel.HIGH
            action = NextAction.REQUIRE_TRUSTED_APPROVAL
            summary = "Операция имеет критический риск: " + "; ".join(rules)
        elif score >= cls.THRESHOLD_MEDIUM:
            level = RiskLevel.MEDIUM
            action = NextAction.ASK_QUESTION
            summary = "Операция имеет повышенный риск, требуется уточнение цели: " + "; ".join(rules)
        else:
            level = RiskLevel.LOW
            action = NextAction.ALLOW
            summary = "Операция в пределах нормы. Дополнительная проверка не требуется."

        return ScoringResult(
            risk_score=round(score, 1),
            risk_level=level,
            action=action,
            triggered_rules=rules,
            explanation=summary,
            signals=None
        )

    @classmethod
    def generate_trusted_alert(
        cls,
        ctx: TransactionContext,
        score: float,
        rules: List[str],
        signals: Optional[ScamSignalExtraction] = None,
        lang: str = "ru"
    ) -> TrustedAlertCard:
        """
        Generates empathetic, human-readable safety cards for the trusted relative.
        Supports both Russian and Kazakh languages.
        """
        is_kz = (lang == "kz") or (signals and signals.language == "kz")
        bullets: List[str] = []

        # Analyze signals for plain bullets
        if signals:
            if signals.safe_account_keyword:
                bullets.append(
                    "'Қауіпсіз/резервтік шотқа' ақша аудару туралы айтылған (алаяқтардың негізгі тәсілі)"
                    if is_kz else
                    "Упомянут перевод на 'безопасный/резервный счет' (классическая схема мошенников)"
                )
            if signals.authority_pressure:
                bullets.append(
                    "Полиция, ҰҚК немесе қауіпсіздік қызметі атынан қоңырау шалып қысым көрсеткен"
                    if is_kz else
                    "В разговоре упоминались звонки 'следователей полиции' или 'службы безопасности'"
                )
            if signals.third_party_instruction:
                bullets.append(
                    "Аударым белгісіз біреулердің телефонмен берген нұсқауы бойынша жасалып жатыр"
                    if is_kz else
                    "Перевод совершается по прямым инструкциям неизвестных лиц по телефону"
                )
            if signals.payment_lure:
                bullets.append(
                    "Жақыныңыздан бейтаныс адамға алдын ала төлем, салық немесе кепіл ақша сұралған"
                    if is_kz else
                    "Просят заранее заплатить незнакомцу: пошлину, налог, залог или взнос (типичная схема обмана)"
                )
            if signals.urgency_score >= 0.6:
                bullets.append(
                    "Жақыныңызды асықтырып, шешім қабылдауға уақыт бермеген"
                    if is_kz else
                    "На клиента оказывается давление со срочностью (требуют отправить немедленно)"
                )

        # Financial contextual bullets
        ratio = ctx.amount / max(ctx.client_typical_amount, 1000.0)
        if ratio >= 4.0:
            bullets.append(
                f"Сомасы жақыныңыздың әдеттегі аударымдарынан {ratio:.1f} есе көп"
                if is_kz else
                f"Сумма перевода ({ctx.amount:,.0f} ₸) в {ratio:.1f} раз превышает обычные траты"
            )

        if ctx.is_new_recipient:
            bullets.append(
                "Ақша бұрын-соңды аударым жасалмаған бейтаныс адамның шотына жіберілуде"
                if is_kz else
                "Получатель перевода — абсолютно новый человек, переводов которому ранее не было"
            )

        if ctx.transfer_hour >= 23 or ctx.transfer_hour <= 6:
            bullets.append(
                f"Аударым түн мезгілінде жасалуда ({ctx.transfer_hour:02d}:00)"
                if is_kz else
                f"Операция проводится в нетипичное ночное время ({ctx.transfer_hour:02d}:00)"
            )

        # Fallback bullets if specific flags are scarce
        if not bullets:
            bullets = [
                "Транзакция параметрлері қалыпты жағдайдан айтарлықтай ауытқыған"
                if is_kz else
                "Параметры операции существенно отклоняются от привычного профиля клиента"
            ]

        # Titles and actionable advice
        if is_kz:
            title = "⚠️ Назар аударыңыз: Алаяқтық қаупі жоғары"
            summary = (
                f"Сіздің жақыныңыз {ctx.amount:,.0f} ₸ сомасындағы күмәнді аударымды жасауға "
                "әрекеттеніп жатыр. Әлеуметтік инженерия және телефон алаяқтарының белгілері анықталды."
            )
            recommendation = (
                "Шұғыл түрде жақыныңызға телефон соғып, жағдайды анықтаңыз және АУДАРЫМДЫ ТОҚТАТУДЫ сұраңыз. "
                "Есіңізде болсын: банк немесе құқық қорғау органдары ешқашан 'қауіпсіз шотқа' ақша аударуды сұрамайды!"
            )
            card_lang = "kz"
        else:
            title = "⚠️ Внимание: Высокий риск телефонного мошенничества"
            summary = (
                f"Ваш близкий человек пытается совершить подозрительный перевод на сумму {ctx.amount:,.0f} ₸. "
                "Система обнаружила явные признаки психологического давления и социальной инженерии."
            )
            recommendation = (
                "Срочно позвоните близкому по телефону, успокойте его и попросите НИЧЕГО НЕ ПЕРЕВОДИТЬ. "
                "Помните: настоящие сотрудники банков и полиции никогда не просят переводить деньги на другие счета!"
            )
            card_lang = "ru"

        return TrustedAlertCard(
            title=title,
            danger_summary=summary,
            evidence_bullets=bullets[:4],  # Top 4 most relevant facts
            recommended_action=recommendation,
            language=card_lang
        )

    @classmethod
    def evaluate_with_answer(
        cls,
        ctx: TransactionContext,
        answer_text: str,
        signals: Optional[ScamSignalExtraction] = None
    ) -> ScoringResult:
        """
        Step 2: Scoring after client provided answer to 'Для чего перевод?'.
        Integrates AI extracted markers with base transaction risk.
        """
        # Start from base transaction anomalies
        initial = cls.evaluate_initial_transaction(ctx)
        score = initial.risk_score
        rules = list(initial.triggered_rules)

        # Parse answer if signals not pre-computed
        if signals is None:
            signals = parse_client_answer(answer_text)

        # 1. Critical Hard Rule: 'Safe account' keyword mentioned
        if signals.safe_account_keyword:
            score += 55.0
            rules.append("Критический маркер: клиент упомянул 'безопасный / резервный счет'")

        # 2. Authority pressure (police, security, prosecutors, KNB)
        if signals.authority_pressure:
            score += 35.0
            rules.append("В ответе обнаружено давление силовиков или службы безопасности")

        # 3. Third-party instructions over phone / messenger. A plain request from a close
        # relative ("Мама попросила") is not a stranger's instruction unless something else
        # in the text looks like a scam.
        other_scam_signal = (
            signals.safe_account_keyword or signals.authority_pressure or signals.payment_lure
            or signals.emotional_distress or signals.urgency_score >= 0.5
        )
        third_party = signals.third_party_instruction and not (
            mentions_family(answer_text) and not other_scam_signal
        )
        if third_party:
            score += 25.0
            rules.append("Клиент действует по указанию неизвестных лиц по телефону")

        # 3b. Advance-fee scheme: fee / tax / deposit / prepayment demanded by a stranger
        if signals.payment_lure:
            score += 35.0
            rules.append("Признаки схемы предоплаты или сбора (пошлина, налог, залог, взнос незнакомцу)")

        # 4. Psychological distress / fear
        if signals.emotional_distress:
            score += 20.0
            rules.append("Обнаружены признаки запугивания или страха перед арестом/блокировкой")

        # 5. Urgency factor
        if signals.urgency_score >= 0.7:
            score += 20.0
            rules.append(f"Искусственная спешка (индекс срочности: {signals.urgency_score:.1f})")

        # 6. Legitimate Benign Relief:
        # If no scam signals detected at all, relieve suspicion
        has_any_scam_signal = (
            signals.safe_account_keyword or
            signals.authority_pressure or
            third_party or
            signals.emotional_distress or
            signals.payment_lure or
            signals.urgency_score >= 0.5
        )
        if not has_any_scam_signal and len(answer_text.strip()) > 3:
            score = max(0.0, score - 35.0)
            rules.append("Ответ клиента обоснован, маркеры социальной инженерии отсутствуют")

        # Final clamp
        score = min(100.0, max(0.0, score))

        # Explicit Threshold Logic
        if score >= cls.THRESHOLD_HIGH or signals.safe_account_keyword:
            level = RiskLevel.HIGH
            action = NextAction.REQUIRE_TRUSTED_APPROVAL
            summary = (
                f"КРИТИЧЕСКИЙ РИСК ({score:.0f}/100). Требуется подтверждение близкого: "
                + (signals.explanation_summary if signals.explanation_summary else "; ".join(rules))
            )
        elif score >= cls.THRESHOLD_MEDIUM:
            # The question was already asked and the answer did not clear suspicion.
            # Asking again would let a coached client retry until the story sounds clean,
            # so the ladder moves on to the trusted person.
            level = RiskLevel.HIGH
            action = NextAction.REQUIRE_TRUSTED_APPROVAL
            rules.append("Ответ не снял подозрений: повторный вопрос не задаётся, нужен близкий")
            summary = (
                f"Повышенный риск ({score:.0f}/100), ответ не снял подозрений. "
                "Требуется подтверждение близкого: " + "; ".join(rules)
            )
        else:
            level = RiskLevel.LOW
            action = NextAction.ALLOW
            summary = "Перевод подтвержден и безопасен. Признаков мошенничества не обнаружено."

        alert_card: Optional[TrustedAlertCard] = None
        if level == RiskLevel.HIGH:
            card_lang = signals.language if signals else "ru"
            alert_card = cls.generate_trusted_alert(
                ctx=ctx,
                score=score,
                rules=rules,
                signals=signals,
                lang=card_lang
            )

        return ScoringResult(
            risk_score=round(score, 1),
            risk_level=level,
            action=action,
            triggered_rules=rules,
            explanation=summary,
            signals=signals,
            trusted_alert=alert_card
        )


if __name__ == "__main__":
    print("=== TESTING RULES ENGINE (10 SCENARIOS) ===")

    test_cases = [
        # 1. Normal transfer to known person -> LOW
        (
            TransactionContext(amount=15000, is_new_recipient=False, transfer_hour=14),
            "Внуку на обеды в школе",
            RiskLevel.LOW
        ),
        # 2. Moderate transfer to new recipient -> MEDIUM initial -> LOW after legit answer
        (
            TransactionContext(amount=45000, is_new_recipient=True, transfer_hour=15),
            "Покупка детской коляски на OLX, забираю сам",
            RiskLevel.LOW
        ),
        # 3. Safe account scam -> HIGH
        (
            TransactionContext(amount=450000, is_new_recipient=True, transfer_hour=16),
            "Следователь майор полиции сказал перевести деньги на безопасный счет срочно",
            RiskLevel.HIGH
        ),
        # 4. Kazakh police scam -> HIGH
        (
            TransactionContext(amount=500000, is_new_recipient=True, transfer_hour=17),
            "Маған полициядан қоңырау шалды, шұғыл қауіпсіз шотқа ақша аудару керек дейді",
            RiskLevel.HIGH
        ),
        # 5. Night transfer + high amount + new recipient -> Initial HIGH
        (
            TransactionContext(amount=600000, is_new_recipient=True, transfer_hour=2),
            "Срочно перевожу на резервный счет",
            RiskLevel.HIGH
        ),
        # 6. Smurfing evasion attempt (multiple transfers under 100k) + scam answer -> HIGH
        (
            TransactionContext(amount=95000, is_new_recipient=True, transfer_hour=18, frequency_last_hour=4),
            "Майор просил отправлять частями до 100 тысяч чтобы банк не заметил",
            RiskLevel.HIGH
        ),
        # 7. Rent payment to known recipient -> LOW
        (
            TransactionContext(amount=180000, is_new_recipient=False, transfer_hour=12),
            "Оплата аренды квартиры за ноябрь хозяйке",
            RiskLevel.LOW
        ),
        # 8. Kazakh benign gift -> LOW
        (
            TransactionContext(amount=30000, is_new_recipient=False, transfer_hour=11),
            "Немереме туған күніне сыйлыққа, құттықтап жіберіп жатырмын",
            RiskLevel.LOW
        ),
        # 9. Bank security threat -> HIGH
        (
            TransactionContext(amount=350000, is_new_recipient=True, transfer_hour=19),
            "Сотрудник службы безопасности банка велел перевести, иначе все счета заблокируют!",
            RiskLevel.HIGH
        ),
        # 10. Car repair to new recipient -> MEDIUM initial -> LOW after answer
        (
            TransactionContext(amount=70000, is_new_recipient=True, transfer_hour=14),
            "Оплата СТО за замену масла и колодок",
            RiskLevel.LOW
        ),
    ]

    passed = 0
    for idx, (ctx, answer, expected_level) in enumerate(test_cases, 1):
        res = RulesEngine.evaluate_with_answer(ctx, answer)
        is_ok = (res.risk_level == expected_level)
        if is_ok:
            passed += 1
        status = "PASSED" if is_ok else f"FAILED (expected {expected_level.value}, got {res.risk_level.value})"
        print(f"\nCase {idx}: [{status}] - {ctx.amount:,.0f} KZT | Expected: {expected_level.value} | Score: {res.risk_score}")
        print(f"Action: {res.action.value}")
        print(f"Explanation: {res.explanation}")

    print(f"\n==========================================")
    print(f"Results: {passed}/{len(test_cases)} unit tests passed successfully!")
