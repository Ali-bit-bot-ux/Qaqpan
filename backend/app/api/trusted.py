from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..db import get_db, TransferRecord
from ..models.schemas import (
    TransferResponse,
    TransferStatus,
    TrustedDecisionRequest,
    DecisionType
)
from ..core.state_machine import TransferStateMachine, InvalidStateTransitionError
from ..core.events import event_bus
from .transfers import record_to_response

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
            status_code=400,
            detail=f"Transfer is in status {current_status.value}, not waiting for trusted decision"
        )

    target_status = (
        TransferStatus.COMPLETED
        if payload.decision == DecisionType.APPROVE
        else TransferStatus.BLOCKED
    )

    try:
        new_status = TransferStateMachine.transition(current_status, target_status)
    except InvalidStateTransitionError as e:
        raise HTTPException(status_code=400, detail=str(e))

    rec.status = new_status.value
    db.commit()
    db.refresh(rec)

    resp = record_to_response(rec)
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
            status_code=400,
            detail=f"Cannot trigger timeout for transfer in status {current_status.value}"
        )

    new_status = TransferStateMachine.transition(current_status, TransferStatus.COOLING_OFF)
    rec.status = new_status.value
    db.commit()
    db.refresh(rec)

    resp = record_to_response(rec)
    await event_bus.publish("trusted_timeout", resp.model_dump(mode="json"))
    return resp
