#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Any, List, Set, Tuple


# ---- Env and Cockpit helpers (fail-closed) ----
def _env_flag(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return bool(default)
    return str(val).strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    val = os.getenv(name)
    try:
        return int(val) if val is not None else int(default)
    except Exception:
        return int(default)


def _env_str(name: str, default: str) -> str:
    val = os.getenv(name)
    return str(val) if val is not None else str(default)


def _cockpit_signal(signal_name: str, payload: dict) -> None:
    try:
        from pods.cockpit.cockpit_reporter import write_signal

        write_signal("lifecycle", signal_name, payload)
    except Exception:
        # fail-closed: ignore emitter errors
        pass


# ---- Config knobs ----
JOURNAL_COMPACTION_ENABLED = _env_flag("JOURNAL_COMPACTION_ENABLED", True)
JOURNAL_RETENTION_DAYS = _env_int("JOURNAL_RETENTION_DAYS", 180)
JOURNAL_COMPACTION_DRY_RUN = _env_flag("JOURNAL_COMPACTION_DRY_RUN", True)
JOURNAL_ARCHIVE_DIR = Path(_env_str("JOURNAL_ARCHIVE_DIR", "archive/journal"))
JOURNAL_MANIFEST_PATH = Path(
    _env_str("JOURNAL_MANIFEST_PATH", "archive/journal/manifest.json")
)


# ---- Journal model integration ----
def _load_all_memories() -> List[Dict[str, Any]]:
    """Use Memory().snapshot() as journal source. Fail-closed on errors."""
    try:
        from pods.memory.memory_manager import Memory

        m = Memory()
        m.load()
        return list(m.snapshot())
    except Exception:
        return []


def _pinned_ids() -> Set[str]:
    """Collect journal IDs pinned by beliefs/provenance, active goals, or open sagas.

    - beliefs: entries may have related_journal_id in memory store
    - provenance: use known fields such as source_ids on journal entries
    - goals: Memory().get_goals() returns goal dicts that may reference journal IDs
    - open sagas: Cockpit signals contain saga steps with info referencing journal IDs
    """
    pinned: Set[str] = set()
    try:
        from pods.memory.memory_manager import Memory

        mem = Memory()
        mem.load()
        # Beliefs referencing journals
        for rec in mem.snapshot():
            if not isinstance(rec, dict):
                continue
            # Any explicit links
            rjid = rec.get("related_journal_id")
            if rjid:
                pinned.add(str(rjid))
            # Journal entries with source_ids that might reference earlier journal ids
            for sid in (rec.get("source_ids") or []):
                try:
                    if sid:
                        pinned.add(str(sid))
                except Exception:
                    pass
        # Goals may carry references as metadata
        for g in mem.get_goals():
            for key in ("related_journal_id", "journal_id", "source_id"):
                val = g.get(key)
                if val:
                    pinned.add(str(val))
    except Exception:
        pass

    # Saga signals: scan signal dir for recent saga files and pick IDs
    try:
        signal_dir = Path(os.environ.get("COCKPIT_SIGNAL_DIR", "axiom_boot"))
        if signal_dir.exists():
            for fp in sorted(signal_dir.glob("governor.saga_step.*.json"))[-500:]:
                try:
                    data = json.loads(fp.read_text())
                    info = (data.get("data") or {}).get("info") or {}
                    # Convention: info may include {"id": "<journal_id>"}
                    jid = info.get("id") or info.get("journal_id")
                    if jid:
                        pinned.add(str(jid))
                except Exception:
                    continue
    except Exception:
        pass

    return pinned


def _classify_entries(memories: List[Dict[str, Any]], now: datetime) -> Tuple[Set[str], Set[str]]:
    keep: Set[str] = set()
    archive: Set[str] = set()
    cutoff = now - timedelta(days=int(JOURNAL_RETENTION_DAYS))
    pinned = _pinned_ids()

    for rec in memories:
        if not isinstance(rec, dict):
            continue
        rid = rec.get("id")
        if not rid:
            continue
        # Always keep pinned
        if str(rid) in pinned:
            keep.add(str(rid))
            continue
        # Keep recent within retention window
        ts = rec.get("timestamp") or rec.get("created_at") or rec.get("updated_at")
        try:
            dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00")) if ts else None
        except Exception:
            dt = None
        if dt and dt >= cutoff:
            keep.add(str(rid))
            continue
        # Else eligible for archive
        archive.add(str(rid))

    return keep, archive


def plan_compaction(now: datetime | None = None) -> dict:
    """Compute compaction plan.

    Returns: {keep_ids:set, archive_ids:set, stats:{...}}
    """
    now = now or datetime.now(timezone.utc)
    memories = _load_all_memories()
    keep_ids, archive_ids = _classify_entries(memories, now)

    stats = {
        "total": len([m for m in memories if isinstance(m, dict) and m.get("id")]),
        "kept": len(keep_ids),
        "archived": len(archive_ids),
    }
    _cockpit_signal("lifecycle.compaction.planned", stats)
    return {"keep_ids": keep_ids, "archive_ids": archive_ids, "stats": stats}


def _write_atomic(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_fd, tmp_path = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp_manifest_")
    try:
        with os.fdopen(tmp_fd, "w") as f:
            json.dump(data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, str(path))
    finally:
        try:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
        except Exception:
            pass


def _rotate_to_archive(memories: List[Dict[str, Any]], archive_ids: Set[str]) -> Tuple[int, int]:
    """Write archived entries into rotated file under JOURNAL_ARCHIVE_DIR.

    Returns: (archived_count, bytes_written)
    """
    if not archive_ids:
        return 0, 0
    recs = [m for m in memories if str(m.get("id")) in archive_ids]
    if not recs:
        return 0, 0
    JOURNAL_ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    run_id = uuid.uuid4().hex[:12]
    out_path = JOURNAL_ARCHIVE_DIR / f"journal_archive_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{run_id}.jsonl"
    # Write to temp and atomically rename
    tmp_fd, tmp_path = tempfile.mkstemp(dir=str(JOURNAL_ARCHIVE_DIR), prefix=".tmp_archive_")
    total_bytes = 0
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            for rec in recs:
                line = json.dumps(rec, ensure_ascii=False)
                f.write(line + "\n")
                total_bytes += len(line) + 1
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, str(out_path))
    except Exception:
        # Abort on any error; leave journal untouched by returning zero
        try:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
        except Exception:
            pass
        raise
    return len(recs), total_bytes


def _remove_archived_from_memory(archive_ids: Set[str]) -> int:
    """Persist Memory file without archived IDs. Atomic write.
    Returns number removed.
    """
    from pods.memory.memory_manager import Memory

    mem = Memory()
    mem.load()
    before = len(mem.long_term_memory)
    mem.long_term_memory = [m for m in mem.long_term_memory if str(m.get("id")) not in archive_ids]
    after = len(mem.long_term_memory)
    # Atomic save of MEMORY_FILE
    try:
        path = Path(os.getenv("MEMORY_FILE", "memory/long_term_memory.json"))
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_fd, tmp_path = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp_memory_")
        try:
            with os.fdopen(tmp_fd, "w") as f:
                json.dump(mem.long_term_memory, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, str(path))
        finally:
            try:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
            except Exception:
                pass
    except Exception:
        # Fail-closed: abort removal if we couldn't write
        raise
    return before - after


def run_compaction(dry_run: bool = True) -> dict:
    if not JOURNAL_COMPACTION_ENABLED:
        reason = "disabled"
        _cockpit_signal("lifecycle.compaction.skipped", {"reason": reason})
        return {"skipped": True, "reason": reason}

    # Honor global dry-run default if caller did not override
    dry_run = bool(dry_run) if dry_run is not None else JOURNAL_COMPACTION_DRY_RUN

    plan = plan_compaction()
    keep_ids: Set[str] = set(plan["keep_ids"]) if isinstance(plan.get("keep_ids"), set) else set(plan.get("keep_ids") or [])
    archive_ids: Set[str] = set(plan["archive_ids"]) if isinstance(plan.get("archive_ids"), set) else set(plan.get("archive_ids") or [])

    if dry_run or _env_flag("JOURNAL_COMPACTION_DRY_RUN", JOURNAL_COMPACTION_DRY_RUN):
        summary = {
            "kept": len(keep_ids),
            "archived": len(archive_ids),
            "bytes_saved": 0,
            "run_id": uuid.uuid4().hex[:12],
            "ts": datetime.utcnow().isoformat(),
            "dry_run": True,
        }
        _cockpit_signal("lifecycle.compaction.completed", summary)
        return summary

    # Execute compaction: write archive, then remove from memory atomically
    try:
        memories = _load_all_memories()
        archived_count, bytes_written = _rotate_to_archive(memories, archive_ids)
        if archived_count != len(archive_ids):
            # Sanity check: if mismatch, abort removal to keep journal intact
            raise RuntimeError("archived_count_mismatch")
        removed = _remove_archived_from_memory(archive_ids)
        if removed != archived_count:
            # Extremely defensive: mismatch indicates partial failure; abort
            raise RuntimeError("removed_count_mismatch")
        manifest = {
            "kept": len(keep_ids),
            "archived": int(archived_count),
            "bytes_saved": int(bytes_written),
            "run_id": uuid.uuid4().hex[:12],
            "ts": datetime.utcnow().isoformat(),
        }
        # Best-effort manifest write
        try:
            _write_atomic(JOURNAL_MANIFEST_PATH, manifest)
        except Exception:
            pass
        _cockpit_signal("lifecycle.compaction.completed", manifest)
        return manifest
    except Exception as e:
        _cockpit_signal("lifecycle.compaction.skipped", {"reason": str(e)})
        # Fail-closed: leave journal untouched
        return {"skipped": True, "reason": str(e)}


if __name__ == "__main__":
    import sys

    dry = "--execute" not in sys.argv
    res = run_compaction(dry_run=dry)
    print(json.dumps(res, indent=2))

