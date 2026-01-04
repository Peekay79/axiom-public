import os
from tests.utils.env import temp_env


def test_missing_provenance_hits_are_dropped(monkeypatch):
    # Ensure planner filter and pipeline filter work when provenance is required
    with temp_env({"AXIOM_PROVENANCE_REQUIRED": "1"}):
        # Build a mixed set of hits
        raw = [
            {"id": "a", "content": "x", "provenance": "user"},
            {"id": "b", "content": "y"},  # missing provenance
            {"id": "c", "content": "z", "metadata": {"provenance": "system"}},
            {"id": "d", "content": "w", "source": "journal"},
            {"id": "e", "content": "q"},  # missing provenance
        ]

        from retrieval_planner import _filter_missing_provenance as _f  # type: ignore

        kept = _f(raw)
        ids = sorted([h["id"] for h in kept])
        assert ids == ["a", "c", "d"], ids
