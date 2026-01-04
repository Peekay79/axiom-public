#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from memory.utils.contradiction_utils import (
    conflict_identity,
    resolve_conflict_timestamp,
)


def test_conflict_identity_prefers_uuid():
    c = {"uuid": "conf-123", "belief_a": "A", "belief_b": "B"}
    assert conflict_identity(c) == "conf-123"


def test_conflict_identity_hashes_text_when_missing_ids():
    c = {"belief_a": "A should do X", "belief_b": "A should not do X"}
    cid = conflict_identity(c)
    assert isinstance(cid, str) and len(cid) > 3


def test_resolve_conflict_timestamp_prefers_created_at_then_meta():
    now = datetime.now(timezone.utc)
    older = (now - timedelta(days=3)).isoformat()
    newer = (now - timedelta(days=1)).isoformat()
    c = {
        "belief_a": "A",
        "belief_b": "B",
        "belief_a_meta": {"last_updated": older},
        "created_at": newer,
    }
    ts = resolve_conflict_timestamp(c)
    # Should pick 'created_at' first
    assert ts.isoformat().startswith(newer[:19])

