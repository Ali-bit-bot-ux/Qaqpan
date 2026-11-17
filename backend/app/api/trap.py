"""
Scammer-trap API (team-only simulator).

The bot plays a cautious elderly victim in a dialogue with a suspected scammer.
Each scammer message is persisted, scanned for payment recipients (LLM with
regex fallback), and answered by the victim persona. Extracted recipients are
reviewed by the bank analyst via /analyst/feed and the decision endpoint.

All blocking LLM I/O runs in a threadpool; 404/409 semantics mirror the
transfers API. Events published: trap_message, trap_recipient,
trap_recipient_decision, trap_session_timeout.

Every session carries an absolute UTC expires_at deadline
(TRAP_SESSION_SECONDS, default 600). Posting to an expired ACTIVE session
compares-and-swaps it to TIMEOUT exactly once, publishes trap_session_timeout,
and returns 409. A per-session asyncio task enforces the deadline even when
nobody posts; ACTIVE sessions are re-armed at startup.
"""

import asyncio
import logging
import os
import time
import uuid
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from ..db import get_db, SessionLocal, TrapSession, TrapMessage, TrapRecipient
from ..models.schemas import (
    TrapSessionCreate,
    TrapMessageCreate,
    TrapSessionStopRequest,
    TrapSessionResponse,
    TrapSessionDetailResponse,
    TrapMessageOut,
    TrapRecipientOut,
    RecipientDecisionRequest,
    TrapSessionStatus,
)
from ..core.events import event_bus
from ..core.trap_persona import (
    generate_victim_reply, _fallback_reply, DEFAULT_TIMEOUT_SECONDS,
    TrapLLMTrace, trap_llm_trace,
)
from ..core.recipient_extractor import extract_recipients, extract_recipients_offline

router = APIRouter(prefix="/trap", tags=["Scammer Trap (Team Simulator)"])
logger = logging.getLogger("qaqpan.trap")

ACTIVE_STATUS = "ACTIVE"
STOPPED_STATUS = "STOPPED"
TIMEOUT_STATUS = "TIMEOUT"
NEW_STATUS = "NEW"

DEFAULT_TRAP_SESSION_SECONDS = 600
_trap_tasks: dict[str, asyncio.Task[None]] = {}


def _trap_session_ttl_seconds() -> int:
    """Positive TRAP_SESSION_SECONDS; invalid values fail closed to the default."""
    raw = os.getenv("TRAP_SESSION_SECONDS", "").strip()
    if not raw:
        return DEFAULT_TRAP_SESSION_SECONDS
    try:
        seconds = int(raw)
    except ValueError:
        seconds = 0
    if seconds <= 0:
        logger.warning(
            "Invalid TRAP_SESSION_SECONDS=%r; falling back to %d",
            raw, DEFAULT_TRAP_SESSION_SECONDS,
        )
        return DEFAULT_TRAP_SESSION_SECONDS
    return seconds


def _expire_session(
    db: Session,
    session_id: str,
    expected_expires_at: Optional[datetime],
) -> Optional[TrapSessionResponse]:
    """
    Compare-and-swap an expired ACTIVE session to TIMEOUT. Commits before
    returning so callers may publish the snapshot without holding a transaction.
    Returns the committed snapshot, or None when this caller lost the race.
    """
    now = datetime.utcnow()
    updated = db.query(TrapSession).filter(
        TrapSession.session_id == session_id,
        TrapSession.status == ACTIVE_STATUS,
        TrapSession.expires_at == expected_expires_at,
        TrapSession.expires_at.isnot(None),
        TrapSession.expires_at <= now,
    ).update({
        TrapSession.status: TIMEOUT_STATUS,
        TrapSession.updated_at: now,
    }, synchronize_session=False)
    if updated != 1:
        db.rollback()
        return None
    session = db.query(TrapSession).filter(TrapSession.session_id == session_id).one()
    # synchronize_session=False leaves any pre-loaded instance stale; reload it.
    db.refresh(session)
    response = _session_to_response(session)
    db.commit()
    return response


async def _expire_after(session_id: str) -> None:
    while True:
        snapshot: Optional[TrapSessionResponse] = None
        wait_seconds: Optional[float] = None
        with SessionLocal() as db:
            session = db.get(TrapSession, session_id)
            if session is None or session.status != ACTIVE_STATUS or session.expires_at is None:
                return
            remaining = (session.expires_at - datetime.utcnow()).total_seconds()
            if remaining <= 0:
                snapshot = _expire_session(db, session_id, session.expires_at)
            else:
                wait_seconds = remaining
        # Never retain a session/transaction while sleeping or publishing.
        if wait_seconds is not None:
            await asyncio.sleep(wait_seconds)
            continue
        if snapshot is not None:
            await event_bus.publish("trap_session_timeout", snapshot.model_dump(mode="json"))
        return


def _schedule_expiry(session_id: str) -> None:
    existing = _trap_tasks.get(session_id)
    if existing is not None and not existing.done():
        return
    task = asyncio.create_task(_expire_after(session_id))
    _trap_tasks[session_id] = task

    def finished(done: asyncio.Task[None]) -> None:
        if _trap_tasks.get(session_id) is done:
            _trap_tasks.pop(session_id)
        if not done.cancelled() and done.exception() is not None:
            logger.error("Trap expiry timer failed for %s", session_id, exc_info=done.exception())

    task.add_done_callback(finished)


def recover_trap_sessions() -> None:
    """Re-arm expiry timers for sessions still ACTIVE from a previous run."""
    with SessionLocal() as db:
        active_ids = db.query(TrapSession.session_id).filter(
            TrapSession.status == ACTIVE_STATUS,
            TrapSession.expires_at.isnot(None),
        ).all()
    for (session_id,) in active_ids:
        _schedule_expiry(session_id)


async def stop_trap_tasks() -> None:
    tasks = list(_trap_tasks.values())
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    _trap_tasks.clear()


def _message_to_out(msg: TrapMessage) -> TrapMessageOut:
    return TrapMessageOut(
        id=msg.id,
        sender=msg.sender,
        text=msg.text,
        created_at=msg.created_at,
    )


def _recipient_to_out(rec: TrapRecipient) -> TrapRecipientOut:
    return TrapRecipientOut(
        id=rec.id,
        session_id=rec.session_id,
        recipient_type=rec.recipient_type,
        value=rec.value,
        quote=rec.quote,
        status=rec.status,
        decision_comment=rec.decision_comment,
        created_at=rec.created_at,
        decided_at=rec.decided_at,
    )


def _session_to_response(session: TrapSession) -> TrapSessionResponse:
    return TrapSessionResponse(
        session_id=session.session_id,
        status=session.status,
        language=session.language,
        message_count=session.message_count,
        max_messages=session.max_messages,
        expires_at=session.expires_at,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


def _session_detail(db: Session, session: TrapSession) -> TrapSessionDetailResponse:
    messages = (
        db.query(TrapMessage)
        .filter(TrapMessage.session_id == session.session_id)
        .order_by(TrapMessage.id)
        .all()
    )
    recipients = (
        db.query(TrapRecipient)
        .filter(TrapRecipient.session_id == session.session_id)
        .order_by(TrapRecipient.id)
        .all()
    )
    return TrapSessionDetailResponse(
        **_session_to_response(session).model_dump(),
        messages=[_message_to_out(m) for m in messages],
        recipients=[_recipient_to_out(r) for r in recipients],
    )


@router.post("/sessions", response_model=TrapSessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(
    payload: TrapSessionCreate,
    db: Session = Depends(get_db)
):
    session = TrapSession(
        session_id=f"trap_{uuid.uuid4().hex[:8]}",
        status=ACTIVE_STATUS,
        language=payload.language,
        expires_at=datetime.utcnow() + timedelta(seconds=_trap_session_ttl_seconds()),
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    # Async so the expiry timer can be armed on the running event loop.
    _schedule_expiry(session.session_id)
    return _session_to_response(session)


@router.get("/sessions", response_model=List[TrapSessionResponse])
def list_sessions(
    status_filter: Optional[TrapSessionStatus] = Query(None, alias="status", description="Filter by session status"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    query = db.query(TrapSession).order_by(TrapSession.created_at.desc())
    if status_filter:
        query = query.filter(TrapSession.status == status_filter)
    return [_session_to_response(s) for s in query.limit(limit).all()]


@router.get("/sessions/{session_id}", response_model=TrapSessionDetailResponse)
def get_session(
    session_id: str,
    db: Session = Depends(get_db)
):
    session = db.get(TrapSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Trap session not found")
    return _session_detail(db, session)


@router.post("/sessions/{session_id}/messages", response_model=TrapSessionDetailResponse)
async def post_message(
    session_id: str,
    payload: TrapMessageCreate,
    db: Session = Depends(get_db)
):
    session = db.get(TrapSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Trap session not found")
    if (
        session.status == ACTIVE_STATUS
        and session.expires_at is not None
        and session.expires_at <= datetime.utcnow()
    ):
        # Deadline reached: CAS to TIMEOUT once, commit, notify, reject the post.
        snapshot = _expire_session(db, session_id, session.expires_at)
        if snapshot is not None:
            await event_bus.publish("trap_session_timeout", snapshot.model_dump(mode="json"))
        raise HTTPException(status_code=409, detail="Trap session timed out")
    if session.status != ACTIVE_STATUS:
        raise HTTPException(
            status_code=409,
            detail=f"Trap session is in status {session.status}, cannot accept messages"
        )
    if session.message_count >= session.max_messages:
        raise HTTPException(status_code=409, detail="Trap session message limit reached")
    expected_count = session.message_count
    language = session.language
    expires_at = session.expires_at
    history_rows = (
        db.query(TrapMessage)
        .filter(TrapMessage.session_id == session_id)
        .order_by(TrapMessage.id)
        .all()
    )
    history = [(m.sender, m.text) for m in history_rows] + [("SCAMMER", payload.text)]
    # Release even the read transaction before awaiting external work. No pending
    # rows may autoflush and take a write lock while the model is running.
    db.rollback()

    started = time.monotonic()
    extraction_trace = TrapLLMTrace(uuid.uuid4().hex)
    persona_trace = TrapLLMTrace(uuid.uuid4().hex)
    token = trap_llm_trace.set(extraction_trace)
    try:
        found = await asyncio.wait_for(
            run_in_threadpool(extract_recipients, payload.text), DEFAULT_TIMEOUT_SECONDS
        )
        extraction_source = extraction_trace.source
    except Exception as exc:
        logger.warning("Trap extraction unavailable (%s); using local parser", type(exc).__name__)
        found = extract_recipients_offline(payload.text)
        extraction_source = "regex_api_fallback"
    finally:
        trap_llm_trace.reset(token)
    token = trap_llm_trace.set(persona_trace)
    try:
        reply = await asyncio.wait_for(
            run_in_threadpool(generate_victim_reply, history, language), DEFAULT_TIMEOUT_SECONDS
        )
        if not isinstance(reply, str) or not reply.strip() or len(reply) > 400:
            raise ValueError("Invalid persona reply")
        persona_source = persona_trace.source
    except Exception as exc:
        logger.warning("Trap reply unavailable (%s); using local template", type(exc).__name__)
        reply = _fallback_reply(history, language)
        persona_source = "template_api_fallback"
    finally:
        trap_llm_trace.reset(token)

    new_recipients: List[TrapRecipient] = []
    try:
        # CAS is the FIRST write. A loser persists neither messages nor recipients.
        updated = db.query(TrapSession).filter(
            TrapSession.session_id == session_id,
            TrapSession.status == ACTIVE_STATUS,
            TrapSession.message_count == expected_count,
            TrapSession.message_count < TrapSession.max_messages,
            # Deadline guard: an expired session must lose even if its counters match.
            TrapSession.expires_at == expires_at,
            (TrapSession.expires_at.is_(None)) | (TrapSession.expires_at > datetime.utcnow()),
        ).update({
            TrapSession.message_count: expected_count + 1,
            TrapSession.updated_at: datetime.utcnow(),
        }, synchronize_session=False)
        if updated != 1:
            db.rollback()
            # Surface expiry as TIMEOUT instead of an opaque write-race conflict.
            if expires_at is not None and expires_at <= datetime.utcnow():
                snapshot = _expire_session(db, session_id, expires_at)
                if snapshot is not None:
                    await event_bus.publish("trap_session_timeout", snapshot.model_dump(mode="json"))
                raise HTTPException(status_code=409, detail="Trap session timed out")
            raise HTTPException(status_code=409, detail="Trap session changed while posting message")

        existing_keys = {
            (r.recipient_type, r.value)
            for r in db.query(TrapRecipient).filter(TrapRecipient.session_id == session_id).all()
        }
        for item in found:
            key = (item.recipient_type.value, item.value)
            if key in existing_keys:
                continue
            existing_keys.add(key)
            row = TrapRecipient(
                session_id=session_id, recipient_type=item.recipient_type.value,
                value=item.value, quote=item.quote, status=NEW_STATUS,
            )
            db.add(row)
            new_recipients.append(row)
        db.add(TrapMessage(session_id=session_id, sender="SCAMMER", text=payload.text))
        db.add(TrapMessage(session_id=session_id, sender="BOT", text=reply))
        db.flush()
        db.refresh(session)
        detail = _session_detail(db, session)
        recipient_events = [_recipient_to_out(row).model_dump(mode="json") for row in new_recipients]
        db.commit()
    except Exception:
        db.rollback()
        raise

    # Snapshot sources above: abandoned workers must not relabel accepted fallbacks.
    logger.info(
        "Trap API accepted extraction_call_id=%s source=%s persona_call_id=%s "
        "source=%s elapsed_ms=%.0f",
        extraction_trace.call_id, extraction_source, persona_trace.call_id,
        persona_source, (time.monotonic() - started) * 1000,
    )
    # Publish only committed snapshots, without opening a new DB transaction.
    await event_bus.publish("trap_message", {
        "session_id": session_id, "sender": "SCAMMER", "text": payload.text
    })
    for recipient_event in recipient_events:
        await event_bus.publish("trap_recipient", recipient_event)
    await event_bus.publish("trap_message", {
        "session_id": session_id, "sender": "BOT", "text": reply
    })
    return detail


@router.post("/sessions/{session_id}/stop", response_model=TrapSessionResponse)
def stop_session(
    session_id: str,
    payload: TrapSessionStopRequest = TrapSessionStopRequest(),
    db: Session = Depends(get_db)
):
    session = db.get(TrapSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Trap session not found")
    updated = db.query(TrapSession).filter(
        TrapSession.session_id == session_id,
        TrapSession.status == ACTIVE_STATUS,
    ).update({
        TrapSession.status: STOPPED_STATUS,
        TrapSession.updated_at: datetime.utcnow(),
    }, synchronize_session=False)
    if updated != 1:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail=f"Trap session is in status {session.status}, cannot stop"
        )
    db.refresh(session)
    response = _session_to_response(session)
    db.commit()
    return response


@router.post("/recipients/{recipient_id}/decision", response_model=TrapRecipientOut)
async def decide_recipient(
    recipient_id: int,
    payload: RecipientDecisionRequest,
    db: Session = Depends(get_db)
):
    rec = db.get(TrapRecipient, recipient_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="Trap recipient not found")
    updated = db.query(TrapRecipient).filter(
        TrapRecipient.id == recipient_id,
        TrapRecipient.status == NEW_STATUS,
    ).update({
        TrapRecipient.status: payload.decision.value,
        TrapRecipient.decision_comment: payload.comment,
        TrapRecipient.decided_at: datetime.utcnow(),
    }, synchronize_session=False)
    if updated != 1:
        db.rollback()
        raise HTTPException(status_code=409, detail="Recipient already decided")
    db.refresh(rec)
    out = _recipient_to_out(rec)
    db.commit()
    await event_bus.publish("trap_recipient_decision", out.model_dump(mode="json"))
    return out
