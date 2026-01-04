from __future__ import annotations

import os
import threading
from typing import Optional

from . import RESILIENCE_ENABLED


class BudgetExceeded(Exception):
	pass


class TurnBudget:
	def __init__(self, tokens_limit: int, tool_limit: int):
		self.tokens_limit = int(tokens_limit)
		self.tool_limit = int(tool_limit)
		self.tokens_used = 0
		self.tools_used = 0

	def charge_tokens(self, n: int) -> bool:
		try:
			self.tokens_used += int(n or 0)
			return self.tokens_used <= self.tokens_limit
		except Exception:
			# Fail-closed: if accounting fails, treat as over budget
			return False

	def charge_tool(self) -> bool:
		try:
			self.tools_used += 1
			return self.tools_used <= self.tool_limit
		except Exception:
			return False


class BudgetEnforcer:
	"""Per-turn budget enforcer.

	Additive and flag-gated; if RESILIENCE_ENABLED is False, methods are no-ops.
	"""

	def __init__(self, tokens: int, tools: int):
		self.turn = TurnBudget(tokens, tools)

	def ensure_tokens(self, n: int) -> None:
		if not RESILIENCE_ENABLED:
			return
		ok = self.turn.charge_tokens(int(n or 0))
		if not ok:
			_try_report_budget_exceeded("tokens")
			raise BudgetExceeded("tokens")

	def ensure_tool(self) -> None:
		if not RESILIENCE_ENABLED:
			return
		ok = self.turn.charge_tool()
		if not ok:
			_try_report_budget_exceeded("tools")
			raise BudgetExceeded("tools")


# ── Simple thread-local to scope a "turn" per request/thread ───────────────
_LOCAL = threading.local()


def _default_tokens_limit() -> int:
	try:
		return int(os.getenv("TOKENS_PER_TURN", "4000"))
	except Exception:
		return 4000


def _default_tools_limit() -> int:
	try:
		return int(os.getenv("TOOL_CALLS_PER_TURN", "6"))
	except Exception:
		return 6


def start_new_turn(tokens_limit: Optional[int] = None, tools_limit: Optional[int] = None) -> BudgetEnforcer:
	"""Create and bind a new BudgetEnforcer for the current thread.

	Call at the beginning of a request/turn. Safe to call multiple times.
	"""
	be = BudgetEnforcer(tokens=int(tokens_limit or _default_tokens_limit()), tools=int(tools_limit or _default_tools_limit()))
	set_current_enforcer(be)
	return be


def get_current_enforcer() -> Optional[BudgetEnforcer]:
	return getattr(_LOCAL, "be", None)


def set_current_enforcer(be: Optional[BudgetEnforcer]) -> None:
	setattr(_LOCAL, "be", be)


def ensure_tool_call() -> None:
	"""Convenience: charge one tool call against the current turn, if any."""
	be = get_current_enforcer()
	if be is None:
		return
	be.ensure_tool()


def ensure_token_usage(n: int) -> None:
	"""Convenience: charge token usage against the current turn, if any."""
	be = get_current_enforcer()
	if be is None:
		return
	be.ensure_tokens(n)


def _try_report_budget_exceeded(kind: str) -> None:
	"""Best-effort Cockpit signal for visibility."""
	try:
		from pods.cockpit.cockpit_reporter import write_signal

		write_signal("resilience", f"budget_exceeded.{kind}", {})
	except Exception:
		pass


__all__ = [
	"BudgetExceeded",
	"BudgetEnforcer",
	"TurnBudget",
	"start_new_turn",
	"get_current_enforcer",
	"set_current_enforcer",
	"ensure_tool_call",
	"ensure_token_usage",
]

