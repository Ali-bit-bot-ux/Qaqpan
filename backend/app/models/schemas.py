from enum import Enum
from typing import List, Literal, Optional
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class RiskTier(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class TransferStatus(str, Enum):
    SUBMITTED = "SUBMITTED"
    EVALUATING = "EVALUATING"
    AWAITING_ANSWER = "AWAITING_ANSWER"
    TRUSTED_PENDING = "TRUSTED_PENDING"
    COOLING_OFF = "COOLING_OFF"
    MANUAL_BANK_REVIEW = "MANUAL_BANK_REVIEW"
    COMPLETED = "COMPLETED"
    BLOCKED = "BLOCKED"
    CANCELLED = "CANCELLED"


# --- Transfer Schemas ---

class TransferCreate(BaseModel):
    client_id: str = Field(..., description="Unique client identifier, e.g. usr_kz_1001")
    recipient_account: str = Field(..., description="IBAN or Card number, e.g. KZ888561000293847291")
    recipient_name: str = Field(..., description="Full name of recipient, e.g. Ержан С.")
    amount: float = Field(..., gt=0, description="Amount in KZT, must be positive")
    currency: str = Field(default="KZT", description="Currency code (KZT)")
    language: str = Field(default="ru", description="Client language: 'ru' or 'kz'")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "client_id": "usr_kz_1001",
                "recipient_account": "KZ888561000293847291",
                "recipient_name": "Ержан С.",
                "amount": 250000.0,
                "currency": "KZT",
                "language": "ru"
            }
        }
    )


class TrustedContactInfo(BaseModel):
    name: str = Field(..., description="Name and relation, e.g. Айгерим (Дочь)")
    phone: str = Field(..., description="Masked phone number, e.g. +7 701 *** ** 44")


class TransferResponse(BaseModel):
    transfer_id: str
    client_id: str
    recipient_account: str
    recipient_name: str
    amount: float
    currency: str
    status: TransferStatus
    risk_tier: RiskTier
    risk_score: int = Field(default=0, ge=0, le=100)
    challenge_question: Optional[str] = None
    challenge_question_kz: Optional[str] = None
    trusted_contact: Optional[TrustedContactInfo] = None
    timeout_seconds: Optional[int] = None
    detected_signals: List[str] = Field(default_factory=list)
    alert_reason_ru: Optional[str] = None
    alert_reason_kz: Optional[str] = None
    cooling_warning_ru: Optional[str] = None
    cooling_warning_kz: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# --- Client Challenge Answer Schemas ---

class AnswerRequest(BaseModel):
    answer_text: str = Field(..., min_length=1, description="Client explanation response text")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "answer_text": "Мне позвонил сотрудник службы безопасности банка и сказал перевести на безопасный счет"
            }
        }
    )


# --- Trusted Decision Schemas ---

class DecisionType(str, Enum):
    APPROVE = "APPROVE"
    DECLINE = "DECLINE"


class TrustedDecisionRequest(BaseModel):
    trusted_user_id: str = Field(..., description="ID of trusted contact")
    decision: DecisionType = Field(..., description="APPROVE or DECLINE")
    comment: Optional[str] = Field(None, description="Optional explanation note")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "trusted_user_id": "usr_kz_2002",
                "decision": "DECLINE",
                "comment": "Мама, не переводи, это мошенники!"
            }
        }
    )


# --- Client Self-Cancellation / Cooldown ---

class CancelRequest(BaseModel):
    reason: Optional[str] = Field(default="Отменено клиентом", description="Client cancellation note")


class ManualReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    warning_acknowledged: bool = Field(..., strict=True)


# --- Bank Analyst Schemas ---

class TrapSessionStatus(str, Enum):
    ACTIVE = "ACTIVE"
    STOPPED = "STOPPED"
    TIMEOUT = "TIMEOUT"


class TrapRecipientStatus(str, Enum):
    NEW = "NEW"
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"


class AnalystCard(BaseModel):
    transfer_id: str
    client_id: str
    amount: float
    recipient_name: str
    recipient_account: str
    status: TransferStatus | TrapSessionStatus
    risk_tier: Optional[RiskTier]
    risk_score: int = Field(..., description="Transfer risk score; 0 with null risk_tier means unscored trap")
    signals: List[str] = Field(default_factory=list)
    client_answer: Optional[str] = None
    explanation: Optional[str] = None
    created_at: datetime
    # Card source: "TRANSFER" (default, backward compatible) or "TRAP".
    source: Literal["TRANSFER", "TRAP"] = "TRANSFER"
    # Trap-card payload (None for transfer cards).
    recipient_value: Optional[str] = None
    recipient_quote: Optional[str] = None
    dialogue_excerpt: List[str] = Field(default_factory=list)
    session_id: Optional[str] = None


class AnalystFeedResponse(BaseModel):
    total_count: int
    cards: List[AnalystCard]


# --- Scammer Trap Schemas (bot plays a cautious elderly victim) ---

class TrapSessionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    language: Literal["ru", "kz"] = Field(default="ru", description="Dialogue language")


class TrapMessageCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(..., min_length=1, max_length=2000, pattern=r"\S", description="Scammer message text")


class TrapSessionStopRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: Optional[str] = Field(None, max_length=500, description="Optional stop reason (not persisted)")


class TrapSessionResponse(BaseModel):
    session_id: str
    status: TrapSessionStatus
    language: Literal["ru", "kz"]
    message_count: int
    max_messages: int
    expires_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class TrapMessageOut(BaseModel):
    id: int
    sender: Literal["SCAMMER", "BOT"]
    text: str
    created_at: datetime


class TrapRecipientOut(BaseModel):
    id: int
    session_id: str
    recipient_type: Literal["IBAN", "CARD", "PHONE"]
    value: str
    quote: str
    status: TrapRecipientStatus
    decision_comment: Optional[str] = None
    created_at: datetime
    decided_at: Optional[datetime] = None


class TrapSessionDetailResponse(TrapSessionResponse):
    messages: List[TrapMessageOut] = Field(default_factory=list)
    recipients: List[TrapRecipientOut] = Field(default_factory=list)


class RecipientDecision(str, Enum):
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"


class RecipientDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # Enum membership is validated strictly; JSON strings are accepted.
    decision: RecipientDecision = Field(..., description="CONFIRMED or REJECTED")
    comment: Optional[str] = Field(None, max_length=1000, description="Optional analyst note")


# --- Benchmark / Adversarial Robot Schemas ---

class BenchmarkSimulationRequest(BaseModel):
    scenarios_count: int = Field(default=500, ge=10, le=2000, description="Number of synthetic attacks to run")
    enable_adaptive_tuning: bool = Field(default=True, description="Run rule adaptation cycle after bypasses")


class BenchmarkMetrics(BaseModel):
    stop_rate_pct: float
    false_positive_pct: float
    friction_rate_pct: float
    avg_delay_seconds: float


class BenchmarkResult(BaseModel):
    total_scenarios: int
    baseline_metrics: BenchmarkMetrics
    qaqpan_before_metrics: BenchmarkMetrics
    qaqpan_after_metrics: BenchmarkMetrics
    bypasses_found: int
    bypasses_fixed: int
    status: str = "completed"

