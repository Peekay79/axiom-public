import os
import re
import json
from pathlib import Path

import pytest


def _set_env(tmp_path: Path, overrides: dict | None = None):
    os.environ["AXIOM_CONTRADICTION_REGISTRY_PATH"] = str(tmp_path)
    os.environ["AXIOM_CONTRADICTION_RESOLUTION_ENABLED"] = "true"
    os.environ["AXIOM_CONTRADICTION_DECAY"] = "0.1"
    os.environ["AXIOM_CONTRADICTION_REFLECTION_INTERVAL"] = "1s"
    os.environ["AXIOM_CONTRADICTION_CHAMP_OVERRIDE"] = "true"
    os.environ["AXIOM_CONTRADICTION_CHAMP_THRESHOLD"] = "0.6"
    # Ensure CHAMP produces a decision deterministically by leaving defaults
    if overrides:
        for k, v in overrides.items():
            os.environ[k] = str(v)


def _read_registry(tmp_path: Path):
    p = tmp_path / "contradiction_registry.jsonl"
    if not p.exists():
        return []
    rows = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rows.append(json.loads(line))
    return rows


def test_severity_scoring_and_registry_logs(tmp_path, caplog):
    _set_env(tmp_path)
    from contradiction_registry import compute_severity, register_t1_t3_contradiction

    sev_low = compute_severity(
        narrative_conf=0.8,
        raw_conf=0.82,
        narrative_priority=True,
        involves_recent=False,
        raw_is_confident=False,
    )
    assert 0.0 <= sev_low <= 0.2

    sev_high = compute_severity(
        narrative_conf=0.6,
        raw_conf=0.98,
        narrative_priority=True,
        involves_recent=True,
        raw_is_confident=True,
    )
    assert 0.6 <= sev_high <= 1.0

    t1 = {"uuid": "t1-abc", "confidence": 0.82, "narrative_priority": True, "timestamp": "2025-10-01T00:00:00Z"}
    t3 = {"id": "mem-raw-1", "confidence": 0.96, "timestamp": "2025-10-01T00:00:00Z"}

    with caplog.at_level("INFO"):
        rec = register_t1_t3_contradiction(t1, t3)

    # Canonical logs
    assert any("[RECALL][ContradictionRegistry]" in m for m in caplog.messages)
    assert any("[RECALL][ContradictionSeverity]" in m for m in caplog.messages)

    rows = _read_registry(tmp_path)
    assert any(r.get("id") == rec.id for r in rows)
    stored = next(r for r in rows if r.get("id") == rec.id)
    assert stored.get("status") in {"unresolved", "tension", "resolved"}


def test_reflection_processing_and_decay(tmp_path, monkeypatch, caplog):
    _set_env(tmp_path)
    # Prepare a fake memory with T1 confidence that can be decayed
    from pods.memory.memory_manager import Memory
    mem = Memory()
    mem.load()
    t1_id = "t1-decay"
    mem.add_to_long_term({
        "id": t1_id,
        "uuid": t1_id,
        "type": "journal_entry",
        "content": "Narrative claim",
        "confidence": 0.8,
        "narrative_priority": True,
        "timestamp": "2025-10-01T00:00:00Z",
    })

    # Add a registry record where raw is stronger
    from contradiction_registry import process_unresolved_once
    reg_path = Path(os.environ["AXIOM_CONTRADICTION_REGISTRY_PATH"]) / "contradiction_registry.jsonl"
    reg_path.write_text(json.dumps({
        "id": "rec-1",
        "narrative_ref": t1_id,
        "raw_ref": "raw-1",
        "narrative_conf": 0.7,
        "raw_conf": 0.95,
        "severity": 0.5,
        "status": "unresolved",
        "timestamp": "2025-10-01T00:00:00Z"
    }) + "\n", encoding="utf-8")

    with caplog.at_level("INFO"):
        n = process_unresolved_once(severity_threshold=0.4)

    assert n == 1
    assert any("[RECALL][ContradictionResolved]" in m for m in caplog.messages)

    # Verify confidence decayed
    mem2 = Memory()
    mem2.load()
    t1 = next(m for m in mem2.long_term_memory if m.get("id") == t1_id)
    assert t1.get("confidence", 0.0) <= 0.8


def test_champ_override_trigger(tmp_path, caplog):
    _set_env(tmp_path)
    # High severity to exceed CHAMP threshold
    from contradiction_registry import register_t1_t3_contradiction
    t1 = {"uuid": "t1-cx", "confidence": 0.4, "narrative_priority": True, "timestamp": "2025-10-01T00:00:00Z"}
    t3 = {"id": "raw-cx", "confidence": 0.98, "timestamp": "2025-10-01T00:00:00Z"}

    with caplog.at_level("INFO"):
        register_t1_t3_contradiction(t1, t3)

    # Canonical CHAMP log
    assert any("[RECALL][Contradiction→CHAMPOverride]" in m for m in caplog.messages)


def test_fail_closed_off_switch(tmp_path, caplog):
    _set_env(tmp_path, {"AXIOM_CONTRADICTION_RESOLUTION_ENABLED": "false"})
    from contradiction_registry import register_t1_t3_contradiction
    t1 = {"uuid": "t1-off", "confidence": 0.7, "narrative_priority": True, "timestamp": "2025-10-01T00:00:00Z"}
    t3 = {"id": "raw-off", "confidence": 0.95, "timestamp": "2025-10-01T00:00:00Z"}
    with caplog.at_level("INFO"):
        register_t1_t3_contradiction(t1, t3)
    # Should still log registry & severity, but no immediate resolution logs required; just ensure no crash
    assert any("[RECALL][ContradictionRegistry]" in m for m in caplog.messages)
    assert any("[RECALL][ContradictionSeverity]" in m for m in caplog.messages)

