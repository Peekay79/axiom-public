import datetime as dt
import logging
import math
import os

_log = logging.getLogger(__name__)


def _get_half_life_days() -> float:
    """Resolve canonical half-life days with legacy fallback and deprecation log.

    Canonical: AXIOM_DECAY_HALFLIFE_DAYS (default 90)
    Deprecated: AXIOM_DECAY_HALF_LIFE (days)
    """
    try:
        canon = os.getenv("AXIOM_DECAY_HALFLIFE_DAYS")
        if canon is not None and str(canon).strip() != "":
            return float(canon)
        legacy = os.getenv("AXIOM_DECAY_HALF_LIFE")
        if legacy is not None and str(legacy).strip() != "":
            try:
                _log.warning("[RECALL][Deprecation] AXIOM_DECAY_HALF_LIFE is deprecated; use AXIOM_DECAY_HALFLIFE_DAYS")
            except Exception:
                pass
            # Map into canonical for downstream readers in this process
            try:
                os.environ.setdefault("AXIOM_DECAY_HALFLIFE_DAYS", str(legacy))
            except Exception:
                pass
            return float(legacy)
        return 90.0
    except Exception:
        return 90.0


HALF_LIFE_DAYS = _get_half_life_days()


def decay(original_score: float, age: dt.timedelta) -> float:
    if original_score <= 0:
        return 0.0
    # Compute how many half-life periods have elapsed
    halves = age.total_seconds() / (HALF_LIFE_DAYS * 86400)
    return original_score * math.pow(0.5, halves)
