"""Words like 'lawyer', 'police', 'investment' are only suspicious in a scam context."""
import pytest

from backend.app.core.fallback_rules import fallback_parse


# --- legitimate mentions must stay quiet --------------------------------------------------
@pytest.mark.parametrize("text", [
    "Пополняю инвестиционный счет у брокера по договору",
    "Купила облигации через инвестиционную компанию",
    "Оплата услуг адвоката по семейному делу",
    "Госпошлина в полиции за получение справки о несудимости",
    "Заңгердің құжат дайындау қызметіне төлем",
    "Полиция жол айыппұлын төлеу үшін квитанция берді",
])
def test_legit_mentions_do_not_trigger(text):
    s = fallback_parse(text)
    assert s.safe_account_keyword is False
    assert s.authority_pressure is False


# --- the same words in a pressure context must still trigger -------------------------------
@pytest.mark.parametrize("text", [
    "Звонил адвокат и срочно велел перевести деньги для залога",
    "Из полиции позвонили, сказали переводить немедленно",
    "Заңгер қоңырау шалып, шұғыл аударыңыз деді",
])
def test_pressure_context_still_triggers_authority(text):
    assert fallback_parse(text).authority_pressure is True


@pytest.mark.parametrize("text", [
    "Инвестиции с гарантированной прибылью, менеджер велел вложить сегодня",
    "Инвестиционный консультант обещал дивиденды после перевода на кошелек",
    "Криптоплатформа обещает удвоить вложения, перевожу на их кошелек",
    "Инвестициялық қор өкілі қосымша табыс түседі деп аудартты",
])
def test_investment_lure_still_triggers(text):
    assert fallback_parse(text).safe_account_keyword is True


# --- strong authority words never need context --------------------------------------------
@pytest.mark.parametrize("text", [
    "Следователь приказал перевести",
    "Служба безопасности банка попросила",
    "Майор сказал",
])
def test_strong_authority_words_always_trigger(text):
    assert fallback_parse(text).authority_pressure is True
