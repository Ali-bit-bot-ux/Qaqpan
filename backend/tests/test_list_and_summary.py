"""GET /transfers (client history, pending requests) and the analyst feed summary."""
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
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False)

    def override():
        with Session() as db:
            yield db

    app.dependency_overrides[get_db] = override
    yield TestClient(app), Session
    app.dependency_overrides.clear()


def _add(Session, client_id, status="COMPLETED", tier="LOW", age_minutes=0, amount=1000.0):
    tid = f"tr_{uuid.uuid4().hex[:8]}"
    when = datetime.utcnow() - timedelta(minutes=age_minutes)
    with Session() as db:
        db.add(TransferRecord(transfer_id=tid, client_id=client_id, recipient_account="KZ1",
                              recipient_name="n", amount=amount, status=status, risk_tier=tier,
                              risk_score=10, created_at=when, updated_at=when))
        db.commit()
    return tid


# --- GET /transfers -------------------------------------------------------------------------
def test_list_filters_by_client_and_is_newest_first(env):
    client, Session = env
    old = _add(Session, "grandma", age_minutes=30)
    new = _add(Session, "grandma", age_minutes=1)
    _add(Session, "someone_else")
    r = client.get("/api/v1/transfers", params={"client_id": "grandma"})
    assert r.status_code == 200
    body = r.json()
    assert body["total_count"] == 2
    assert [t["transfer_id"] for t in body["transfers"]] == [new, old]


def test_list_filters_by_status_for_trusted_requests(env):
    client, Session = env
    pending = _add(Session, "a", status="TRUSTED_PENDING", tier="HIGH")
    _add(Session, "b", status="COMPLETED")
    body = client.get("/api/v1/transfers", params={"status": "TRUSTED_PENDING"}).json()
    assert [t["transfer_id"] for t in body["transfers"]] == [pending]


def test_list_respects_limit_but_total_count_is_the_full_match(env):
    client, Session = env
    for i in range(5):
        _add(Session, "many", age_minutes=i)
    body = client.get("/api/v1/transfers", params={"client_id": "many", "limit": 2}).json()
    assert len(body["transfers"]) == 2
    assert body["total_count"] == 5


def test_list_unknown_client_is_empty_not_error(env):
    client, _ = env
    body = client.get("/api/v1/transfers", params={"client_id": "nobody"}).json()
    assert body == {"total_count": 0, "transfers": []}


@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 201}, {"status": "NOPE"}])
def test_list_rejects_bad_params(env, params):
    client, _ = env
    assert client.get("/api/v1/transfers", params=params).status_code == 422


def test_get_single_transfer_still_works_next_to_the_list(env):
    client, Session = env
    tid = _add(Session, "c")
    assert client.get(f"/api/v1/transfers/{tid}").json()["transfer_id"] == tid


# --- analyst feed summary ---------------------------------------------------------------------
def test_feed_summary_counts_all_transfers_zero_filled(env):
    client, Session = env
    _add(Session, "a", status="COMPLETED", tier="LOW")
    _add(Session, "b", status="TRUSTED_PENDING", tier="HIGH")
    _add(Session, "c", status="BLOCKED", tier="HIGH")
    s = client.get("/api/v1/analyst/feed", params={"source": "TRANSFER"}).json()["summary"]
    assert s["total_transfers"] == 3
    assert s["by_risk_tier"] == {"LOW": 1, "MEDIUM": 0, "HIGH": 2, "CRITICAL": 0}
    assert s["by_status"]["TRUSTED_PENDING"] == 1
    assert s["by_status"]["BLOCKED"] == 1
    assert s["by_status"]["AWAITING_ANSWER"] == 0  # zero-filled: the UI never needs defaults


def test_feed_summary_ignores_filters_and_limit(env):
    client, Session = env
    for _ in range(4):
        _add(Session, "x", tier="HIGH", status="BLOCKED")
    _add(Session, "y", tier="LOW")
    body = client.get("/api/v1/analyst/feed", params={"risk_tier": "LOW", "limit": 1}).json()
    assert len(body["cards"]) == 1
    assert body["summary"]["total_transfers"] == 5
    assert body["summary"]["by_risk_tier"]["HIGH"] == 4
