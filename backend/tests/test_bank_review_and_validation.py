"""Bank decision for MANUAL_BANK_REVIEW, input validation and CORS settings."""
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import backend.app.api.transfers as transfers_api
from backend.app.config import parse_cors_origins
from backend.app.db import Base, TransferRecord, get_db
from backend.app.main import app


@pytest.fixture()
def env(monkeypatch):
    monkeypatch.setattr(transfers_api, "_schedule_timeout", lambda _tid: None)
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False)

    def override():
        with Session() as db:
            yield db

    app.dependency_overrides[get_db] = override
    yield TestClient(app), Session
    app.dependency_overrides.clear()


def _seed(Session, status: str) -> str:
    tid = f"tr_{uuid.uuid4().hex[:8]}"
    with Session() as db:
        db.add(TransferRecord(transfer_id=tid, client_id="c", recipient_account="KZ1", recipient_name="n",
                              amount=700000.0, status=status, risk_tier="HIGH", risk_score=75))
        db.commit()
    return tid


def _status(Session, tid):
    with Session() as db:
        return db.get(TransferRecord, tid).status


@pytest.mark.parametrize("decision,final", [("APPROVE", "COMPLETED"), ("DECLINE", "BLOCKED")])
def test_bank_decision_resolves_manual_review(env, decision, final):
    client, Session = env
    tid = _seed(Session, "MANUAL_BANK_REVIEW")
    r = client.post(f"/api/v1/analyst/transfers/{tid}/review", json={"decision": decision, "comment": "ok"})
    assert r.status_code == 200
    assert r.json()["status"] == final
    assert _status(Session, tid) == final


@pytest.mark.parametrize("status", ["COOLING_OFF", "TRUSTED_PENDING", "COMPLETED", "AWAITING_ANSWER"])
def test_bank_decision_only_from_manual_review(env, status):
    client, Session = env
    tid = _seed(Session, status)
    r = client.post(f"/api/v1/analyst/transfers/{tid}/review", json={"decision": "APPROVE"})
    assert r.status_code == 409
    assert _status(Session, tid) == status


def test_bank_decision_404_and_double_decision(env):
    client, Session = env
    assert client.post("/api/v1/analyst/transfers/nope/review", json={"decision": "APPROVE"}).status_code == 404
    tid = _seed(Session, "MANUAL_BANK_REVIEW")
    assert client.post(f"/api/v1/analyst/transfers/{tid}/review", json={"decision": "DECLINE"}).status_code == 200
    assert client.post(f"/api/v1/analyst/transfers/{tid}/review", json={"decision": "APPROVE"}).status_code == 409


def test_bank_decision_rejects_bad_body(env):
    client, Session = env
    tid = _seed(Session, "MANUAL_BANK_REVIEW")
    assert client.post(f"/api/v1/analyst/transfers/{tid}/review", json={"decision": "MAYBE"}).status_code == 422


@pytest.mark.parametrize("patch", [
    {"recipient_account": ""},
    {"recipient_account": "   "},
    {"recipient_name": ""},
    {"client_id": ""},
    {"amount": 1e18},
    {"language": "en"},
])
def test_create_transfer_rejects_bad_input(env, patch):
    client, _ = env
    body = {"client_id": "c1", "recipient_account": "KZ123", "recipient_name": "Name", "amount": 1000.0}
    body.update(patch)
    assert client.post("/api/v1/transfers", json=body).status_code == 422


def test_cors_origins_parsing(monkeypatch):
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    assert parse_cors_origins() == ["*"]
    monkeypatch.setenv("CORS_ORIGINS", '["http://localhost:5173", "http://x.test"]')
    assert parse_cors_origins() == ["http://localhost:5173", "http://x.test"]
    monkeypatch.setenv("CORS_ORIGINS", "http://a.test, http://b.test")
    assert parse_cors_origins() == ["http://a.test", "http://b.test"]
    monkeypatch.setenv("CORS_ORIGINS", "[broken")
    assert parse_cors_origins() == ["*"]
