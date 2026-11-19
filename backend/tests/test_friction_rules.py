"""Friction: micro-transfers and plain family requests must not trigger questions or escalations."""
import pytest

import backend.app.core.rules_engine as engine_mod
from backend.app.core.fallback_rules import fallback_parse
from backend.app.core.rules_engine import NextAction, RiskLevel, RulesEngine, TransactionContext


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setattr(engine_mod, "parse_client_answer", fallback_parse)


def ctx(amount, new=True, hour=14, freq=1):
    return TransactionContext(amount=float(amount), is_new_recipient=new, transfer_hour=hour,
                              frequency_last_hour=freq)


# --- micro-transfers ---------------------------------------------------------------------------
def test_micro_transfer_at_night_to_new_recipient_passes_without_question():
    res = RulesEngine.evaluate_initial_transaction(ctx(2500, new=True, hour=23))
    assert res.action == NextAction.ALLOW


def test_ordinary_small_night_transfer_still_asks():
    # 40 000 is not a micro-transfer: new recipient + night keep their weight.
    res = RulesEngine.evaluate_initial_transaction(ctx(40000, new=True, hour=23))
    assert res.action == NextAction.ASK_QUESTION


def test_micro_transfers_in_a_burst_are_still_caught():
    # Splitting a theft into tiny pieces must not hide it: frequency keeps its weight.
    res = RulesEngine.evaluate_initial_transaction(ctx(2500, new=True, hour=23, freq=3))
    assert res.action == NextAction.ASK_QUESTION


# --- plain family requests -----------------------------------------------------------------------
@pytest.mark.parametrize("answer", [
    "Мама попросила",
    "Папа попросил перевести другу на такси",
    "Брат позвонил и попросил, возвращаю долг",
    "Сестра сказала, что надо отправить ей на проезд",
    "Анам сұрады",
    "Ағам қоңырау шалып, қарызды қайтаруды сұрады",
])
def test_plain_family_request_is_not_escalated(answer):
    res = RulesEngine.evaluate_with_answer(ctx(250000, new=True), answer)
    assert res.risk_level != RiskLevel.HIGH
    assert res.action != NextAction.REQUIRE_TRUSTED_APPROVAL


@pytest.mark.parametrize("answer", [
    "Мама позвонила, сказала срочно перевести на безопасный счёт",
    "Сын позвонил, сказал что сбил человека, нужны деньги на мировую",
    "Звонил внук, попал в аварию, срочно просит деньги",
    "Ұлым деп таныстырған адам апатқа ұшырадым деп ақша сұрады",
])
def test_family_story_with_pressure_still_escalates(answer):
    res = RulesEngine.evaluate_with_answer(ctx(250000, new=True), answer)
    assert res.risk_level == RiskLevel.HIGH


def test_unknown_caller_without_family_still_escalates():
    res = RulesEngine.evaluate_with_answer(ctx(250000, new=True), "Позвонил человек и попросил перевести")
    assert res.risk_level == RiskLevel.HIGH
