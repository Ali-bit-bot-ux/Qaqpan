import os
from typing import Generator
from dotenv import load_dotenv
from sqlalchemy import create_engine, String, Float, Integer, DateTime, Text, JSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker, Session
from datetime import datetime

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./qaqpan.db")
# If using asyncpg prefix, normalize for standard driver
if "sqlite+aiosqlite" in DATABASE_URL:
    DATABASE_URL = "sqlite:///./qaqpan.db"

connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    DATABASE_URL,
    echo=False,
    connect_args=connect_args
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


class TransferRecord(Base):
    __tablename__ = "transfers"

    transfer_id: Mapped[str] = mapped_column(String(64), primary_key=True, index=True)
    client_id: Mapped[str] = mapped_column(String(64), index=True)
    recipient_account: Mapped[str] = mapped_column(String(64))
    recipient_name: Mapped[str] = mapped_column(String(128))
    amount: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(8), default="KZT")
    status: Mapped[str] = mapped_column(String(32), default="SUBMITTED", index=True)
    risk_tier: Mapped[str] = mapped_column(String(16), default="LOW")
    risk_score: Mapped[int] = mapped_column(Integer, default=0)
    
    challenge_question: Mapped[str | None] = mapped_column(String(255), nullable=True)
    challenge_question_kz: Mapped[str | None] = mapped_column(String(255), nullable=True)
    client_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    trusted_contact_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    trusted_contact_phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    timeout_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    
    detected_signals: Mapped[list] = mapped_column(JSON, default=list)
    alert_reason_ru: Mapped[str | None] = mapped_column(Text, nullable=True)
    alert_reason_kz: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
