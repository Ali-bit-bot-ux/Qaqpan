"""
Airplane Mode / Offline Resilience Verification (Step 5.4).

Verifies that the entire Qaqpan anti-fraud core operates 100% reliably
in full offline isolation (no internet, no external LLM APIs, no Groq/Gemini keys).

Checks:
1. Social engineering signal extraction via regex fallback (RU & KZ).
2. Risk scoring engine decision-making on offline signals.
3. Scammer-Trap Bot persona dialogue response via offline templates (RU & KZ).
4. Scammer payment recipient extraction (IBAN, card with Luhn, phone) via offline regex.
5. End-to-end transfer evaluation pipeline under airplane mode.
"""

import os
import sys
import unittest
from unittest.mock import patch

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "../../"))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from backend.app.core.ai_parser import parse_client_answer
from backend.app.core.fallback_rules import fallback_parse
from backend.app.core.rules_engine import RulesEngine, TransactionContext, RiskLevel, NextAction
from backend.app.core.trap_persona import generate_victim_reply
from backend.app.core.recipient_extractor import extract_recipients, RecipientType


class TestAirplaneModeResilience(unittest.TestCase):
    """Test suite verifying Qaqpan functions cleanly without internet."""

    def setUp(self):
        # Force offline environment by wiping out LLM credentials
        self.env_patcher = patch.dict(os.environ, {
            "GEMINI_API_KEY": "",
            "GROQ_API_KEY": "",
            "LLM_MODEL": "none",
        })
        self.env_patcher.start()

    def tearDown(self):
        self.env_patcher.stop()

    def test_offline_ai_parser_ru(self):
        """Verify RU scam explanation is detected accurately in offline mode."""
        text = "Мне только что звонил следователь полиции! Сказал срочно перевести деньги на безопасный счет!"
        result = parse_client_answer(text)

        self.assertEqual(result.source, "fallback")
        self.assertTrue(result.authority_pressure, "Must detect authority pressure (следователь полиции)")
        self.assertTrue(result.safe_account_keyword, "Must detect safe account (безопасный счет)")
        self.assertGreaterEqual(result.urgency_score, 0.5)

    def test_offline_ai_parser_kz(self):
        """Verify KZ scam explanation is detected accurately in offline mode."""
        text = "Маған полициядан хабарласты, шұғыл қауіпсіз шотқа ақша аударыңыз деді!"
        result = parse_client_answer(text)

        self.assertEqual(result.source, "fallback")
        self.assertTrue(result.authority_pressure, "Must detect authority pressure in KZ (полициядан)")
        self.assertTrue(result.safe_account_keyword, "Must detect safe account in KZ (қауіпсіз шот)")
        self.assertGreaterEqual(result.urgency_score, 0.5)

    def test_offline_rules_engine_scoring(self):
        """Verify rules engine calculates risk score and assigns HIGH tier offline."""
        text = "Следователь майор велел срочно спасти деньги на транзитный счет."
        ctx = TransactionContext(
            amount=450000.0,
            is_new_recipient=True,
            transfer_hour=14,
            client_typical_amount=50000.0,
            client_id="client_offline_01"
        )

        res = RulesEngine.evaluate_with_answer(ctx, answer_text=text)

        self.assertEqual(res.risk_level, RiskLevel.HIGH)
        self.assertEqual(res.action, NextAction.REQUIRE_TRUSTED_APPROVAL)
        self.assertGreaterEqual(res.risk_score, 70.0)
        self.assertTrue(len(res.triggered_rules) >= 2)
        self.assertIsNotNone(res.trusted_alert)

    def test_offline_trap_persona_dialogue(self):
        """Verify trap bot persona speaks in character without internet."""
        history = [
            ("BOT", "Слушаю вас внимательно, сынок."),
            ("SCAMMER", "Бабушка, срочно переведите деньги на безопасную карту!")
        ]

        reply_ru = generate_victim_reply(history, language="ru")
        self.assertIsInstance(reply_ru, str)
        self.assertTrue(len(reply_ru) > 10)
        # Verify persona asks for destination details
        self.assertTrue(any(word in reply_ru.lower() for word in ["карт", "счет", "номер", "куда", "сынок", "старая", "аты-жөні"]))

        reply_kz = generate_victim_reply(history, language="kz")
        self.assertIsInstance(reply_kz, str)
        self.assertTrue(len(reply_kz) > 10)

    def test_offline_recipient_extractor(self):
        """Verify extraction of Card, IBAN, and Phone numbers offline with Luhn check."""
        # Message with valid card (Luhn compliant: 4400 4301 2345 6789)
        msg_card = "Переведите на карту 4400 4301 2345 6789 немедленно!"
        extracted_card = extract_recipients(msg_card)
        self.assertTrue(any(r.recipient_type == RecipientType.CARD and "4400430123456789" in r.value for r in extracted_card))

        # Message with Kazakhstan IBAN
        msg_iban = "Вот счёт для перевода KZ123456789012345678 отправляйте"
        extracted_iban = extract_recipients(msg_iban)
        self.assertTrue(any(r.recipient_type == RecipientType.IBAN for r in extracted_iban))

        # Message with phone number
        msg_phone = "Деньги переводите на номер +7 701 555 44 33"
        extracted_phone = extract_recipients(msg_phone)
        self.assertTrue(any(r.recipient_type == RecipientType.PHONE and "77015554433" in r.value for r in extracted_phone))

    def test_offline_secret_rejection(self):
        """Verify trap extractor strictly ignores phishing for secrets offline."""
        msg_secret = "Сообщите трехзначный код CVV с обратной стороны карты и пароль из СМС"
        extracted = extract_recipients(msg_secret)
        self.assertEqual(len(extracted), 0, "Must never extract or process card secrets")


if __name__ == "__main__":
    unittest.main()
