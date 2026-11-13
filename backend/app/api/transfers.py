import uuid
import json
import asyncio
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse
from starlette.concurrency import run_in_threadpool

from ..db import get_db, SessionLocal, TransferRecord
from ..models.schemas import (
    TransferCreate,
    TransferResponse,
    TransferStatus,
    RiskTier,
    AnswerRequest,
    CancelRequest,
    TrustedContactInfo
)
from ..core.state_machine import TransferStateMachine, InvalidStateTransitionError
from ..core.events import event_bus
from ..core.rules_engine import RulesEngine, TransactionContext, RiskLevel, ScoringResult

router = APIRouter(prefix="/transfers", tags=["Transfers (Client)"])
_timeout_tasks: set[asyncio.Task] = set()

CLIENT_TYPICAL_AMOUNT = 50000.0
TRUSTED_TIMEOUT_SECONDS = 30
QUESTION_RU = "Для чего вы совершаете данный перевод?"
QUESTION_KZ = "Бұл аударымды не үшін жасап жатырсыз?"
TRUSTED_CONTACT_NAME = "Айгерим (Дочь)"
TRUSTED_CONTACT_PHONE = "+7 701 *** ** 44"


def _build_context(
    db: Session,
    client_id: str,
    amount: float,
    recipient_account: str,
) -> TransactionContext:
    """Derive scoring features from stored transfer history."""
    since = datetime.utcnow() - timedelta(hours=1)
    recent_count = (
        db.query(TransferRecord)
        .filter(
            TransferRecord.client_id == client_id,
            TransferRecord.created_at >= since,
        )
        .count()
    )
    known_recipient = (
        db.query(TransferRecord)
        .filter(
            TransferRecord.client_id == client_id,
            TransferRecord.recipient_account == recipient_account,
            TransferRecord.status == TransferStatus.COMPLETED.value,
        )
        .first()
    )
    return TransactionContext(
        amount=amount,
        is_new_recipient=known_recipient is None,
        transfer_hour=datetime.now().hour,
        frequency_last_hour=recent_count + 1,
        client_typical_amount=CLIENT_TYPICAL_AMOUNT,
        recipient_account=recipient_account,
        client_id=client_id,
    )


def _status_for(result: ScoringResult, *, after_answer: bool) -> TransferStatus:
    if result.risk_level == RiskLevel.HIGH:
        return TransferStatus.TRUSTED_PENDING
    if result.risk_level == RiskLevel.MEDIUM and not after_answer:
        return TransferStatus.AWAITING_ANSWER
    # MEDIUM after an answer means the client already paid the friction: let it through.
    return TransferStatus.COMPLETED


def _alert_texts(
    ctx: TransactionContext,
    result: ScoringResult,
) -> tuple[str | None, str | None]:
    if result.risk_level != RiskLevel.HIGH:
        return result.explanation, None
    ru = RulesEngine.generate_trusted_alert(
        ctx, result.risk_score, result.triggered_rules, result.signals, lang="ru"
    )
    kz = RulesEngine.generate_trusted_alert(
        ctx, result.risk_score, result.triggered_rules, result.signals, lang="kz"
    )
    return f"{ru.title}. {ru.danger_summary}", f"{kz.title}. {kz.danger_summary}"


def _track_timeout_task(task: asyncio.Task) -> None:
    _timeout_tasks.add(task)
    task.add_done_callback(_timeout_tasks.discard)


async def _timeout_after(transfer_id: str, timeout_seconds: int) -> None:
    await asyncio.sleep(timeout_seconds)
    db = SessionLocal()
    try:
        rec = db.query(TransferRecord).filter(TransferRecord.transfer_id == transfer_id).first()
        if not rec or rec.status != TransferStatus.TRUSTED_PENDING.value:
            return
        rec.status = TransferStateMachine.transition(
            TransferStatus.TRUSTED_PENDING,
            TransferStatus.COOLING_OFF,
        ).value
        db.commit()
        db.refresh(rec)
        await event_bus.publish("trusted_timeout", record_to_response(rec).model_dump(mode="json"))
    finally:
        db.close()


def _schedule_timeout(transfer_id: str, timeout_seconds: int | None) -> None:
    if timeout_seconds and timeout_seconds > 0:
        _track_timeout_task(asyncio.create_task(_timeout_after(transfer_id, timeout_seconds)))


def record_to_response(rec: TransferRecord) -> TransferResponse:
    trusted = None
    if rec.trusted_contact_name:
        trusted = TrustedContactInfo(
            name=rec.trusted_contact_name,
            phone=rec.trusted_contact_phone or ""
        )
    return TransferResponse(
        transfer_id=rec.transfer_id,
        client_id=rec.client_id,
        recipient_account=rec.recipient_account,
        recipient_name=rec.recipient_name,
        amount=rec.amount,
        currency=rec.currency,
        status=TransferStatus(rec.status),
        risk_tier=RiskTier(rec.risk_tier),
        risk_score=rec.risk_score,
        challenge_question=rec.challenge_question,
        challenge_question_kz=rec.challenge_question_kz,
        trusted_contact=trusted,
        timeout_seconds=rec.timeout_seconds,
        detected_signals=rec.detected_signals or [],
        alert_reason_ru=rec.alert_reason_ru,
        alert_reason_kz=rec.alert_reason_kz,
        created_at=rec.created_at,
        updated_at=rec.updated_at
    )


@router.post("", response_model=TransferResponse, status_code=status.HTTP_201_CREATED)
async def create_transfer(
    payload: TransferCreate,
    db: Session = Depends(get_db)
):
    transfer_id = f"tr_{uuid.uuid4().hex[:8]}"

    ctx = _build_context(
        db,
        client_id=payload.client_id,
        amount=payload.amount,
        recipient_account=payload.recipient_account,
    )
    result = RulesEngine.evaluate_initial_transaction(ctx)
    current_status = _status_for(result, after_answer=False)
    alert_ru, alert_kz = _alert_texts(ctx, result)

    rec = TransferRecord(
        transfer_id=transfer_id,
        client_id=payload.client_id,
        recipient_account=payload.recipient_account,
        recipient_name=payload.recipient_name,
        amount=payload.amount,
        currency=payload.currency,
        status=current_status.value,
        risk_tier=RiskTier(result.risk_level.value).value,
        risk_score=int(round(result.risk_score)),
        challenge_question=QUESTION_RU if current_status == TransferStatus.AWAITING_ANSWER else None,
        challenge_question_kz=QUESTION_KZ if current_status == TransferStatus.AWAITING_ANSWER else None,
        trusted_contact_name=TRUSTED_CONTACT_NAME,
        trusted_contact_phone=TRUSTED_CONTACT_PHONE,
        timeout_seconds=TRUSTED_TIMEOUT_SECONDS if current_status == TransferStatus.TRUSTED_PENDING else None,
        detected_signals=result.triggered_rules,
        alert_reason_ru=alert_ru,
        alert_reason_kz=alert_kz,
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)

    resp = record_to_response(rec)
    if current_status == TransferStatus.TRUSTED_PENDING:
        _schedule_timeout(transfer_id, rec.timeout_seconds)
    await event_bus.publish("transfer_created", resp.model_dump(mode="json"))
    return resp


@router.get("/{transfer_id}", response_model=TransferResponse)
def get_transfer(
    transfer_id: str,
    db: Session = Depends(get_db)
):
    rec = db.query(TransferRecord).filter(TransferRecord.transfer_id == transfer_id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Transfer not found")
    return record_to_response(rec)


@router.post("/{transfer_id}/answer", response_model=TransferResponse)
async def submit_client_answer(
    transfer_id: str,
    payload: AnswerRequest,
    db: Session = Depends(get_db)
):
    rec = db.query(TransferRecord).filter(TransferRecord.transfer_id == transfer_id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Transfer not found")

    current_status = TransferStatus(rec.status)
    if current_status != TransferStatus.AWAITING_ANSWER:
        raise HTTPException(
            status_code=400,
            detail=f"Transfer is in status {current_status.value}, cannot submit answer"
        )

    rec.client_answer = payload.answer_text

    ctx = _build_context(
        db,
        client_id=rec.client_id,
        amount=rec.amount,
        recipient_account=rec.recipient_account,
    )
    # LLM parsing is blocking network I/O; keep it off the event loop.
    result = await run_in_threadpool(
        RulesEngine.evaluate_with_answer, ctx, payload.answer_text
    )
    target_status = _status_for(result, after_answer=True)

    try:
        new_status = TransferStateMachine.transition(current_status, target_status)
    except InvalidStateTransitionError as e:
        raise HTTPException(status_code=400, detail=str(e))

    rec.status = new_status.value
    rec.risk_tier = RiskTier(result.risk_level.value).value
    rec.risk_score = int(round(result.risk_score))
    rec.detected_signals = result.triggered_rules
    rec.alert_reason_ru, rec.alert_reason_kz = _alert_texts(ctx, result)
    if new_status == TransferStatus.TRUSTED_PENDING:
        rec.timeout_seconds = TRUSTED_TIMEOUT_SECONDS
        _schedule_timeout(transfer_id, rec.timeout_seconds)
    else:
        rec.timeout_seconds = None

    db.commit()
    db.refresh(rec)

    resp = record_to_response(rec)
    await event_bus.publish("transfer_updated", resp.model_dump(mode="json"))
    return resp


@router.post("/{transfer_id}/cancel", response_model=TransferResponse)
async def cancel_transfer(
    transfer_id: str,
    payload: CancelRequest = CancelRequest(),
    db: Session = Depends(get_db)
):
    rec = db.query(TransferRecord).filter(TransferRecord.transfer_id == transfer_id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Transfer not found")

    current_status = TransferStatus(rec.status)
    try:
        new_status = TransferStateMachine.transition(current_status, TransferStatus.CANCELLED)
    except InvalidStateTransitionError as e:
        raise HTTPException(status_code=400, detail=str(e))

    rec.status = new_status.value
    db.commit()
    db.refresh(rec)

    resp = record_to_response(rec)
    await event_bus.publish("transfer_cancelled", resp.model_dump(mode="json"))
    return resp


@router.get("/stream/events")
async def sse_stream(request: Request):
    queue = await event_bus.subscribe()

    async def event_generator():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    msg = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield {
                        "event": msg["event"],
                        "data": json.dumps(msg["data"], ensure_ascii=False)
                    }
                except asyncio.TimeoutError:
                    yield {"event": "ping", "data": "keep-alive"}
        finally:
            event_bus.unsubscribe(queue)

    return EventSourceResponse(event_generator())
