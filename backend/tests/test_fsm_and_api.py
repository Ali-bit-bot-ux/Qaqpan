import pytest
from backend.app.models.schemas import TransferStatus, RiskTier, TransferCreate, AnswerRequest, TrustedDecisionRequest, DecisionType
from backend.app.core.state_machine import TransferStateMachine, InvalidStateTransitionError
from backend.app.api.transfers import router as transfers_router
from backend.app.api.benchmark import router as benchmark_router


def test_fsm_valid_transitions():
    assert TransferStateMachine.transition(TransferStatus.SUBMITTED, TransferStatus.EVALUATING) == TransferStatus.EVALUATING
    assert TransferStateMachine.transition(TransferStatus.EVALUATING, TransferStatus.COMPLETED) == TransferStatus.COMPLETED
    assert TransferStateMachine.transition(TransferStatus.EVALUATING, TransferStatus.AWAITING_ANSWER) == TransferStatus.AWAITING_ANSWER
    assert TransferStateMachine.transition(TransferStatus.EVALUATING, TransferStatus.TRUSTED_PENDING) == TransferStatus.TRUSTED_PENDING
    assert TransferStateMachine.transition(TransferStatus.TRUSTED_PENDING, TransferStatus.COMPLETED) == TransferStatus.COMPLETED
    assert TransferStateMachine.transition(TransferStatus.TRUSTED_PENDING, TransferStatus.BLOCKED) == TransferStatus.BLOCKED
    assert TransferStateMachine.transition(TransferStatus.TRUSTED_PENDING, TransferStatus.COOLING_OFF) == TransferStatus.COOLING_OFF
    assert TransferStateMachine.transition(TransferStatus.COOLING_OFF, TransferStatus.CANCELLED) == TransferStatus.CANCELLED


def test_fsm_invalid_transitions():
    with pytest.raises(InvalidStateTransitionError):
        TransferStateMachine.transition(TransferStatus.SUBMITTED, TransferStatus.COMPLETED)

    with pytest.raises(InvalidStateTransitionError):
        TransferStateMachine.transition(TransferStatus.COMPLETED, TransferStatus.BLOCKED)

    with pytest.raises(InvalidStateTransitionError):
        TransferStateMachine.transition(TransferStatus.BLOCKED, TransferStatus.COMPLETED)


def test_schema_validations():
    # Valid transfer model
    t = TransferCreate(
        client_id="usr_kz_1001",
        recipient_account="KZ1234567890",
        recipient_name="Тест Т.",
        amount=50000.0,
        currency="KZT",
        language="ru"
    )
    assert t.amount == 50000.0

    # Negative amount should fail validation
    with pytest.raises(Exception):
        TransferCreate(
            client_id="usr_kz_1001",
            recipient_account="KZ1234567890",
            recipient_name="Тест Т.",
            amount=-100.0
        )
