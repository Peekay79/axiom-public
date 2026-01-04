from __future__ import annotations

import json
import os


def test_chaos_skip_when_no_docker(monkeypatch):
    # Arrange: ensure CHAOS is enabled but docker not present and not dry-run
    monkeypatch.setenv("CHAOS_ENABLED", "true")
    monkeypatch.setenv("CHAOS_TARGETS", "[\"vector\",\"memory\"]")
    monkeypatch.setenv("CHAOS_DRY_RUN", "false")

    # Simulate no docker
    import chaos.drills as drills
    monkeypatch.setattr(drills, "_has_docker", lambda: False)

    res = drills.kill_pod("vector", 5)
    assert res.get("skipped") is True
    assert res.get("reason") == "docker_not_present"


def test_chaos_dry_run_does_not_crash(monkeypatch, capsys):
    monkeypatch.setenv("CHAOS_ENABLED", "true")
    monkeypatch.setenv("CHAOS_TARGETS", "[\"vector\",\"memory\"]")
    monkeypatch.setenv("CHAOS_DRY_RUN", "true")

    import chaos.drills as drills

    rec = drills.drill_once(["vector"], 1)
    assert isinstance(rec, dict)
    assert rec.get("target") in {"vector"}
    # Ensure CLI path prints JSON and does not crash
    from chaos.drills import main
    rc = main(["--once", "--target", "vector", "--duration", "1"])
    assert rc == 0
    out = capsys.readouterr().out.strip()
    assert out.startswith("{") and out.endswith("}")

