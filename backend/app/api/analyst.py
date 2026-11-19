from typing import List, Literal, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from ..db import get_db, TransferRecord, TrapSession, TrapMessage, TrapRecipient
from ..core.events import event_bus
from ..models.schemas import (
    AnalystFeedResponse, AnalystCard, AnalystSummary, TransferStatus, RiskTier,
    BankReviewDecisionRequest, DecisionType, TransferResponse,
)
from .transfers import commit_transition

router = APIRouter(prefix="/analyst", tags=["Bank Analyst"])

# Trap card constants (no risk wiring into rules yet — MVP shows the card only).
TRAP_SOURCE = "TRAP"
TRANSFER_SOURCE = "TRANSFER"
DIALOGUE_EXCERPT_MESSAGES = 4


def _transfer_card(r: TransferRecord) -> AnalystCard:
    return AnalystCard(
        transfer_id=r.transfer_id,
        client_id=r.client_id,
        amount=r.amount,
        recipient_name=r.recipient_name,
        recipient_account=r.recipient_account,
        status=TransferStatus(r.status).value,
        risk_tier=RiskTier(r.risk_tier),
        risk_score=r.risk_score,
        signals=r.detected_signals or [],
        client_answer=r.client_answer,
        explanation=r.alert_reason_ru,
        created_at=r.created_at,
        source=TRANSFER_SOURCE,
    )


def _trap_card(db: Session, s: TrapSession) -> AnalystCard:
    # First pending or analyst-confirmed recipient is shown on the card.
    recipient = (
        db.query(TrapRecipient)
        .filter(
            TrapRecipient.session_id == s.session_id,
            TrapRecipient.status.in_(["NEW", "CONFIRMED"]),
        )
        .order_by(TrapRecipient.id)
        .first()
    )
    messages = (
        db.query(TrapMessage)
        .filter(TrapMessage.session_id == s.session_id)
        .order_by(desc(TrapMessage.id))
        .limit(DIALOGUE_EXCERPT_MESSAGES)
        .all()
    )
    excerpt = [m.text for m in reversed(messages)]
    return AnalystCard(
        transfer_id=s.session_id,  # feed key; trap cards are identified by session_id
        client_id="trap_simulator",
        amount=0.0,
        recipient_name="Подозреваемый (диалог-ловушка)",
        recipient_account=recipient.value if recipient else "",
        status=s.status,
        risk_tier=None,
        risk_score=0,  # Unscored; not a LOW-risk transfer.
        signals=["TRAP_DIALOGUE"],
        client_answer=None,
        explanation="Кандидаты из тестового диалога: банк, владелец и контрольная сумма IBAN не проверены; риск не оценён. Требуется проверка аналитика.",
        created_at=s.created_at,
        source=TRAP_SOURCE,
        recipient_value=recipient.value if recipient else None,
        recipient_quote=recipient.quote if recipient else None,
        dialogue_excerpt=excerpt,
        session_id=s.session_id,
    )


def _summary(db: Session) -> AnalystSummary:
    """Counts over every transfer record, zero-filled so the UI never needs defaults."""
    by_tier = {t.value: 0 for t in RiskTier}
    by_status = {s.value: 0 for s in TransferStatus}
    for tier, count in db.query(TransferRecord.risk_tier, func.count()).group_by(TransferRecord.risk_tier):
        by_tier[tier] = by_tier.get(tier, 0) + count
    for status_value, count in db.query(TransferRecord.status, func.count()).group_by(TransferRecord.status):
        by_status[status_value] = by_status.get(status_value, 0) + count
    return AnalystSummary(total_transfers=sum(by_status.values()), by_risk_tier=by_tier, by_status=by_status)


@router.get("/feed", response_model=AnalystFeedResponse)
def get_analyst_feed(
    risk_tier: Optional[RiskTier] = Query(None, description="Filter by risk tier (transfer cards only)"),
    status: Optional[TransferStatus] = Query(None, description="Filter by transfer status (transfer cards only)"),
    source: Literal["TRANSFER", "TRAP", "ALL"] = Query("ALL", description="Filter by card source"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    cards: List[AnalystCard] = []

    if source in (TRANSFER_SOURCE, "ALL"):
        query = db.query(TransferRecord).order_by(desc(TransferRecord.created_at))
        if isinstance(risk_tier, (RiskTier, str)):
            val = risk_tier.value if isinstance(risk_tier, RiskTier) else risk_tier
            query = query.filter(TransferRecord.risk_tier == val)
        if isinstance(status, (TransferStatus, str)):
            val = status.value if isinstance(status, TransferStatus) else status
            query = query.filter(TransferRecord.status == val)
        for r in query.limit(limit).all():
            cards.append(_transfer_card(r))

    # Transfer filters must not be polluted by unrelated, unscored trap cards.
    has_transfer_filter = isinstance(risk_tier, (RiskTier, str)) or isinstance(status, (TransferStatus, str))
    if source in (TRAP_SOURCE, "ALL") and not has_transfer_filter:
        sessions = (
            db.query(TrapSession)
            .order_by(desc(TrapSession.created_at))
            .limit(limit)
            .all()
        )
        for s in sessions:
            cards.append(_trap_card(db, s))

    # Merge newest-first and cut AFTER the merge, not per source.
    cards.sort(key=lambda c: c.created_at, reverse=True)
    cards = cards[:limit]

    return AnalystFeedResponse(total_count=len(cards), cards=cards, summary=_summary(db))


@router.post("/transfers/{transfer_id}/review", response_model=TransferResponse)
async def decide_manual_review(
    transfer_id: str,
    payload: BankReviewDecisionRequest,
    db: Session = Depends(get_db),
) -> TransferResponse:
    """Resolve MANUAL_BANK_REVIEW: APPROVE -> COMPLETED, DECLINE -> BLOCKED."""
    rec = db.get(TransferRecord, transfer_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="Transfer not found")
    if rec.status != TransferStatus.MANUAL_BANK_REVIEW.value:
        raise HTTPException(status_code=409, detail="Transfer is not in manual bank review")
    target = TransferStatus.COMPLETED if payload.decision == DecisionType.APPROVE else TransferStatus.BLOCKED
    resp = commit_transition(db, rec, target)
    if resp is None:
        raise HTTPException(status_code=409, detail="Transfer state changed")
    await event_bus.publish("bank_review_decided", resp.model_dump(mode="json"))
    return resp
