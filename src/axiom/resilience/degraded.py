from __future__ import annotations

import os
from typing import Optional

from . import RESILIENCE_ENABLED


_FLAG = {"active": False}


def is_active() -> bool:
	return bool(_FLAG["active"]) and RESILIENCE_ENABLED


def activate() -> None:
	if not RESILIENCE_ENABLED:
		return
	if str(os.getenv("DEGRADED_READONLY_ENABLED", "true")).strip().lower() in {"1", "true", "yes", "y"}:
		_FLAG["active"] = True
		_try_report_degraded(True, None)


def deactivate() -> None:
	_FLAG["active"] = False
	_try_report_degraded(False, None)


def _try_report_degraded(active: bool, depth: Optional[int]) -> None:
	try:
		from pods.cockpit.cockpit_reporter import write_signal

		write_signal("resilience", "degraded", {"active": bool(active), "depth": (int(depth) if depth is not None else None)})
	except Exception:
		pass


__all__ = ["is_active", "activate", "deactivate"]

