"""Friction metrics: how many legitimate clients get questioned and how long they wait."""
import pytest

import backend.app.core.rules_engine as engine_mod
from backend.app.benchmark.evaluator import (
    BASELINE_REVIEW_SECONDS,
    QUESTION_ANSWER_SECONDS,
    TRUSTED_WAIT_SECONDS,
    BenchmarkEvaluator,
)
from backend.app.core.fallback_rules import fallback_parse


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setattr(engine_mod, "parse_client_answer", fallback_parse)


def _legit(amount, new, answer="Аренда квартиры за ноябрь"):
    return {"is_scam": False, "amount": amount, "is_new_recipient": new, "answer_text": answer, "split": "test"}


def _scam():
    return {"is_scam": True, "amount": 250000.0, "is_new_recipient": True, "split": "test",
            "answer_text": "Сотрудник банка сказал срочно перевести на безопасный счёт"}


def test_friction_is_measured_for_legit_clients():
    data = [
        _legit(5000.0, False),    # passes instantly
        _legit(250000.0, True),   # asked one question, clean answer -> completes
        _scam(),
    ]
    q = BenchmarkEvaluator.run_evaluation(data, split="test").qaqpan
    assert q.legit_questioned_rate == pytest.approx(0.5)
    assert q.avg_delay_seconds == pytest.approx(QUESTION_ANSWER_SECONDS / 2)


def test_legit_sent_to_trusted_pays_the_longer_delay():
    data = [_legit(250000.0, True, answer="Мне позвонили и сказали срочно перевести"), _scam()]
    q = BenchmarkEvaluator.run_evaluation(data, split="test").qaqpan
    assert q.false_positives == 1
    assert q.avg_delay_seconds == pytest.approx(QUESTION_ANSWER_SECONDS + TRUSTED_WAIT_SECONDS)


def test_baseline_friction_is_amount_limit_only():
    data = [_legit(900000.0, False), _legit(5000.0, False), _scam()]
    b = BenchmarkEvaluator.run_evaluation(data, split="test").baseline
    assert b.legit_questioned_rate == pytest.approx(0.5)
    assert b.avg_delay_seconds == pytest.approx(BASELINE_REVIEW_SECONDS / 2)
