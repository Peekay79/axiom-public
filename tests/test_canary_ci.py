from __future__ import annotations

import json
import os
from pathlib import Path


class _StubRetrieval:
    def __init__(self, mapping):
        self.mapping = mapping

    async def search_hybrid(self, query: str, k: int):
        # Return list of dicts with id keys
        items = self.mapping.get(query, [])
        return [{"id": x} for x in items][:k]


def test_canary_eval_and_signals(tmp_path, monkeypatch, capsys):
    os.environ["CANARY_CI_ENABLED"] = "true"
    os.environ["COCKPIT_SIGNAL_DIR"] = str(tmp_path)

    # Create a simple canary dataset
    ds = tmp_path / "canaries.jsonl"
    lines = [
        {"q": "q1", "labels": ["a", "b"]},
        {"q": "q2", "labels": ["x"]},
    ]
    with ds.open("w") as f:
        for it in lines:
            f.write(json.dumps(it) + "\n")

    # Stub retrieval.search_hybrid
    mapping = {"q1": ["a", "z"], "q2": ["y", "x"]}
    stub = _StubRetrieval(mapping)

    import retrieval

    monkeypatch.setattr(retrieval, "search_hybrid", stub.search_hybrid)

    # Run canary CLI first time (baseline will be 0 then updated)
    from ci.nightly_canary import _main_sync

    rc = _main_sync(str(ds), 1)
    assert rc == 0
    out = capsys.readouterr().out.strip()
    assert out
    # Signals should be present
    r_files = list(tmp_path.glob("ci.canary.recall_at_k*.json"))
    d_files = list(tmp_path.glob("ci.canary.delta*.json"))
    assert r_files, "recall signal missing"
    assert d_files, "delta signal missing"

    # Second run should compute delta vs baseline
    rc2 = _main_sync(str(ds), 1)
    assert rc2 == 0
    out2 = capsys.readouterr().out.strip()
    assert out2

