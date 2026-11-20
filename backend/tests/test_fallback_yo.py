"""The fallback parser must treat 'ё' and 'е' as the same letter."""
import pytest

from backend.app.core.fallback_rules import fallback_parse


@pytest.mark.parametrize("text", [
    "Мне позвонили из банка, сказали перевести на безопасный счёт, никому не говорить",
    "перевести на БЕЗОПАСНЫЙ СЧЁТ",
    "нужно на резервный счёт",
    "перевод на специальный счёт",
    "на транзитный счёт",
    "на страховой счёта",
    "перевести на безопасный счет",
])
def test_safe_account_detected_with_and_without_yo(text):
    assert fallback_parse(text).safe_account_keyword is True


@pytest.mark.parametrize("text", [
    "Оплата аренды квартиры за ноябрь",
    "Внуку на обеды в школе",
    "Купила в магазине счётчик воды",
])
def test_benign_text_not_flagged(text):
    assert fallback_parse(text).safe_account_keyword is False
