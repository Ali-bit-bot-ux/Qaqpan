import uuid
import json
import re
import asyncio
import logging
from dataclasses import replace
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse
from starlette.concurrency import run_in_threadpool

from ..db import get_db, SessionLocal, TransferRecord, TrapRecipient
from ..models.schemas import (
    TransferCreate,
    TransferResponse,
    TransferStatus,
    RiskTier,
    AnswerRequest,
    CancelRequest,
    ManualReviewRequest,
    TrustedContactInfo
)
from ..core.state_machine import TransferStateMachine, InvalidStateTransitionError
from ..core.events import event_bus
from ..core.rules_engine import RulesEngine, TransactionContext, RiskLevel, NextAction, ScoringResult

router = APIRouter(prefix="/transfers", tags=["Transfers (Client)"])
_timeout_tasks: dict[str, asyncio.Task[None]] = {}
logger = logging.getLogger("qaqpan.timers")

CLIENT_TYPICAL_AMOUNT = 50000.0
TRUSTED_TIMEOUT_SECONDS = 30
QUESTION_RU = "Для чего вы совершаете данный перевод?"
QUESTION_KZ = "Бұл аударымды не үшін жасап жатырсыз?"
TRUSTED_CONTACT_NAME = "Айгерим (Дочь)"
TRUSTED_CONTACT_PHONE = "+7 701 *** ** 44"
COOLING_WARNING_RU = (
    "Близкий не ответил. Перевод не выполнен. Не переводите деньги по указанию незнакомых людей. "
    "Вы можете отменить перевод или запросить проверку банка. Запрос проверки не выполняет перевод."
)
COOLING_WARNING_KZ = (
    "Жақыныңыз жауап бермеді. Аударым орындалған жоқ. Бейтаныс адамдардың нұсқауымен ақша аудармаңыз. "
    "Аударымнан бас тартуға немесе банктің тексеруін сұрауға болады. Тексеру сұрауы аударымды орындамайды."
)


def _build_context(
    db: Session,
    client_id: str,
    amount: float,
    recipient_account: str,
    current_transfer_id: str | None = None,
) -> TransactionContext:
    since = datetime.utcnow() - timedelta(hours=1)
    recent_query = db.query(TransferRecord).filter(
        TransferRecord.client_id == client_id,
        TransferRecord.created_at >= since,
    )
    if current_transfer_id is not None:
        recent_query = recent_query.filter(TransferRecord.transfer_id != current_transfer_id)
    recent_count = recent_query.count()
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


def _status_for(result: ScoringResult) -> TransferStatus:
    if result.action == NextAction.ALLOW:
        return TransferStatus.COMPLETED
    if result.action == NextAction.ASK_QUESTION:
        return TransferStatus.AWAITING_ANSWER
    if result.action == NextAction.REQUIRE_TRUSTED_APPROVAL:
        return TransferStatus.TRUSTED_PENDING
    raise HTTPException(status_code=502, detail="Unsupported scoring action")


def _alert_texts(
    ctx: TransactionContext,
    result: ScoringResult,
) -> tuple[str | None, str | None]:
    if result.risk_level != RiskLevel.HIGH:
        return result.explanation, None
    # The renderer also infers language from signals; override only a copy.
    ru = RulesEngine.generate_trusted_alert(
        ctx, result.risk_score, result.triggered_rules,
        replace(result.signals, language="ru") if result.signals is not None else None,
        lang="ru",
    )
    kz = RulesEngine.generate_trusted_alert(
        ctx, result.risk_score, result.triggered_rules,
        replace(result.signals, language="kz") if result.signals is not None else None,
        lang="kz",
    )
    return (
        "\n".join([
            f"{ru.title}. {ru.danger_summary}",
            *(f"- {bullet}" for bullet in ru.evidence_bullets),
            ru.recommended_action,
        ]),
        "\n".join([
            f"{kz.title}. {kz.danger_summary}",
            *(f"- {bullet}" for bullet in kz.evidence_bullets),
            kz.recommended_action,
        ]),
    )


def trusted_deadline(rec: TransferRecord) -> datetime:
    # Legacy pending rows without a duration retain the same 30-second policy.
    seconds = rec.timeout_seconds if rec.timeout_seconds is not None else TRUSTED_TIMEOUT_SECONDS
    return rec.updated_at + timedelta(seconds=seconds)


def commit_transition(
    db: Session,
    rec: TransferRecord,
    target: TransferStatus,
    *,
    timeout: bool = False,
) -> TransferResponse | None:
    """Compare-and-set; snapshot our write before commit so later writes cannot leak into its event."""
    current = TransferStatus(rec.status)
    TransferStateMachine.transition(current, target)
    query = db.query(TransferRecord).filter(
        TransferRecord.transfer_id == rec.transfer_id,
        TransferRecord.status == current.value,
    )
    if timeout:
        if trusted_deadline(rec) > datetime.utcnow():
            return None
        # Guard the exact persisted deadline checked above, not just the status.
        query = query.filter(
            TransferRecord.updated_at == rec.updated_at,
            TransferRecord.timeout_seconds == rec.timeout_seconds,
        )
    updated = query.update({
        TransferRecord.status: target.value,
        TransferRecord.timeout_seconds: None,
        TransferRecord.updated_at: datetime.utcnow(),
    }, synchronize_session=False)
    if updated != 1:
        db.rollback()
        return None
    db.refresh(rec)
    response = record_to_response(rec)
    db.commit()
    return response


async def _timeout_after(transfer_id: str) -> None:
    while True:
        response = None
        with SessionLocal() as db:
            rec = db.get(TransferRecord, transfer_id)
            if rec is None or rec.status != TransferStatus.TRUSTED_PENDING.value:
                return
            remaining = (trusted_deadline(rec) - datetime.utcnow()).total_seconds()
            if remaining <= 0:
                response = commit_transition(db, rec, TransferStatus.COOLING_OFF, timeout=True)
        # Never retain a session/transaction while sleeping or publishing.
        if remaining > 0:
            await asyncio.sleep(remaining)
            continue
        if response is not None:
            await event_bus.publish("trusted_timeout", response.model_dump(mode="json"))
        return


def _schedule_timeout(transfer_id: str) -> None:
    existing = _timeout_tasks.get(transfer_id)
    if existing is not None and not existing.done():
        return
    task = asyncio.create_task(_timeout_after(transfer_id))
    _timeout_tasks[transfer_id] = task

    def finished(done: asyncio.Task[None]) -> None:
        if _timeout_tasks.get(transfer_id) is done:
            _timeout_tasks.pop(transfer_id)
        if not done.cancelled() and done.exception() is not None:
            logger.error("Trusted timer failed for %s", transfer_id, exc_info=done.exception())

    task.add_done_callback(finished)


def recover_pending_timeouts() -> None:
    with SessionLocal() as db:
        pending_ids = db.query(TransferRecord.transfer_id).filter(
            TransferRecord.status == TransferStatus.TRUSTED_PENDING.value,
        ).all()
    for (transfer_id,) in pending_ids:
        _schedule_timeout(transfer_id)


async def stop_timeout_tasks() -> None:
    tasks = list(_timeout_tasks.values())
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    _timeout_tasks.clear()


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
        timeout_seconds=rec.timeout_seconds if rec.status == TransferStatus.TRUSTED_PENDING.value else None,
        detected_signals=rec.detected_signals or [],
        alert_reason_ru=rec.alert_reason_ru,
        alert_reason_kz=rec.alert_reason_kz,
        cooling_warning_ru=COOLING_WARNING_RU if rec.status == TransferStatus.COOLING_OFF.value else None,
        cooling_warning_kz=COOLING_WARNING_KZ if rec.status == TransferStatus.COOLING_OFF.value else None,
        created_at=rec.created_at,
        updated_at=rec.updated_at
    )


def _normalize_account_candidates(raw: str) -> list[str]:
    """Generate normalized search candidates for card, phone, or IBAN matching."""
    candidates = set()
    cleaned = re.sub(r"[\s-]+", "", raw.strip())
    if cleaned:
        candidates.add(cleaned)
        candidates.add(cleaned.upper())
    digits_only = re.sub(r"\D", "", raw)
    if digits_only:
        candidates.add(digits_only)
        if len(digits_only) == 11 and digits_only.startswith("8"):
            candidates.add("7" + digits_only[1:])
        elif len(digits_only) == 10:
            candidates.add("7" + digits_only)
    return list(candidates)


def _find_confirmed_trap_recipient(db: Session, recipient_account: str) -> TrapRecipient | None:
    candidates = _normalize_account_candidates(recipient_account)
    if not candidates:
        return None
    return (
        db.query(TrapRecipient)
        .filter(
            TrapRecipient.status == "CONFIRMED",
            TrapRecipient.value.in_(candidates),
        )
        .first()
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

    # Check against verified scammer database collected by trap bot (Step L.6)
    confirmed_scam = _find_confirmed_trap_recipient(db, payload.recipient_account)
    if confirmed_scam is not None:
        current_status = TransferStatus.TRUSTED_PENDING
        risk_tier = RiskTier.HIGH
        risk_score = 99
        timeout_seconds = TRUSTED_TIMEOUT_SECONDS
        signals = [
            "CONFIRMED_TRAP_SCAMMER_RECIPIENT",
            f"trap_session_{confirmed_scam.session_id}",
            f"recipient_type_{confirmed_scam.recipient_type}",
            *result.triggered_rules,
        ]
        alert_ru = (
            f"Внимание! Счёт получателя ({confirmed_scam.value}) совпадает с реквизитом мошенника, "
            f"выявленным ботом-ловушкой и подтверждённым аналитиком банка. "
            f"Перевод направлен на проверку доверенному лицу."
        )
        alert_kz = (
            f"Назар аударыңыз! Алушының шоты ({confirmed_scam.value}) банк аналитигі растаған "
            f"тұзақ-боты анықтаған алаяқтың реквизиттерімен сәйкес келеді. "
            f"Аударым сенімді тұлғаның тексеруіне бағытталды."
        )
    else:
        current_status = _status_for(result)
        risk_tier = RiskTier(result.risk_level.value)
        risk_score = int(round(result.risk_score))
        timeout_seconds = TRUSTED_TIMEOUT_SECONDS if current_status == TransferStatus.TRUSTED_PENDING else None
        signals = result.triggered_rules
        alert_ru, alert_kz = _alert_texts(ctx, result)

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
        challenge_question=QUESTION_RU if current_status == TransferStatus.AWAITING_ANSWER else None,
        challenge_question_kz=QUESTION_KZ if current_status == TransferStatus.AWAITING_ANSWER else None,
        trusted_contact_name=TRUSTED_CONTACT_NAME,
        trusted_contact_phone=TRUSTED_CONTACT_PHONE,
        timeout_seconds=timeout_seconds,
        detected_signals=signals,
        alert_reason_ru=alert_ru,
        alert_reason_kz=alert_kz,
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)

    resp = record_to_response(rec)
    if current_status == TransferStatus.TRUSTED_PENDING:
        _schedule_timeout(transfer_id)
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

    expected_updated_at = rec.updated_at
    ctx = _build_context(
        db,
        client_id=rec.client_id,
        amount=rec.amount,
        recipient_account=rec.recipient_account,
        current_transfer_id=transfer_id,
    )
    db.rollback()
    # LLM parsing is blocking network I/O; keep it off the event loop.
    result = await run_in_threadpool(
        RulesEngine.evaluate_with_answer, ctx, payload.answer_text
    )
    target_status = _status_for(result)

    new_status = current_status
    if target_status != current_status:
        try:
            new_status = TransferStateMachine.transition(current_status, target_status)
        except InvalidStateTransitionError as e:
            raise HTTPException(status_code=400, detail=str(e))

    alert_ru, alert_kz = _alert_texts(ctx, result)
    timeout_seconds = TRUSTED_TIMEOUT_SECONDS if new_status == TransferStatus.TRUSTED_PENDING else None
    updated = db.query(TransferRecord).filter(
        TransferRecord.transfer_id == transfer_id,
        TransferRecord.status == current_status.value,
        # A repeated question retains status but must still match the scored revision.
        TransferRecord.updated_at == expected_updated_at,
    ).update({
        TransferRecord.status: new_status.value,
        TransferRecord.client_answer: payload.answer_text,
        TransferRecord.risk_tier: RiskTier(result.risk_level.value).value,
        TransferRecord.risk_score: int(round(result.risk_score)),
        TransferRecord.detected_signals: result.triggered_rules,
        TransferRecord.alert_reason_ru: alert_ru,
        TransferRecord.alert_reason_kz: alert_kz,
        TransferRecord.timeout_seconds: timeout_seconds,
        # Pending deadline starts at this transition, never at transfer creation.
        TransferRecord.updated_at: datetime.utcnow(),
    }, synchronize_session=False)
    if updated != 1:
        db.rollback()
        raise HTTPException(status_code=409, detail="Transfer changed while evaluating the answer")

    db.refresh(rec)
    resp = record_to_response(rec)
    db.commit()
    if new_status == TransferStatus.TRUSTED_PENDING:
        _schedule_timeout(transfer_id)

    await event_bus.publish("transfer_updated", resp.model_dump(mode="json"))
    return resp


@router.post("/{transfer_id}/manual-review", response_model=TransferResponse)
async def request_manual_review(
    transfer_id: str,
    payload: ManualReviewRequest,
    db: Session = Depends(get_db),
) -> TransferResponse:
    if not payload.warning_acknowledged:
        raise HTTPException(status_code=400, detail="Acknowledge the cooling-off warning first")
    rec = db.get(TransferRecord, transfer_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="Transfer not found")
    if rec.status != TransferStatus.COOLING_OFF.value:
        raise HTTPException(status_code=409, detail="Transfer is not in cooling-off")
    target = TransferStateMachine.transition(
        TransferStatus.COOLING_OFF, TransferStatus.MANUAL_BANK_REVIEW,
    )
    updated = db.query(TransferRecord).filter(
        TransferRecord.transfer_id == transfer_id,
        TransferRecord.status == TransferStatus.COOLING_OFF.value,
    ).update({
        TransferRecord.status: target.value,
        TransferRecord.timeout_seconds: None,
    }, synchronize_session=False)
    if updated != 1:
        db.rollback()
        raise HTTPException(status_code=409, detail="Transfer state changed")
    db.refresh(rec)
    response = record_to_response(rec)
    db.commit()
    await event_bus.publish("transfer_updated", response.model_dump(mode="json"))
    return response


@router.post("/{transfer_id}/cancel", response_model=TransferResponse)
async def cancel_transfer(
    transfer_id: str,
    payload: CancelRequest = CancelRequest(),
    db: Session = Depends(get_db)
):
    rec = db.query(TransferRecord).filter(TransferRecord.transfer_id == transfer_id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Transfer not found")

    try:
        resp = commit_transition(db, rec, TransferStatus.CANCELLED)
    except InvalidStateTransitionError as e:
        raise HTTPException(status_code=409, detail=str(e))
    if resp is None:
        raise HTTPException(status_code=409, detail="Transfer state changed")

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
