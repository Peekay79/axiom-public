from contextlib import contextmanager
from datetime import datetime, timezone
import importlib


@contextmanager
def freeze_utc_now(iso_str=None):
    """Monkeypatch utils.time_utils.utc_now_iso to return a fixed ISO string."""
    mod = importlib.import_module("memory.utils.time_utils")
    orig = getattr(mod, "utc_now_iso", None)
    fixed = iso_str or datetime.now(timezone.utc).isoformat()

    def _fixed():
        return fixed

    setattr(mod, "utc_now_iso", _fixed)
    try:
        yield fixed
    finally:
        if orig is not None:
            setattr(mod, "utc_now_iso", orig)

