"""Cooling-off exit: the client may confirm their own transfer after the repeated warning."""
import uuid

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


def _seed(Session, status: str) -> str:
    tid = f"tr_{uuid.uuid4().hex[:8]}"
    with Session() as db:
        db.add(TransferRecord(
            transfer_id=tid, client_id="c1", recipient_account="KZ1", recipient_name="n",
            amount=700000.0, status=status, risk_tier="HIGH", risk_score=75,
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
