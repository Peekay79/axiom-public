import logging
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from tests.utils.env import temp_env


@pytest.mark.phase("X")
def test_outbox_saga_retry_and_completion(monkeypatch, tmp_path, caplog):
    caplog.set_level(logging.INFO)

    # Point Outbox to temp sqlite
    with temp_env({
        "OUTBOX_ENABLED": "true",
        "OUTBOX_DB": str(tmp_path / "outbox.sqlite"),
        "OUTBOX_VISIBILITY_SEC": "0",
        "OUTBOX_MAX_RETRIES": "2",
    }):
        from outbox.models import OutboxItem
        from outbox.store import append, list_items
        from outbox.worker import OutboxWorker

        # Capture saga signals
        emitted = []
        def sb(cid, saga_type, meta=None): emitted.append(("begin", cid, saga_type, meta))
        def ss(cid, saga_type, step, ok, info=None): emitted.append(("step", cid, saga_type, step, ok, info))
        def se(cid, saga_type, ok, summary=None): emitted.append(("end", cid, saga_type, ok, summary))
        monkeypatch.setitem(__import__("sys").modules, "governor.saga", SimpleNamespace(saga_begin=sb, saga_step=ss, saga_end=se))

        # Handler that fails first two times for a specific idem_key, then succeeds
        call_counts = {"idem_x": 0}

        def handler(payload):
            ik = payload.get("idem_key")
            if ik == "idem_x":
                call_counts["idem_x"] += 1
                if call_counts["idem_x"] < 3:
                    raise RuntimeError("forced_fail")
            # success after retries
            return None

        handlers = {"vector_upsert": handler}
        worker = OutboxWorker(handlers)

        # Enqueue item
        oi = OutboxItem(id=None, idem_key="idem_x", cid="cid_1", type="vector_upsert", payload={"idem_key": "idem_x"})
        item_id = append(oi)
        assert item_id > 0

        # Run a few polling iterations manually by invoking internal claim/loop through run logic
        # Instead of run_forever, simulate three attempts by calling private logic via exposed functions
        from outbox.store import claim, fail_and_maybe_retry, ack_done
        from outbox import OUTBOX_MAX_RETRIES

        # 1st attempt → fail
        items = claim(max_items=1)
        assert items and items[0].id == item_id
        it = items[0]
        try:
            handlers[it.type](it.payload)
            ack_done(int(it.id or 0))
        except Exception as e:
            status = fail_and_maybe_retry(int(it.id or 0), str(e), OUTBOX_MAX_RETRIES)
            assert status != "DLQ"

        # 2nd attempt → fail
        items = claim(max_items=1)
        assert items and items[0].id == item_id
        it = items[0]
        try:
            handlers[it.type](it.payload)
            ack_done(int(it.id or 0))
        except Exception as e:
            status = fail_and_maybe_retry(int(it.id or 0), str(e), OUTBOX_MAX_RETRIES)
            assert status != "DLQ"

        # 3rd attempt → success
        items = claim(max_items=1)
        assert items and items[0].id == item_id
        it = items[0]
        handlers[it.type](it.payload)
        ack_done(int(it.id or 0))

        # Verify idempotency key persisted and final DONE shows up
        final = list_items()
        found = [x for x in final if int(x.id or 0) == item_id]
        assert found and found[0].status == "DONE"

        # Verify saga signals emitted (begin, multiple steps, end)
        # We aren't matching exact text, just that callbacks were called in some order
        kinds = [e[0] for e in emitted]
        assert "begin" in kinds and "step" in kinds and "end" in kinds

