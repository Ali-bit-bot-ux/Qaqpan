"""Tunable demo settings read from the environment (defaults keep current behaviour)."""
import logging
import os

logger = logging.getLogger("qaqpan.config")


def env_float(name: str, default: float) -> float:
    """Positive float from env; anything else falls back to the default."""
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError:
        value = 0.0
    if value <= 0:
        logger.warning("Ignoring invalid %s=%r, using default %s", name, raw, default)
        return default
    return value


def env_int(name: str, default: int) -> int:
    return int(env_float(name, float(default)))


# Seconds the trusted person has to answer (the idea suggests 15 min = 900; demo default is 30).
TRUSTED_TIMEOUT_SECONDS: int = env_int("TRUSTED_TIMEOUT_SECONDS", 30)
# Amount treated as "usual" for a client until per-client history is modelled.
CLIENT_TYPICAL_AMOUNT: float = env_float("CLIENT_TYPICAL_AMOUNT", 50000.0)
