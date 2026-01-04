import os
import time
from datetime import datetime, timezone, timedelta

import pytest

from tests.utils.env import temp_env


def _mk_hit(ts: int, id_: str) -> dict:
    return {
        "id": id_,
        "content": f"event {id_}",
        "_similarity": 0.9,
        "final_score": 0.5,
        "timestamp": ts,
        "tags": [],
    }


def test_before_after_filters_apply():
    from temporal_utils import extract_temporal_spec, apply_temporal_filters

    # Build three hits with increasing time
    t0 = int(time.time()) - 3 * 86400
    t1 = int(time.time()) - 2 * 86400
    t2 = int(time.time()) - 1 * 86400
    hits = [_mk_hit(t0, "a"), _mk_hit(t1, "b"), _mk_hit(t2, "c")]

    spec = extract_temporal_spec("before:2099-01-01 after:1970-01-02")
    out = apply_temporal_filters(hits, spec)
    assert len(out) == 3

    # After cutoff excluding oldest (after: yesterday-1)
    day_cut = datetime.now(timezone.utc) - timedelta(days=2)
    q = f"after:{day_cut.strftime('%Y-%m-%d')}"
    spec2 = extract_temporal_spec(q)
    out2 = apply_temporal_filters(hits, spec2)
    ids2 = {h["id"] for h in out2}
    assert ids2 == {"b", "c"}

    # Before cutoff excluding newest (before: yesterday)
    day_cut2 = datetime.now(timezone.utc) - timedelta(days=1)
    q2 = f"before:{day_cut2.strftime('%Y-%m-%d')}"
    spec3 = extract_temporal_spec(q2)
    out3 = apply_temporal_filters(hits, spec3)
    ids3 = {h["id"] for h in out3}
    assert ids3 == {"a", "b"}


def test_since_maps_to_relative_days():
    from temporal_utils import extract_temporal_spec, apply_temporal_filters, since_to_epoch

    t_now = int(time.time())
    # Create hits at T-1d and T-3d
    h1 = _mk_hit(t_now - 86400, "h1")
    h3 = _mk_hit(t_now - 3 * 86400, "h3")
    hits = [h1, h3]

    spec = extract_temporal_spec("since:2d")
    cutoff = spec.get("since_cutoff_ts")
    assert cutoff is not None
    # Must be close to t_now - 2d
    assert abs(cutoff - since_to_epoch(2, anchor_ts=t_now)) <= 2
    out = apply_temporal_filters(hits, spec)
    ids = {h["id"] for h in out}
    assert ids == {"h1"}


def test_bias_recent_applies_only_on_ties(monkeypatch):
    # Two hits with equal final_score, different timestamps
    from temporal_utils import tiebreak_by_recency

    t_old = int(time.time()) - 10
    t_new = int(time.time())
    a = _mk_hit(t_old, "old")
    b = _mk_hit(t_new, "new")
    # Equalize final_score explicitly
    a["final_score"] = 0.8
    b["final_score"] = 0.8

    ordered = tiebreak_by_recency([a, b])
    assert ordered[0]["id"] == "new"

    # Non-tied scores should preserve order (no change)
    a2 = _mk_hit(t_old, "old2")
    b2 = _mk_hit(t_new, "new2")
    a2["final_score"] = 0.9
    b2["final_score"] = 0.8
    ordered2 = tiebreak_by_recency([a2, b2])
    assert [h["id"] for h in ordered2] == ["a2", "b2"].__class__(["old2", "new2"])  # identity check


def test_disabled_temporal_sequencing_baseline(monkeypatch):
    # Ensure retrieval_planner does not strip operators when disabled
    import retrieval_planner as rp

    with temp_env({"AXIOM_TEMPORAL_SEQUENCING_ENABLED": "0"}):
        q = rp.plan_query("before:2025-01-01 events about Hev")
        # With sequencing disabled, planner may still simplify but shouldn't strip temporal token
        assert "before:2025-01-01" in q or q == "before:2025-01-01 events about hev"

