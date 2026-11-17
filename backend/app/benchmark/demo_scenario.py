"""
Qaqpan Anti-Fraud Guardian: End-to-End Live Demo Scenario (Step L.9).

Executes the complete unified hackathon presentation storyline in a single script:
1. Scammer-Trap Bot: Scammer tries to lure the elderly victim into transferring funds.
   The bot plays along in-character and extracts the scammer's card number.
2. Bank Analyst Decision: The incident appears on the analyst dashboard.
   The analyst inspects the dialogue excerpt and marks the recipient as CONFIRMED fraud.
3. Protected Client Transfer: A bank client tries to transfer money to this exact card.
   The Qaqpan risk engine cross-references the verified trap database:
   - Escalates risk to HIGH (score 99).
   - Enforces TRUSTED_PENDING status.
   - Generates bilingual explainable alerts for the family member.
4. Trusted Relative Intervention: The daughter inspects the alarm and DECLINES the transfer.
   - Status moves to BLOCKED.
   - Customer funds are safely protected!
"""

import asyncio
import json
import os
import sys
import time

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "../../../"))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from backend.app.db import SessionLocal, init_db, TrapRecipient
from backend.app.models.schemas import (
    TrapSessionCreate,
    TrapMessageCreate,
    RecipientDecisionRequest,
    RecipientDecision,
    TransferCreate,
    TrustedDecisionRequest,
    DecisionType,
    RiskTier,
    TransferStatus,
)
from backend.app.api.trap import (
    create_session,
    post_message,
    decide_recipient,
    stop_session,
    stop_trap_tasks,
)
from backend.app.api.analyst import get_analyst_feed
from backend.app.api.transfers import create_transfer, stop_timeout_tasks
from backend.app.api.trusted import submit_trusted_decision


def banner(title: str):
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


async def run_live_demo():
    init_db()
    scammer_card = "4400430123456789"

    with SessionLocal() as db:
        # Clean previous demo artifacts for this card
        db.query(TrapRecipient).filter(TrapRecipient.value == scammer_card).delete()
        db.commit()

        # -------------------------------------------------------------
        # ACT 1: Scammer Trap in Action
        # -------------------------------------------------------------
        banner("АКТ 1: ДИАЛОГ С БОТОМ-ЛОВУШКОЙ (ПЕРСОНА БАБУШКИ)")
        s_resp = await create_session(TrapSessionCreate(language="ru"), db)
        session_id = s_resp.session_id
        print(f"[1.1] Сессия ловушки создана: {session_id} (Язык: RU)")

        scammer_msg = (
            "Здравствуйте! Это капитан юстиции Сабиров. Ваши счета под угрозой ареста. "
            f"Срочно переведите сбережения на резервную безопасную карту {scammer_card}!"
        )
        print(f"[1.2] Мошенник пишет:\n      «{scammer_msg}»")

        msg_resp = await post_message(session_id, TrapMessageCreate(text=scammer_msg), db)
        bot_reply = msg_resp.messages[-1].text
        print(f"[1.3] Бабушка-бот отвечает:\n      «{bot_reply}»")

        extracted_cards = [r for r in msg_resp.recipients if r.value == scammer_card]
        assert len(extracted_cards) > 0, "Card extraction failed"
        trap_recipient = extracted_cards[0]
        print(f"[1.4] Экстрактор перехватил реквизит:\n      Тип: {trap_recipient.recipient_type} | Номер: {trap_recipient.value} | Статус: {trap_recipient.status.value}")

        # -------------------------------------------------------------
        # ACT 2: Analyst Review Dashboard
        # -------------------------------------------------------------
        banner("АКТ 2: КАБИНЕТ АНАЛИТИКА БАНКА (ВЕРИФИКАЦИЯ РЕКВИЗИТА)")
        feed = get_analyst_feed(source="TRAP", limit=5, db=db)
        card = next(c for c in feed.cards if c.session_id == session_id)
        print(f"[2.1] Карточка инцидента в ленте аналитика:\n      Источник: {card.source} | Подозреваемый счёт: {card.recipient_account}")
        print(f"      Выдержка диалога: {card.dialogue_excerpt[-1]}")

        # Analyst confirms the scam card
        dec_resp = await decide_recipient(
            trap_recipient.id,
            RecipientDecisionRequest(
                decision=RecipientDecision.CONFIRMED,
                comment="Подтверждённый номер карты мошенника из ловушки"
            ),
            db
        )
        print(f"[2.2] Решение аналитика сохранено:\n      Статус реквизита: {dec_resp.status.value} (Подтверждён мошеннический счёт)")

        # -------------------------------------------------------------
        # ACT 3: Protected Transfer Attempt
        # -------------------------------------------------------------
        banner("АКТ 3: ПОПЫТКА ПЕРЕВОДА КЛИЕНТОМ БАНКА (ЗАЩИТА «ҚАҚПАН»)")
        print(f"[3.1] Клиент банка (бабушка) оформляет перевод 120 000 ₸ на карту {scammer_card}...")
        transfer = await create_transfer(
            TransferCreate(
                client_id="client_grandma_01",
                recipient_account=scammer_card,
                recipient_name="Лже-капитан Сабиров",
                amount=120000.0,
                currency="KZT",
                language="ru"
            ),
            db
        )
        print(f"[3.2] Результат мгновенного скоринга:")
        print(f"      Уровень риска:   {transfer.risk_tier.value}")
        print(f"      Risk Score:      {transfer.risk_score} / 100")
        print(f"      Статус перевода: {transfer.status.value}")
        print(f"      Сигналы защиты:  {transfer.detected_signals}")
        print(f"      Алерт для семьи:\n      «{transfer.alert_reason_ru}»")

        assert transfer.risk_tier == RiskTier.HIGH
        assert transfer.status == TransferStatus.TRUSTED_PENDING
        assert "CONFIRMED_TRAP_SCAMMER_RECIPIENT" in transfer.detected_signals

        # -------------------------------------------------------------
        # ACT 4: Trusted Person Intervention
        # -------------------------------------------------------------
        banner("АКТ 4: ВМЕШАТЕЛЬСТВО БЛИЗКОГО (ДОЧЬ ОСТАНАВЛИВАЕТ ПЕРЕВОД)")
        print(f"[4.1] Дочь Айгерим получает тревожный пуш в приложении и нажимает «ОТКЛОНИТЬ»...")
        dec_result = await submit_trusted_decision(
            transfer.transfer_id,
            TrustedDecisionRequest(
                trusted_user_id="trusted_daughter_44",
                decision=DecisionType.DECLINE,
                comment="Мама, не переводи, это мошенники! Я звоню в банк."
            ),
            db
        )
        print(f"[4.2] Итоговый статус перевода: {dec_result.status.value}")
        print(f"[4.3] РЕЗУЛЬТАТ: 120 000 ₸ клиента ЦентраКредит УСПЕШНО СПАСЕНЫ ОТ КРАЖИ! 🛡️")

        assert dec_result.status == TransferStatus.BLOCKED

        # Cleanup tasks
        await stop_trap_tasks()
        await stop_timeout_tasks()

    banner("ДЕМОНСТРАЦИОННЫЙ СЦЕНАРИЙ УСПЕШНО ПРОЙДЕН (ШАГ Л.9 ВЫПОЛНЕН) ✅")


if __name__ == "__main__":
    asyncio.run(run_live_demo())
