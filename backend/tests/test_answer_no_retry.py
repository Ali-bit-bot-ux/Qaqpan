"""An answer that does not clear suspicion escalates; the client cannot re-answer until it sounds clean."""
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import backend.app.api.transfers as transfers_api
import backend.app.core.rules_engine as engine_mod
from backend.app.core.fallback_rules import fallback_parse
from backend.app.core.rules_engine import NextAction, RiskLevel, RulesEngine, TransactionContext
from backend.app.db import Base, TransferRecord, get_db
from backend.app.main import app

SCAMMY = "Мне позвонили и сказали срочно перевести деньги"
CLEAN = "Аренда квартиры"


@pytest.fixture(autouse=True)
def offline_parser(monkeypatch):
    # Deterministic, no network: always use the regex parser.
    monkeypatch.setattr(engine_mod, "parse_client_answer", fallback_parse)
    monkeypatch.setattr(transfers_api, "_schedule_timeout", lambda _tid: None)


def _ctx() -> TransactionContext:
    return TransactionContext(amount=250000.0, is_new_recipient=True, transfer_hour=14)


def test_suspicious_answer_is_not_left_at_medium():
    res = RulesEngine.evaluate_with_answer(_ctx(), SCAMMY)
    assert res.risk_level == RiskLevel.HIGH
    assert res.action == NextAction.REQUIRE_TRUSTED_APPROVAL
    assert res.trusted_alert is not None


def test_clean_answer_still_passes():
    res = RulesEngine.evaluate_with_answer(_ctx(), CLEAN)
    assert res.risk_level == RiskLevel.LOW
    assert res.action == NextAction.ALLOW


@pytest.fixture()
def client_and_db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False)

    def override():
        with Session() as db:
            yield db

    app.dependency_overrides[get_db] = override
    yield TestClient(app), Session
    app.dependency_overrides.clear()


def _seed(Session) -> str:
    tid = f"tr_{uuid.uuid4().hex[:8]}"
    with Session() as db:
        db.add(TransferRecord(
            transfer_id=tid, client_id="c-retry", recipient_account="KZ9", recipient_name="n",
            amount=250000.0, status="AWAITING_ANSWER", risk_tier="MEDIUM", risk_score=40,
        ))
        db.commit()
    return tid


def test_api_escalates_and_blocks_coached_retry(client_and_db):
    client, Session = client_and_db
    tid = _seed(Session)
    r1 = client.post(f"/api/v1/transfers/{tid}/answer", json={"answer_text": SCAMMY})
    assert r1.status_code == 200
    assert r1.json()["status"] == "TRUSTED_PENDING"
    # Coached resubmission with a clean story must not slip through.
    r2 = client.post(f"/api/v1/transfers/{tid}/answer", json={"answer_text": CLEAN})
    assert r2.status_code == 400
    assert client.get(f"/api/v1/transfers/{tid}").json()["status"] == "TRUSTED_PENDING"
