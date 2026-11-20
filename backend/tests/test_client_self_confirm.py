"""Cooling-off exit: the client may confirm their own transfer after the repeated warning."""
import uuid
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.db import Base, TransferRecord, get_db
from backend.app.main import app


@pytest.fixture()
def env():
    # Isolated in-memory DB: never touches the real database from .env.
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False)

    def override():
        with Session() as db:
            yield db

    app.dependency_overrides[get_db] = override
    yield TestClient(app), Session
    app.dependency_overrides.clear()


def _seed(Session, status: str, age_seconds: float = 3600) -> str:
    """Seed a transfer that entered its current status age_seconds ago (default: long ago)."""
    tid = f"tr_{uuid.uuid4().hex[:8]}"
    when = datetime.utcnow() - timedelta(seconds=age_seconds)
    with Session() as db:
        db.add(TransferRecord(
            transfer_id=tid, client_id="c1", recipient_account="KZ1", recipient_name="n",
            amount=700000.0, status=status, risk_tier="HIGH", risk_score=75,
            created_at=when, updated_at=when,
        ))
        db.commit()
    return tid


def _status(Session, tid: str) -> str:
    with Session() as db:
        return db.get(TransferRecord, tid).status


def test_confirm_after_warning_completes(env):
    client, Session = env
    tid = _seed(Session, "COOLING_OFF")
    r = client.post(f"/api/v1/transfers/{tid}/confirm", json={"warning_acknowledged": True})
    assert r.status_code == 200
    assert r.json()["status"] == "COMPLETED"
    assert _status(Session, tid) == "COMPLETED"


def test_confirm_requires_acknowledged_warning(env):
    client, Session = env
    tid = _seed(Session, "COOLING_OFF")
    r = client.post(f"/api/v1/transfers/{tid}/confirm", json={"warning_acknowledged": False})
    assert r.status_code == 400
    assert _status(Session, tid) == "COOLING_OFF"


@pytest.mark.parametrize("status", ["TRUSTED_PENDING", "AWAITING_ANSWER", "BLOCKED", "COMPLETED", "MANUAL_BANK_REVIEW"])
def test_confirm_only_from_cooling_off(env, status):
    client, Session = env
    tid = _seed(Session, status)
    r = client.post(f"/api/v1/transfers/{tid}/confirm", json={"warning_acknowledged": True})
    assert r.status_code == 409
    assert _status(Session, tid) == status


def test_confirm_unknown_transfer_404(env):
    client, _ = env
    r = client.post("/api/v1/transfers/nope/confirm", json={"warning_acknowledged": True})
    assert r.status_code == 404


def test_confirm_twice_second_is_409(env):
    client, Session = env
    tid = _seed(Session, "COOLING_OFF")
    assert client.post(f"/api/v1/transfers/{tid}/confirm", json={"warning_acknowledged": True}).status_code == 200
    assert client.post(f"/api/v1/transfers/{tid}/confirm", json={"warning_acknowledged": True}).status_code == 409


# --- cooling period: the client must wait before confirming on their own --------------------
def test_confirm_blocked_until_cooling_period_ends(env):
    client, Session = env
    tid = _seed(Session, "COOLING_OFF", age_seconds=1)
    r = client.post(f"/api/v1/transfers/{tid}/confirm", json={"warning_acknowledged": True})
    assert r.status_code == 409
    assert "seconds left" in r.json()["detail"]
    assert _status(Session, tid) == "COOLING_OFF"


def test_cancel_and_manual_review_are_allowed_during_cooling_period(env):
    client, Session = env
    t1 = _seed(Session, "COOLING_OFF", age_seconds=1)
    t2 = _seed(Session, "COOLING_OFF", age_seconds=1)
    assert client.post(f"/api/v1/transfers/{t1}/cancel").status_code == 200
    r = client.post(f"/api/v1/transfers/{t2}/manual-review", json={"warning_acknowledged": True})
    assert r.status_code == 200


def test_countdown_is_exposed_only_while_cooling(env):
    client, Session = env
    fresh = client.get(f"/api/v1/transfers/{_seed(Session, 'COOLING_OFF', age_seconds=1)}").json()
    assert 0 < fresh["cooling_seconds_left"] <= 30
    done = client.get(f"/api/v1/transfers/{_seed(Session, 'COOLING_OFF')}").json()
    assert done["cooling_seconds_left"] == 0
    other = client.get(f"/api/v1/transfers/{_seed(Session, 'TRUSTED_PENDING')}").json()
    assert other["cooling_seconds_left"] is None
