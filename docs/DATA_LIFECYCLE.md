## Data Lifecycle & Hygiene

Additive, env-gated lifecycle tasks for journal compaction and Qdrant snapshots. All actions are fail-closed and dry-run friendly.

### Config (ENV)

Defaults shown:

```
JOURNAL_COMPACTION_ENABLED=true
JOURNAL_RETENTION_DAYS=180
JOURNAL_COMPACTION_DRY_RUN=true
JOURNAL_ARCHIVE_DIR=archive/journal
JOURNAL_MANIFEST_PATH=archive/journal/manifest.json

QDRANT_SNAPSHOT_ENABLED=true
SNAPSHOT_SCHEDULE_CRON="0 3 * * *"   # daily 03:00 (operator-driven)
QDRANT_SNAPSHOT_DIR=archive/qdrant
QDRANT_SNAPSHOT_KEEP=7
```

### Compaction policy

- Retain: entries created within the last `JOURNAL_RETENTION_DAYS` days
- Pin: any entry referenced by beliefs/provenance, active goals, or open sagas
- Archive: older, unpinned entries → rotated `*.jsonl` in `JOURNAL_ARCHIVE_DIR`
- Manifest: `JOURNAL_MANIFEST_PATH` records `{kept, archived, bytes_saved, run_id, ts}`
- Safety: atomic writes; if anything fails, journal file is left untouched

Always run a dry-run first to validate plan and counts before executing.

### How to run (Compaction)

```bash
python -m lifecycle.compaction --dry-run
python -m lifecycle.compaction --execute
```

Dry-run computes the plan only and emits a Cockpit signal `lifecycle.compaction.planned` and a `completed` summary with `dry_run: true`. Execute will write rotated archives and a manifest, then remove archived entries.

### Snapshot drill (Qdrant)

Take snapshots and prune by retention. Uses native Qdrant snapshot API when available, otherwise scroll-dumps.

```bash
python -m lifecycle.snapshot --take --output archive/qdrant
python -m lifecycle.snapshot --drill --output archive/qdrant --keep 7
```

Restore is explicit and disabled in prod by default. Use only in staging by policy.

```bash
python -m lifecycle.snapshot --restore archive/qdrant/<file>.tar.gz --alias mem_current
```

Emitted signals:
- `lifecycle.snapshot.taken` (stats)
- `lifecycle.snapshot.pruned` (counts)
- `lifecycle.snapshot.failed` (reason)

### Cockpit visibility

`/status/cockpit` includes:

```
"lifecycle": {
  "compaction": {"last_run": "...", "kept": N, "archived": M, "bytes_saved": B},
  "snapshot": {"last_taken_at": "...", "last_path": "...", "size_bytes": S, "kept": K}
}
```

Optional gauges (Prometheus-style):
- `cockpit.lifecycle.compaction_bytes_saved`
- `cockpit.lifecycle.snapshot_last_size_bytes`

Optional alerts:
- Alert if compaction archived > X% in one run (possible misconfig)
- Alert if snapshot failed in last 24h

### Operational guidance

- Schedule compaction weekly (start with dry-run to verify no pinned entries would be removed)
- Schedule snapshots nightly; keep last 7
- Run a periodic restore drill in staging; verify recall parity on a small canary query set

