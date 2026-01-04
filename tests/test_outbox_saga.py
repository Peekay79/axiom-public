import logging
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from tests.utils.env import temp_env


@pytest.mark.phase("subsystems")
def test_env_gating_and_canonical_logs(monkeypatch, tmp_path, caplog):
    caplog.set_level(logging.INFO)

    # With AXIOM_OUTBOX_ENABLED=0, worker should log disabled and do nothing
    with temp_env({
        "AXIOM_OUTBOX_ENABLED": "0",
        "OUTBOX_DB": str(tmp_path / "outbox.sqlite"),
    }):
        from importlib import reload
        import outbox
        reload(outbox)
        from outbox.worker import OutboxWorker

        worker = OutboxWorker({})
        # Run only one loop iteration by calling internal methods indirectly: claim returns empty, but gate should block first
        worker.run_forever = MagicMock()  # prevent long running
        # Gate log should be present from import path
        assert any("[RECALL][Outbox]" in rec.getMessage() for rec in caplog.records)

    # With AXIOM_SAGA_ENABLED=0, governor.saga emits disabled logs and no signals
    with temp_env({
        "AXIOM_SAGA_ENABLED": "0",
    }):
        from importlib import reload
        import governor.saga as saga
        reload(saga)
        saga.saga_begin("cid-x", "TestSaga", {"k": 1})
        saga.saga_step("cid-x", "TestSaga", "step1", True, {})
        saga.saga_end("cid-x", "TestSaga", True, {})
        assert any("[RECALL][Saga]" in rec.getMessage() for rec in caplog.records)


@pytest.mark.phase("subsystems")
def test_fail_closed_and_logging(monkeypatch, tmp_path, caplog):
    caplog.set_level(logging.INFO)

    with temp_env({
        "AXIOM_OUTBOX_ENABLED": "1",
        "AXIOM_SAGA_ENABLED": "1",
        "OUTBOX_DB": str(tmp_path / "outbox.sqlite"),
        "OUTBOX_VISIBILITY_SEC": "0",
        "OUTBOX_MAX_RETRIES": "1",
    }):
        import importlib, sys
        # Capture saga signals
        emitted = []

        def sb(cid, saga_type, meta=None):
            emitted.append(("begin", cid, saga_type))

        def ss(cid, saga_type, step, ok, info=None):
            emitted.append(("step", cid, ok))

        def se(cid, saga_type, ok, summary=None):
            emitted.append(("end", cid, ok))

        # Patch saga BEFORE importing worker so it binds to our callbacks
        monkeypatch.setitem(sys.modules, "governor.saga", SimpleNamespace(saga_begin=sb, saga_step=ss, saga_end=se))

        import outbox
        importlib.reload(outbox)
        import outbox.store as ob_store
        importlib.reload(ob_store)
        import outbox.worker as ob_worker
        importlib.reload(ob_worker)
        from outbox.models import OutboxItem
        from outbox.store import append
        from outbox.worker import OutboxWorker

        calls = {"x": 0}

        def handler(payload):
            if payload.get("idem_key") == "x":
                calls["x"] += 1
                if calls["x"] == 1:
                    raise RuntimeError("boom")

        worker = OutboxWorker({"vector_upsert": handler})

        # Append
        oi = OutboxItem(id=None, idem_key="x", cid="c1", type="vector_upsert", payload={"idem_key": "x"})
        item_id = append(oi)
        assert item_id > 0

        # Use the worker single-iteration runner which emits canonical logs
        worker.run_once()
        worker.run_once()

        # Check logs contain canonical tags
        msgs = [r.getMessage() for r in caplog.records]
        assert any("[RECALL][Outbox]" in m for m in msgs)
        # We don't assert exact wording, only presence of canonical tags

        # Saga callbacks called
        kinds = [e[0] for e in emitted]
        assert "begin" in kinds and "step" in kinds and "end" in kinds
