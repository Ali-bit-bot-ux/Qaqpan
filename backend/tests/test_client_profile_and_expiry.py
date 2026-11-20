"""Per-client typical amount, configurable trusted contact, expiry of unanswered questions."""
import uuid
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import backend.app.api.transfers as transfers_api
import backend.app.core.rules_engine as engine_mod
from backend.app.core.fallback_rules import fallback_parse
from backend.app.db import Base, TransferRecord, get_db
from backend.app.main import app


@pytest.fixture()
def env(monkeypatch):
    monkeypatch.setattr(transfers_api, "_schedule_timeout", lambda _tid: None)
    monkeypatch.setattr(engine_mod, "parse_client_answer", fallback_parse)
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False)

    def override():
        with Session() as db:
            yield db

    app.dependency_overrides[get_db] = override
    yield TestClient(app), Session
    app.dependency_overrides.clear()


def _history(Session, client_id, amounts, risk_tier="LOW", status="COMPLETED"):
    old = datetime.utcnow() - timedelta(days=5)
    with Session() as db:
        for i, amt in enumerate(amounts):
            db.add(TransferRecord(
                transfer_id=f"h_{uuid.uuid4().hex[:8]}", client_id=client_id,
                recipient_account=f"KZ_OLD_{i}", recipient_name="old", amount=amt,
                status=status, risk_tier=risk_tier, risk_score=5, created_at=old, updated_at=old,
            ))
        db.commit()


def _create(client, client_id, amount, **extra):
    body = {"client_id": client_id, "recipient_account": f"KZ{uuid.uuid4().int % 10**16:016d}",
            "recipient_name": "Name", "amount": amount, **extra}
    return client.post("/api/v1/transfers", json=body)


# --- per-client typical amount -----------------------------------------------------------
def test_new_client_uses_default_typical_amount(env):
    client, _ = env
    assert _create(client, "fresh", 600000.0).json()["status"] == "TRUSTED_PENDING"


def test_client_with_big_history_is_not_over_flagged(env):
    client, Session = env
    _history(Session, "rich", [500000.0, 520000.0, 480000.0])
    assert _create(client, "rich", 600000.0).json()["status"] == "AWAITING_ANSWER"


def test_history_needs_at_least_three_samples(env):
    client, Session = env
    _history(Session, "twice", [500000.0, 520000.0])
    assert _create(client, "twice", 600000.0).json()["status"] == "TRUSTED_PENDING"


def test_risky_history_does_not_inflate_typical_amount(env):
    client, Session = env
    # Completed but HIGH-risk (e.g. approved scams) must not teach the system "big is normal".
    _history(Session, "victim", [500000.0, 520000.0, 480000.0], risk_tier="HIGH")
    assert _create(client, "victim", 600000.0).json()["status"] == "TRUSTED_PENDING"


# --- trusted contact ------------------------------------------------------------------------
def test_default_trusted_contact(env):
    client, _ = env
    tc = _create(client, "c-default", 600000.0).json()["trusted_contact"]
    assert tc["name"] and tc["phone"]


def test_custom_trusted_contact(env):
    client, _ = env
    r = _create(client, "c-custom", 600000.0, trusted_contact_name="Данияр (Сын)",
                trusted_contact_phone="+7 700 *** ** 11")
    assert r.json()["trusted_contact"] == {"name": "Данияр (Сын)", "phone": "+7 700 *** ** 11"}


def test_trusted_contact_name_cannot_be_blank(env):
    client, _ = env
    assert _create(client, "c-blank", 600000.0, trusted_contact_name="  ").status_code == 422


# --- unanswered question expires --------------------------------------------------------------
def _awaiting(Session, age_seconds):
    tid = f"tr_{uuid.uuid4().hex[:8]}"
    when = datetime.utcnow() - timedelta(seconds=age_seconds)
    with Session() as db:
        db.add(TransferRecord(transfer_id=tid, client_id="c", recipient_account="KZ1", recipient_name="n",
                              amount=250000.0, status="AWAITING_ANSWER", risk_tier="MEDIUM",
                              risk_score=40, created_at=when, updated_at=when))
        db.commit()
    return tid


def test_stale_question_expires_and_cancels(env):
    client, Session = env
    tid = _awaiting(Session, age_seconds=3600)
    r = client.post(f"/api/v1/transfers/{tid}/answer", json={"answer_text": "Аренда квартиры"})
    assert r.status_code == 409
    assert client.get(f"/api/v1/transfers/{tid}").json()["status"] == "CANCELLED"


def test_fresh_question_can_still_be_answered(env):
    client, Session = env
    tid = _awaiting(Session, age_seconds=5)
    r = client.post(f"/api/v1/transfers/{tid}/answer", json={"answer_text": "Аренда квартиры"})
    assert r.status_code == 200
