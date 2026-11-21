"""Prime an empty local simulator database with an operation for the demo household."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from .api.transfers import TRUSTED_CONTACT_NAME, TRUSTED_CONTACT_PHONE
from .db import SessionLocal, TransferRecord, init_db
from .models.schemas import RiskTier, TransferStatus


def seed_demo() -> None:
    init_db()
    with SessionLocal() as db:
        if db.scalar(select(TransferRecord.transfer_id).limit(1)) is not None:
            return
        yesterday = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=1)
        db.add(TransferRecord(
            transfer_id="seed-saule-arman",
            client_id="demo-client",
            recipient_account="KZ000000000000000102",
            recipient_name="Арман",
            amount=5000,
            currency="KZT",
            status=TransferStatus.COMPLETED.value,
            risk_tier=RiskTier.LOW.value,
            risk_score=0,
            trusted_contact_name=TRUSTED_CONTACT_NAME,
            trusted_contact_phone=TRUSTED_CONTACT_PHONE,
            created_at=yesterday,
            updated_at=yesterday,
        ))
        db.commit()


if __name__ == "__main__":
    seed_demo()
