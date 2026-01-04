import os
import time


def test_budgets_exceed_tokens_and_tools(monkeypatch):
	from resilience.budgets import BudgetEnforcer, BudgetExceeded
	be = BudgetEnforcer(tokens=10, tools=1)
	# One tool ok, second should exceed
	be.ensure_tool()
	try:
		be.ensure_tool()
		assert False, "Expected BudgetExceeded for tools"
	except BudgetExceeded as e:
		assert str(e) == "tools"
	# Tokens limit 10: charging 7 ok, then +5 exceeds
	be = BudgetEnforcer(tokens=10, tools=5)
	be.ensure_tokens(7)
	try:
		be.ensure_tokens(5)
		assert False, "Expected BudgetExceeded for tokens"
	except BudgetExceeded as e:
		assert str(e) == "tokens"


def test_breaker_opens_and_half_open_allows_some(monkeypatch):
	from resilience.breakers import Breaker
	br = Breaker(fails=3, reset_sec=1, half_open_prob=1.0)
	# 2 failures not open yet
	br.failure(); br.failure()
	assert br.allow() is True
	# Third failure opens
	br.failure()
	assert br.allow() is False
	# After reset, half-open
	time.sleep(1.05)
	assert br.allow() is True
	# Success closes
	br.success()
	assert br.allow() is True


def test_degraded_queues_to_outbox(tmp_path, monkeypatch):
	# Force degraded active and outbox to temp sqlite
	monkeypatch.setenv("DEGRADED_READONLY_ENABLED", "true")
	from resilience.degraded import activate, deactivate, is_active
	activate()
	assert is_active() is True
	monkeypatch.setenv("OUTBOX_ENABLED", "true")
	monkeypatch.setenv("OUTBOX_DB", str(tmp_path / "outbox.sqlite"))

	# Simulate Memory API JSON mode path by calling outbox append directly
	from outbox.models import OutboxItem
	from outbox.store import append, list_items

	item = OutboxItem(id=None, idem_key="idem_test", cid="cid1", type="vector_upsert", payload={"content":"x","metadata":{"memory_id":"m1"}})
	item_id = append(item)
	assert item_id > 0
	depth = len(list_items())
	assert depth >= 1
	deactivate()
