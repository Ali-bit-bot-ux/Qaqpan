import pytest

from backend.app.config import env_float, env_int


def test_defaults_when_unset(monkeypatch):
    monkeypatch.delenv("QAQPAN_X", raising=False)
    assert env_int("QAQPAN_X", 30) == 30
    assert env_float("QAQPAN_X", 5.0) == 5.0


def test_reads_valid_value(monkeypatch):
    monkeypatch.setenv("QAQPAN_X", "900")
    assert env_int("QAQPAN_X", 30) == 900


@pytest.mark.parametrize("bad", ["abc", "", "-5", "0"])
def test_invalid_value_falls_back_to_default(monkeypatch, bad):
    monkeypatch.setenv("QAQPAN_X", bad)
    assert env_int("QAQPAN_X", 30) == 30
    assert env_float("QAQPAN_X", 5.0) == 5.0
