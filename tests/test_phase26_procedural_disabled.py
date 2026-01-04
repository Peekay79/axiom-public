from __future__ import annotations

import os


def test_procedural_loop_disabled_does_not_run(monkeypatch, caplog):
    os.environ["AXIOM_PROCEDURAL_LOOP_ENABLED"] = "0"
    from procedural_loop import maybe_run_procedural_loop

    with caplog.at_level("INFO"):
        res = maybe_run_procedural_loop()
    assert res.get("status") == "aborted"
    assert res.get("reason") in {"disabled", "tripwire"}

