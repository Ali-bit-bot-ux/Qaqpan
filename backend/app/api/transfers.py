import uuid
import json
import asyncio
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from ..db import get_db, TransferRecord
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

router = APIRouter(prefix="/transfers", tags=["Transfers (Client)"])


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

    if payload.amount < 50000:
        current_status = TransferStatus.COMPLETED
        risk_tier = RiskTier.LOW
        risk_score = 10
        question_ru = None
        question_kz = None
    elif payload.amount < 300000:
        current_status = TransferStatus.AWAITING_ANSWER
        risk_tier = RiskTier.MEDIUM
        risk_score = 55
        question_ru = "Для чего вы совершаете данный перевод?"
        question_kz = "Бұл аударымды не үшін жасап жатырсыз?"
    else:
        current_status = TransferStatus.TRUSTED_PENDING
        risk_tier = RiskTier.HIGH
        risk_score = 88
        question_ru = None
        question_kz = None

    rec = TransferRecord(
        transfer_id=transfer_id,
        client_id=payload.client_id,
        recipient_account=payload.recipient_account,
        recipient_name=payload.recipient_name,
        amount=payload.amount,
        currency=payload.currency,
        status=current_status.value,
        risk_tier=risk_tier.value,
        risk_score=risk_score,
        challenge_question=question_ru,
        challenge_question_kz=question_kz,
        trusted_contact_name="Айгерим (Дочь)",
        trusted_contact_phone="+7 701 *** ** 44",
        timeout_seconds=30 if current_status == TransferStatus.TRUSTED_PENDING else None,
        detected_signals=["unusual_amount_threshold"] if payload.amount >= 50000 else [],
        alert_reason_ru="Сумма превышает стандартный лимит клиента" if payload.amount >= 300000 else None,
        alert_reason_kz="Сома клиенттің стандартты лимитінен асады" if payload.amount >= 300000 else None,
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)

    resp = record_to_response(rec)
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
    
    text_lower = payload.answer_text.lower()
    is_suspicious = any(w in text_lower for w in [
        "безопасн", "сотрудник", "банк", "полици", "кнб", "срочно", "қауіпсіз", "шұғыл"
    ])

    try:
        if is_suspicious:
            new_status = TransferStateMachine.transition(current_status, TransferStatus.TRUSTED_PENDING)
            rec.status = new_status.value
            rec.risk_tier = RiskTier.HIGH.value
            rec.risk_score = 94
            rec.detected_signals = ["safe_account_keyword", "bank_impersonation", "psychological_pressure"]
            rec.alert_reason_ru = "Клиент сообщает о звонке из службы безопасности и переводе на «безопасный счет»"
            rec.alert_reason_kz = "Клиент қауіпсіздік қызметінен қоңырау түскенін және «қауіпсіз шотқа» аударуды хабарлайды"
            rec.timeout_seconds = 30
        else:
            new_status = TransferStateMachine.transition(current_status, TransferStatus.COMPLETED)
            rec.status = new_status.value
            rec.risk_tier = RiskTier.LOW.value
            rec.risk_score = 20
    except InvalidStateTransitionError as e:
        raise HTTPException(status_code=400, detail=str(e))

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
