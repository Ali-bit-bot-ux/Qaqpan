from typing import Optional, List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc

from ..db import get_db, TransferRecord
from ..models.schemas import AnalystFeedResponse, AnalystCard, TransferStatus, RiskTier

router = APIRouter(prefix="/analyst", tags=["Bank Analyst"])


@router.get("/feed", response_model=AnalystFeedResponse)
def get_analyst_feed(
    risk_tier: Optional[RiskTier] = Query(None, description="Filter by risk tier"),
    status: Optional[TransferStatus] = Query(None, description="Filter by transfer status"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    query = db.query(TransferRecord).order_by(desc(TransferRecord.created_at))
    if risk_tier:
        query = query.filter(TransferRecord.risk_tier == risk_tier.value)
    if status is not None:
        query = query.filter(TransferRecord.status == status.value)

    records = query.limit(limit).all()

    cards: List[AnalystCard] = []
    for r in records:
        cards.append(
            AnalystCard(
                transfer_id=r.transfer_id,
                client_id=r.client_id,
                amount=r.amount,
                recipient_name=r.recipient_name,
                recipient_account=r.recipient_account,
                status=TransferStatus(r.status),
                risk_tier=RiskTier(r.risk_tier),
                risk_score=r.risk_score,
                signals=r.detected_signals or [],
                client_answer=r.client_answer,
                explanation=r.alert_reason_ru,
                created_at=r.created_at
            )
        )

    return AnalystFeedResponse(total_count=len(cards), cards=cards)
