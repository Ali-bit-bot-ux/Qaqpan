"""Tunable demo settings read from the environment (defaults keep current behaviour)."""
import json
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
# Amount treated as "usual" for a client with too little history (see TYPICAL_AMOUNT_MIN_SAMPLES).
CLIENT_TYPICAL_AMOUNT: float = env_float("CLIENT_TYPICAL_AMOUNT", 50000.0)
# Typical amount = median of the client's last completed LOW-risk transfers, once there are enough.
TYPICAL_AMOUNT_MIN_SAMPLES: int = env_int("TYPICAL_AMOUNT_MIN_SAMPLES", 3)
TYPICAL_AMOUNT_HISTORY_LIMIT: int = env_int("TYPICAL_AMOUNT_HISTORY_LIMIT", 20)
# Cooling-off delay after the trusted person stays silent: the client may cancel or ask the bank
# at once, but can only confirm on their own after this many seconds (idea: minutes; demo: 30 s).
COOLING_PERIOD_SECONDS: int = env_int("COOLING_PERIOD_SECONDS", 30)
# Seconds the client has to answer the question before the transfer is cancelled.
ANSWER_TIMEOUT_SECONDS: int = env_int("ANSWER_TIMEOUT_SECONDS", 300)


def parse_cors_origins() -> list[str]:
    """CORS_ORIGINS as a JSON list or a comma-separated string; '*' when unset or invalid."""
    raw = os.getenv("CORS_ORIGINS")
    if not raw or not raw.strip():
        return ["*"]
    raw = raw.strip()
    if raw.startswith("["):
        try:
            parsed = json.loads(raw)
        except ValueError:
            logger.warning("Ignoring invalid CORS_ORIGINS=%r, allowing all origins", raw)
            return ["*"]
        origins = [str(o).strip() for o in parsed if str(o).strip()] if isinstance(parsed, list) else []
    else:
        origins = [o.strip() for o in raw.split(",") if o.strip()]
    return origins or ["*"]
