"""Advance-fee style lures (customs fee, prize tax, entry fee, deposit before viewing, prepayment)."""
import pytest

from backend.app.core.fallback_rules import detect_payment_lure, fallback_parse
from backend.app.core.rules_engine import RiskLevel, RulesEngine, TransactionContext

SCAMS = [
    "Курьер написал, что посылка застряла на таможне, надо внести сбор, прислал номер карты в WhatsApp",
    "Мне сообщили о выигрыше в лотерею, для получения надо оплатить налог, перевожу организатору",
    "Предложили подработку удалённо, но сначала нужен вступительный взнос за обучение",
    "Нашла квартиру в объявлении, хозяин просит залог до просмотра, я там ещё не была",
    "Магазин в инстаграме просит полную предоплату, говорит акция только сегодня",
    "Познакомился в сети с девушкой из-за границы, она просит оплатить ей билет",
    "Заказал с сайта-однодневки, продавец ждёт перевод на карту, которую скинул в чате",
    "Курьер жөнелтім кеденде тұр деп, төлем салуды сұрады",
    "Лотереядан ұттың деп, салық төлеуді сұрады",
    "Жұмысқа алам деп, алдымен кіру жарнасын төлеуді сұрады",
    "Пәтерді әлі көрген жоқпын, иесі алдын ала залог салуды сұрады",
    "Желіде танысқан адам көмек сұрап, ақша аударуды өтінді",
]

LEGIT = [
    "Госпошлина за загранпаспорт в банке",
    "Предоплата за кухню по договору, образцы видела в салоне",
    "Оплата курсов английского для дочери, договор заключили",
    "Залог за аренду по договору, квартиру смотрела вместе с мужем",
    "Купила платье на маркетплейсе, оплата при получении через банк",
    "Выигрыш получила, перевожу часть подруге в подарок",
    "Познакомились с будущей свекровью, перевожу ей на подарок к юбилею",
    "Ағылшын тілі курсына шарт бойынша төлем",
    "Пәтер жалдауға кепілақы, пәтерді өзім көріп келдім",
    "Салық органына мүлік салығын төлеу",
]


@pytest.mark.parametrize("text", SCAMS)
def test_scam_wording_sets_payment_lure(text):
    assert detect_payment_lure(text) is True
    assert fallback_parse(text).payment_lure is True


@pytest.mark.parametrize("text", LEGIT)
def test_legit_wording_does_not_set_payment_lure(text):
    assert detect_payment_lure(text) is False
    assert fallback_parse(text).payment_lure is False


def test_lure_raises_risk_even_for_a_small_transfer():
    ctx = TransactionContext(amount=40000.0, is_new_recipient=True, transfer_hour=14)
    res = RulesEngine.evaluate_with_answer(ctx, SCAMS[0])
    assert res.risk_level == RiskLevel.HIGH
    assert any("предоплат" in r.lower() or "схем" in r.lower() for r in res.triggered_rules)


def test_lure_wording_is_kept_when_llm_result_lacks_it():
    """The LLM schema has no payment_lure field; the regex floor must still apply."""
    from backend.app.core import ai_parser

    original = ai_parser.call_gemini_api
    ai_parser.call_gemini_api = lambda *a, **k: {"urgency_score": 0.0, "explanation_summary": "x", "language": "ru"}
    import os

    old = os.environ.get("GEMINI_API_KEY")
    os.environ["GEMINI_API_KEY"] = "test-key"
    try:
        res = ai_parser.parse_client_answer(SCAMS[0])
    finally:
        ai_parser.call_gemini_api = original
        if old is None:
            os.environ.pop("GEMINI_API_KEY")
        else:
            os.environ["GEMINI_API_KEY"] = old
    assert res.source == "llm"
    assert res.payment_lure is True
