from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path


def _write_memory(tmp_path: Path, records: list[dict]):
    mf = tmp_path / "memory" / "long_term_memory.json"
    mf.parent.mkdir(parents=True, exist_ok=True)
    mf.write_text(json.dumps(records, indent=2))
    os.environ["MEMORY_FILE"] = str(mf)


def _ts(days_ago: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()


def test_plan_compaction_respects_retention_and_pins(tmp_path, monkeypatch):
    # Build small memory with timestamps
    recent = {"id": "r1", "type": "journal_entry", "timestamp": _ts(5)}
    old = {"id": "o1", "type": "journal_entry", "timestamp": _ts(400)}
    pinned_belief = {"id": "b1", "type": "belief", "related_journal_id": "o1"}
    _write_memory(tmp_path, [recent, old, pinned_belief])

    monkeypatch.setenv("JOURNAL_RETENTION_DAYS", "180")
    monkeypatch.setenv("JOURNAL_COMPACTION_ENABLED", "true")

    from lifecycle.compaction import plan_compaction

    plan = plan_compaction()
    keep = set(plan["keep_ids"]) if isinstance(plan.get("keep_ids"), set) else set(plan.get("keep_ids") or [])
    arch = set(plan["archive_ids"]) if isinstance(plan.get("archive_ids"), set) else set(plan.get("archive_ids") or [])

    # recent kept, old pinned via belief kept
    assert "r1" in keep
    assert "o1" not in arch


def test_run_compaction_dry_run_no_writes(tmp_path, monkeypatch):
    recent = {"id": "r1", "type": "journal_entry", "timestamp": _ts(5)}
    old = {"id": "o1", "type": "journal_entry", "timestamp": _ts(400)}
    _write_memory(tmp_path, [recent, old])

    monkeypatch.setenv("JOURNAL_RETENTION_DAYS", "180")
    monkeypatch.setenv("JOURNAL_COMPACTION_ENABLED", "true")
    monkeypatch.setenv("JOURNAL_COMPACTION_DRY_RUN", "true")
    monkeypatch.setenv("JOURNAL_ARCHIVE_DIR", str(tmp_path / "archive" / "journal"))
    monkeypatch.setenv("JOURNAL_MANIFEST_PATH", str(tmp_path / "archive" / "journal" / "manifest.json"))

    from lifecycle.compaction import run_compaction

    res = run_compaction(dry_run=True)
    # manifest should not exist
    assert not (tmp_path / "archive" / "journal" / "manifest.json").exists()
    # memory file untouched
    mf = Path(os.environ["MEMORY_FILE"]) 
    data = json.loads(mf.read_text())
    assert len(data) == 2

