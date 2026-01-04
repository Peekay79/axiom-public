from __future__ import annotations

import os


def _env_bool(name: str, default: bool = False) -> bool:
	val = os.getenv(name)
	if val is None:
		return bool(default)
	return str(val).strip().lower() in {"1", "true", "yes", "y"}


RESILIENCE_ENABLED = _env_bool("RESILIENCE_ENABLED", True)

__all__ = ["RESILIENCE_ENABLED"]

