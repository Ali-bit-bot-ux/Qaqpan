from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..db import get_db, TransferRecord
from ..models.schemas import (
    TransferResponse,
    TransferStatus,
    TrustedDecisionRequest,
    DecisionType
)
from ..core.events import event_bus
from .transfers import commit_transition

router = APIRouter(prefix="/transfers", tags=["Trusted Contact"])


@router.post("/{transfer_id}/trusted-decision", response_model=TransferResponse)
async def submit_trusted_decision(
    transfer_id: str,
    payload: TrustedDecisionRequest,
    db: Session = Depends(get_db)
):
    rec = db.query(TransferRecord).filter(TransferRecord.transfer_id == transfer_id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Transfer not found")

    current_status = TransferStatus(rec.status)
    if current_status != TransferStatus.TRUSTED_PENDING:
        raise HTTPException(
            status_code=409,
            detail=f"Transfer is in status {current_status.value}, not waiting for trusted decision"
        )

    target_status = (
        TransferStatus.COMPLETED
        if payload.decision == DecisionType.APPROVE
        else TransferStatus.BLOCKED
    )

    resp = commit_transition(db, rec, target_status)
    if resp is None:
        raise HTTPException(status_code=409, detail="Transfer state changed")
    event_type = "trusted_approved" if payload.decision == DecisionType.APPROVE else "trusted_declined"
    await event_bus.publish(event_type, resp.model_dump(mode="json"))
    return resp


@router.post("/{transfer_id}/timeout", response_model=TransferResponse)
async def handle_trusted_timeout(
    transfer_id: str,
    db: Session = Depends(get_db)
):
    rec = db.query(TransferRecord).filter(TransferRecord.transfer_id == transfer_id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Transfer not found")

    current_status = TransferStatus(rec.status)
    if current_status != TransferStatus.TRUSTED_PENDING:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot trigger timeout for transfer in status {current_status.value}"
        )

    resp = commit_transition(db, rec, TransferStatus.COOLING_OFF, timeout=True)
    if resp is None:
        raise HTTPException(status_code=409, detail="Deadline has not elapsed or transfer state changed")
    await event_bus.publish("trusted_timeout", resp.model_dump(mode="json"))
    return resp
