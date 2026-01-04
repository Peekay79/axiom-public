import os
import time
from datetime import datetime, timezone

from outbox import OUTBOX_DB, OUTBOX_MAX_RETRIES
from outbox.models import OutboxItem, OutboxStatus
from outbox.store import append, claim, ack_done, fail_and_maybe_retry, list_items, purge


def test_idempotent_append(tmp_path):
	os.environ["OUTBOX_DB"] = str(tmp_path / "outbox.sqlite")
	item = OutboxItem(id=None, idem_key="idem_1", cid="corr_1", type="vector_upsert", payload={"x": 1})
	id1 = append(item)
	id2 = append(item)
	assert id1 == id2 and id1 != 0


def test_retry_to_dlq(tmp_path):
	os.environ["OUTBOX_DB"] = str(tmp_path / "outbox.sqlite")
	os.environ["OUTBOX_VISIBILITY_SEC"] = "1"
	item = OutboxItem(id=None, idem_key="idem_2", cid="corr_2", type="vector_upsert", payload={})
	item_id = append(item)
	# Claim and fail repeatedly
	it = claim(max_items=1)[0]
	for i in range(OUTBOX_MAX_RETRIES + 1):
		status = fail_and_maybe_retry(it.id, f"e{i}", OUTBOX_MAX_RETRIES)
	last = [x for x in list_items() if x.id == item_id][0]
	assert last.status == OutboxStatus.DLQ


def test_visibility_timeout_redelivery(tmp_path):
	os.environ["OUTBOX_DB"] = str(tmp_path / "outbox.sqlite")
	os.environ["OUTBOX_VISIBILITY_SEC"] = "1"
	item = OutboxItem(id=None, idem_key="idem_3", cid="corr_3", type="vector_upsert", payload={})
	append(item)
	first = claim(max_items=1)[0]
	time.sleep(1.2)  # let visibility expire
	second = claim(max_items=1)[0]
	assert first.id == second.id
	# ack once should finalize
	ack_done(first.id)
	left = [x for x in list_items() if x.id == first.id][0]
	assert left.status == OutboxStatus.DONE