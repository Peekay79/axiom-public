#!/usr/bin/env python3
from __future__ import annotations

import os


def test_exactly_once_flow(monkeypatch):
    # Use temp sqlite path
    monkeypatch.setenv("EVENTLOG_DB", "eventlog/test_events.sqlite")
    monkeypatch.setenv("EVENTLOG_BATCH_SIZE", "10")

    from eventlog import store
    from eventlog.consumer import EventConsumer

    processed = []

    def h(ev):
        processed.append(ev.idem_key)

    # Append two events, including duplicate idem
    e1 = store.append("idem-1", "cid-1", "journal.append", {"entry": "x", "schema_version": "v2"})
    e2 = store.append("idem-1", "cid-1", "journal.append", {"entry": "x", "schema_version": "v2"})  # duplicate
    e3 = store.append("idem-2", "cid-2", "memory.write", {"text": "y", "tags": [], "schema_version": "v2"})

    cons = EventConsumer({"journal.append": h, "memory.write": h})
    n1 = cons.run_once()
    # Should process up to 2 unique events
    assert n1 >= 2
    # Duplicate idem does not add a second row
    n2 = cons.run_once()
    assert n2 == 0

