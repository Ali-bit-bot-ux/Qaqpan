import logging
from typing import Set, Dict
from ..models.schemas import TransferStatus

logger = logging.getLogger("qaqpan.fsm")


class InvalidStateTransitionError(Exception):
    def __init__(self, current_status: TransferStatus, target_status: TransferStatus):
        self.current_status = current_status
        self.target_status = target_status
        super().__init__(
            f"Invalid FSM state transition: Cannot move from {current_status.value} to {target_status.value}"
        )


class TransferStateMachine:
    """
    Finite State Machine for Transfer Lifecycle.
    Ensures that only valid transitions occur and preserves client autonomy.
    """

    ALLOWED_TRANSITIONS: Dict[TransferStatus, Set[TransferStatus]] = {
        TransferStatus.SUBMITTED: {
            TransferStatus.EVALUATING,
            TransferStatus.CANCELLED
        },
        TransferStatus.EVALUATING: {
            TransferStatus.COMPLETED,         # Low risk tier
            TransferStatus.AWAITING_ANSWER,   # Medium risk tier (challenge question)
            TransferStatus.TRUSTED_PENDING,   # High risk tier (escalated to trusted person)
            TransferStatus.CANCELLED
        },
        TransferStatus.AWAITING_ANSWER: {
            TransferStatus.EVALUATING,        # Re-evaluating after client provides text
            TransferStatus.COMPLETED,         # Answer is clean — approved directly
            TransferStatus.TRUSTED_PENDING,   # Answer triggers escalation to trusted person
            TransferStatus.BLOCKED,           # Answer triggers immediate block (extreme risk)
            TransferStatus.CANCELLED          # Client cancels at any point
        },
        TransferStatus.TRUSTED_PENDING: {
            TransferStatus.COMPLETED,         # Trusted person approves
            TransferStatus.BLOCKED,           # Trusted person declines (stops scam)
            TransferStatus.COOLING_OFF,       # Timeout (trusted person didn't answer in time)
            TransferStatus.CANCELLED          # Client cancels while waiting
        },
        TransferStatus.COOLING_OFF: {
            TransferStatus.CANCELLED,          # Client realizes risk and cancels
            TransferStatus.MANUAL_BANK_REVIEW, # Client insists after explicit warning
            TransferStatus.COMPLETED           # Authorized bank approval
        },
        TransferStatus.MANUAL_BANK_REVIEW: {
            TransferStatus.COMPLETED,
            TransferStatus.BLOCKED,
            TransferStatus.CANCELLED
        },
        # Terminal states:
        TransferStatus.COMPLETED: set(),
        TransferStatus.BLOCKED: set(),
        TransferStatus.CANCELLED: set(),
    }

    @classmethod
    def can_transition(cls, current: TransferStatus, target: TransferStatus) -> bool:
        allowed = cls.ALLOWED_TRANSITIONS.get(current, set())
        return target in allowed

    @classmethod
    def transition(cls, current: TransferStatus, target: TransferStatus) -> TransferStatus:
        if not cls.can_transition(current, target):
            logger.error(f"FSM Transition Rejected: {current} -> {target}")
            raise InvalidStateTransitionError(current, target)
        logger.info(f"FSM Transition Accepted: {current} -> {target}")
        return target

