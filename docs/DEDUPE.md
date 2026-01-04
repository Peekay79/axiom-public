Qdrant De-duplication (safe + dry-run)
======================================

This tool helps clean up duplicate memories in Qdrant safely. It computes a canonical fingerprint for each memory and groups duplicates by fingerprint (optionally per source). It then selects a single survivor per group and prepares a deletion plan, which is dry‑run by default and backed up to a JSONL file.

What is a fingerprint?
----------------------
- A deterministic SHA‑1 hash over normalized fields: `type`, `memory_type`, `source`, `speaker`, and normalized `content` (or `text`).
- Computed at write time and stored as `payload.fingerprint`.
- Used by this tool to identify duplicates and by the system to derive stable point IDs for idempotent upserts.

Dry‑run and safe execution
--------------------------
- The tool runs in dry‑run mode by default. No deletions occur unless `--dry-run` is explicitly disabled.
- Every planned deletion is written to a timestamped JSONL backup with the survivor ID and the duplicate ID.
- You can scope grouping by fingerprint alone or by fingerprint+source with `--by-source`.

Quick start
-----------
1) Ensure environment

```bash
export AX_QDRANT_URL=http://<host>:<port>
```

2) Install dependency if needed

```bash
pip install qdrant-client
```

3) Backfill missing fingerprints (safe)

```bash
make dedupe-backfill
```

4) Preview duplicates (no deletions)

```bash
make dedupe-dry
```

5) Execute deletions (after review)

```bash
make dedupe-run
```

CLI options
-----------
- `--collection`: Qdrant collection name (default: `axiom_memories` or `AX_QDRANT_COLLECTION`)
- `--url`: Qdrant URL (default: `AX_QDRANT_URL`)
- `--api-key`: API key if needed
- `--by-source`: Group by fingerprint+source instead of fingerprint only
- `--limit`: Scroll page size (default: 5000)
- `--dry-run`: Dry‑run mode (default: true)
- `--backfill-only`: Only compute and set missing fingerprints; do not delete
- `--out`: Path to the backup JSONL file (default: `.data/dedupe_<ts>.jsonl`)

Restoring
---------
The backup JSONL file contains every duplicate ID and the chosen survivor for its group. You can use these records to recover points if needed by re‑ingesting or selectively restoring from snapshots.

Caveats
-------
- If you prefer to treat duplicate content from different sources as distinct, run with `--by-source`.
- Fingerprints are conservative but still hashes; always review the plan before deletion.

Why this works
--------------
- Idempotent upserts use deterministic point IDs based on the fingerprint; re‑ingesting overwrites instead of duplicating.
- The tool is conservative, dry‑runs by default, and writes a complete backup plan.
