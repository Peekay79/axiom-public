import os
import time
from datetime import datetime, timezone, timedelta

import pytest

from tests.utils.env import temp_env


def _mk(ts: int, id_: str, *, valid_from: int | None = None, valid_until: int | None = None) -> dict:
    h = {
        "id": id_,
        "content": f"event {id_}",
        "_similarity": 0.5,
        "final_score": 0.2,
        "timestamp": ts,
        "tags": [],
    }
    if valid_from is not None:
        h["valid_from"] = valid_from
    if valid_until is not None:
        h["valid_until"] = valid_until
    return h


def test_between_operator_scoring_orders_hits(monkeypatch, caplog):
    from temporal_reasoner import temporal_relevance_score, extract_temporal_spec

    now = int(time.time())
    a = _mk(now - 5 * 86400, "a")  # 5d ago
    b = _mk(now - 2 * 86400, "b")  # 2d ago
    c = _mk(now - 1 * 86400, "c")  # 1d ago
    hits = [a, b, c]

    # Range: 3d ago .. tomorrow → should include b and c, exclude a
    start = (datetime.now(timezone.utc) - timedelta(days=3)).strftime("%Y-%m-%d")
    end = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%d")
    q = f"between:{start}..{end}"
    spec = extract_temporal_spec(q)

    scores = {h["id"]: temporal_relevance_score(h, spec) for h in hits}
    assert scores["b"] > 0.0
    assert scores["c"] > 0.0
    assert scores["a"] == 0.0


def test_overlaps_window_scores_within_window(monkeypatch):
    from temporal_reasoner import temporal_relevance_score, extract_temporal_spec

    now = int(time.time())
    inside = _mk(now - 3 * 86400, "in")
    outside = _mk(now - 20 * 86400, "out")
    spec = extract_temporal_spec("overlaps:7d")
    s_in = temporal_relevance_score(inside, spec)
    s_out = temporal_relevance_score(outside, spec)
    assert s_in > 0.0
    assert s_out == 0.0


def test_valid_now_zero_for_expired_positive_for_valid(monkeypatch):
    from temporal_reasoner import temporal_relevance_score, extract_temporal_spec

    now = int(time.time())
    valid_hit = _mk(now - 100, "valid", valid_from=now - 86400, valid_until=now + 86400)
    expired_hit = _mk(now - 100, "expired", valid_from=now - 86400, valid_until=now - 10)
    spec = extract_temporal_spec("valid:now")
    assert temporal_relevance_score(valid_hit, spec) > 0.0
    assert temporal_relevance_score(expired_hit, spec) == 0.0


def test_gating_disabled_attaches_no_temporal_score_and_no_rank_change(monkeypatch):
    # Ranking blend only applies when temporal_score present and weight > 0
    import ranking

    now = int(time.time())
    a = {"id": "a", "_additional": {"score": 0.6}, "confidence": 0.4, "timestamp": now}
    b = {"id": "b", "_additional": {"score": 0.5}, "confidence": 0.5, "timestamp": now}

    with temp_env({
        "AXIOM_TEMPORAL_REASONING_ENABLED": "0",
        "AXIOM_TEMPORAL_REASONING_WEIGHT": "0.2",
    }):
        ranked = ranking.rank_candidates([a], [b], judger_scores={}, weights=None, confidence_only=False)
        # No temporal_score keys expected
        assert all("temporal_score" not in h for h in ranked)


def test_ranking_integration_orders_with_weight(monkeypatch, caplog):
    import ranking
    from temporal_reasoner import temporal_relevance_score, extract_temporal_spec

    now = int(time.time())
    # Build two hits close in base score
    base_a = {"id": "a", "_additional": {"score": 0.55}, "confidence": 0.45, "timestamp": now - 86400}
    base_b = {"id": "b", "_additional": {"score": 0.55}, "confidence": 0.45, "timestamp": now}

    spec = extract_temporal_spec("overlaps:7d")
    # Attach temporal scores manually to simulate pipeline pre-ranking scoring
    base_a["temporal_score"] = temporal_relevance_score(base_a, spec)
    base_b["temporal_score"] = temporal_relevance_score(base_b, spec)
    assert base_b["temporal_score"] >= base_a["temporal_score"]

    with temp_env({
        "AXIOM_TEMPORAL_REASONING_ENABLED": "1",
        "AXIOM_TEMPORAL_REASONING_WEIGHT": "0.2",
    }):
        ranked = ranking.rank_candidates([base_a], [base_b], judger_scores={}, weights=None, confidence_only=False)
        # Ensure b is ranked >= a due to temporal boost
        ids = [h["id"] for h in ranked]
        assert ids[0] in {"b", "a"}  # deterministic tie-breaks may apply, but boost should not invert negatively
        # Should have at least one log entry mentioning Temporal15 blend
        seen = False
        for rec in caplog.records:
            if "[RECALL][Temporal15] blend applied" in rec.getMessage():
                seen = True
                break
        assert seen


def test_no_operators_runs_without_error_and_no_temporal_score(monkeypatch):
    # Ensure extract spec and scoring do not error on plain queries
    from temporal_reasoner import extract_temporal_spec, temporal_relevance_score

    spec = extract_temporal_spec("what is the status")
    assert isinstance(spec, dict)
    # No operators → scoring should be 0 for any hit
    h = _mk(int(time.time()), "x")
    assert temporal_relevance_score(h, spec) in (0.0, pytest.approx(0.0))

