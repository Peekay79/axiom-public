import logging
from datetime import datetime, timezone

import pytest


def _now():
    return datetime.now(timezone.utc).isoformat()


def _seed_memory(mem):
    mem.store({"id": "u1", "content": "user likes apples", "speaker": "user", "timestamp": _now(), "memory_type": "episodic", "confidence": 0.7})
    mem.store({"id": "a1", "content": "assistant suggests buying apples", "speaker": "axiom", "timestamp": _now(), "memory_type": "episodic", "confidence": 0.7})
    mem.store({"id": "u2", "content": "user reports apples helped", "speaker": "user", "timestamp": _now(), "memory_type": "episodic", "confidence": 0.7})


@pytest.mark.phase("25-27")
def test_consolidation_with_fallback_and_manifest(monkeypatch, tmp_path, caplog):
    caplog.set_level(logging.INFO)

    # Provide a stub Memory that reports fallback active and returns seeded snapshot
    class FakeMemory:
        def __init__(self):
            self._snap = []
            _seed_memory(self)

        def store(self, entry):
            self._snap.append(entry)

        def snapshot(self, limit=None):
            return self._snap[:]

        def is_fallback_mode(self):
            return True

    # Patch each loop module to use the FakeMemory
    import episodic_loop as L25
    import procedural_loop as L26
    import abstraction_loop as L27

    monkeypatch.setattr(L25, "Memory", FakeMemory)
    monkeypatch.setattr(L26, "Memory", FakeMemory)
    monkeypatch.setattr(L27, "Memory", FakeMemory)

    # Enable loops to exercise fallback tag emission paths
    monkeypatch.setenv("AXIOM_EPISODIC_LOOP_ENABLED", "1")
    monkeypatch.setenv("AXIOM_PROCEDURAL_LOOP_ENABLED", "1")
    monkeypatch.setenv("AXIOM_ABSTRACTION_LOOP_ENABLED", "1")

    res25 = L25.maybe_run_episodic_loop()
    assert res25.get("status") in {"ok", "aborted"}
    res26 = L26.maybe_run_procedural_loop()
    assert res26.get("status") in {"ok", "aborted"}
    res27 = L27.maybe_run_abstraction_loop()
    assert res27.get("status") in {"ok", "aborted"}

    # Assert canonical fallback tags present from any of the loops
    msgs = [r.getMessage() for r in caplog.records]
    assert any("[RECALL][Loop25][Fallback]" in m or "[RECALL][Loop26][Fallback]" in m or "[RECALL][Loop27][Fallback]" in m for m in msgs)


@pytest.mark.phase("25-27")
def test_consolidation_fail_closed_without_fallback(monkeypatch, caplog):
    caplog.set_level(logging.INFO)

    # Ensure loops run (even if disabled they should fail-closed without crash)
    import episodic_loop as L25
    import procedural_loop as L26
    import abstraction_loop as L27

    r1 = L25.maybe_run_episodic_loop()
    r2 = L26.maybe_run_procedural_loop()
    r3 = L27.maybe_run_abstraction_loop()
    assert r1.get("status") in {"ok", "aborted"}
    assert r2.get("status") in {"ok", "aborted"}
    assert r3.get("status") in {"ok", "aborted"}

    # If nothing seeded or fallback disabled, there should be no crash and standard tags still appear
    msgs = [r.getMessage() for r in caplog.records]
    assert any("[RECALL][Loop25]" in m for m in msgs)
    assert any("[RECALL][Loop26]" in m for m in msgs)
    assert any("[RECALL][Loop27]" in m for m in msgs)

import logging

import pytest

from tests.utils.env import temp_env


@pytest.mark.phase("25-27")
def test_consolidation_loops_dry_run_and_disabled(monkeypatch, caplog):
    caplog.set_level(logging.INFO)

    # Mock Memory snapshot to provide minimal entries; Belief graph ops will be None-safe
    class DummyMem:
        def snapshot(self, limit=None):
            return [
                {"id": "m1", "content": "talk about project alpha", "timestamp": "2025-01-01T00:00:00+00:00", "type": "user", "tags": ["episodic"]},
                {"id": "m2", "content": "AXIOM answered with plan", "timestamp": "2025-01-01T00:10:00+00:00", "type": "axiom"},
                {"id": "m3", "content": "user confirms outcome", "timestamp": "2025-01-01T00:20:00+00:00", "type": "user"},
            ]

    monkeypatch.setitem(__import__("sys").modules, "pods.memory.memory_manager", type("M", (), {"Memory": lambda: DummyMem()}))

    # Abstraction loop dry-run (AXIOM_ABSTRACTION_DRY_RUN=1)
    with temp_env({"AXIOM_ABSTRACTION_LOOP_ENABLED": "1", "AXIOM_ABSTRACTION_DRY_RUN": "1"}):
        from abstraction_loop import maybe_run_abstraction_loop

        res = maybe_run_abstraction_loop()
        assert res.get("status") in {"ok", "aborted"}
        # Expect at least one Abstraction log line
        assert any("[RECALL][Loop27]" in r.getMessage() for r in caplog.records)
        # Dry-run should not corrupt memory; our dummy does not mutate

    # Episodic loop enabled
    with temp_env({"AXIOM_EPISODIC_LOOP_ENABLED": "1", "AXIOM_EPISODIC_WINDOW_HOURS": "24"}):
        from episodic_loop import maybe_run_episodic_loop

        res = maybe_run_episodic_loop()
        assert res.get("status") in {"ok", "aborted"}
        assert any("[RECALL][Loop25]" in r.getMessage() for r in caplog.records)

    # Procedural loop enabled
    with temp_env({"AXIOM_PROCEDURAL_LOOP_ENABLED": "1", "AXIOM_PROCEDURAL_WINDOW_TURNS": "9", "AXIOM_PROCEDURAL_MIN_SUPPORT": "1"}):
        from procedural_loop import maybe_run_procedural_loop

        res = maybe_run_procedural_loop()
        assert res.get("status") in {"ok", "aborted"}
        assert any("[RECALL][Loop26]" in r.getMessage() for r in caplog.records)

    # Disabled flags cause no-op/aborted
    with temp_env({
        "AXIOM_ABSTRACTION_LOOP_ENABLED": "0",
        "AXIOM_EPISODIC_LOOP_ENABLED": "0",
        "AXIOM_PROCEDURAL_LOOP_ENABLED": "0",
    }):
        from abstraction_loop import maybe_run_abstraction_loop
        from episodic_loop import maybe_run_episodic_loop
        from procedural_loop import maybe_run_procedural_loop

        ar = maybe_run_abstraction_loop()
        er = maybe_run_episodic_loop()
        pr = maybe_run_procedural_loop()
        assert ar.get("status") == "aborted" and ar.get("reason") == "disabled"
        assert er.get("status") == "aborted" and er.get("reason") == "disabled"
        assert pr.get("status") == "aborted" and pr.get("reason") == "disabled"

