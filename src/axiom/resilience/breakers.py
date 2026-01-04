from __future__ import annotations

import os
import random
import time
from typing import Optional

from . import RESILIENCE_ENABLED


class Breaker:
	CLOSED = "closed"
	OPEN = "open"
	HALF_OPEN = "half_open"

	def __init__(self, fails: int, reset_sec: int, half_open_prob: float = 0.2):
		self.fails = max(1, int(fails))
		self.reset_sec = max(1, int(reset_sec))
		self.half_open_prob = float(half_open_prob)
		self.state = self.CLOSED
		self.errs = 0
		self.open_at = 0.0

	def allow(self) -> bool:
		if not RESILIENCE_ENABLED:
			return True
		if self.state == self.CLOSED:
			return True
		if self.state == self.OPEN and (time.time() - self.open_at) >= self.reset_sec:
			self.state = self.HALF_OPEN
		if self.state == self.HALF_OPEN:
			return random.random() < self.half_open_prob
		return False

	def success(self) -> None:
		self.errs = 0
		self.state = self.CLOSED

	def failure(self) -> None:
		self.errs += 1
		if self.errs >= self.fails:
			self.state = self.OPEN
			self.open_at = time.time()
			self.errs = 0
			_try_report_breaker_event("open")


def build_breaker_from_env() -> Breaker:
	def _env_int(name: str, default: int) -> int:
		try:
			return int(os.getenv(name, str(default)))
		except Exception:
			return default

	def _env_float(name: str, default: float) -> float:
		try:
			return float(os.getenv(name, str(default)))
		except Exception:
			return default

	return Breaker(
		fails=_env_int("BREAKER_FAILS", 5),
		reset_sec=_env_int("BREAKER_RESET_SEC", 60),
		half_open_prob=_env_float("BREAKER_HALF_OPEN_PROB", 0.2),
	)


def _try_report_breaker_event(event: str, dep: str = "vector") -> None:
	try:
		from pods.cockpit.cockpit_reporter import write_signal

		write_signal("resilience", f"breaker.{dep}.{event}", {})
	except Exception:
		pass


__all__ = ["Breaker", "build_breaker_from_env"]

