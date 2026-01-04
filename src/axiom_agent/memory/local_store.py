from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_dir(path: str) -> None:
    d = os.path.dirname(path)
    if d and not os.path.exists(d):
        os.makedirs(d, exist_ok=True)


@dataclass
class LocalStoreAdapter:
    """
    Tiny local store adapter (SQLite) for the demo.

    Supports explicit begin/commit/rollback to demonstrate transactional behavior.
    """

    db_path: str

    def __post_init__(self) -> None:
        _ensure_dir(self.db_path)
        # isolation_level=None puts sqlite3 in autocommit mode; we control BEGIN/COMMIT explicitly.
        self._conn = sqlite3.connect(self.db_path, isolation_level=None)
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute("PRAGMA synchronous=NORMAL;")
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS journal_entries (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              created_at TEXT NOT NULL,
              payload_json TEXT NOT NULL
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS memory_entries (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              created_at TEXT NOT NULL,
              payload_json TEXT NOT NULL
            )
            """
        )

    def begin(self) -> None:
        self._conn.execute("BEGIN;")

    def commit(self) -> None:
        self._conn.execute("COMMIT;")

    def rollback(self) -> None:
        self._conn.execute("ROLLBACK;")

    def append_journal(self, payload: Dict[str, Any]) -> int:
        created_at = str(payload.get("created_at") or _utc_now_iso())
        cur = self._conn.execute(
            "INSERT INTO journal_entries (created_at, payload_json) VALUES (?, ?)",
            (created_at, json.dumps(payload, ensure_ascii=False, sort_keys=True)),
        )
        return int(cur.lastrowid)

    def append_memory(self, payload: Dict[str, Any]) -> int:
        created_at = str(payload.get("created_at") or _utc_now_iso())
        cur = self._conn.execute(
            "INSERT INTO memory_entries (created_at, payload_json) VALUES (?, ?)",
            (created_at, json.dumps(payload, ensure_ascii=False, sort_keys=True)),
        )
        return int(cur.lastrowid)

    def counts(self) -> Dict[str, int]:
        j = int(self._conn.execute("SELECT COUNT(*) FROM journal_entries").fetchone()[0])
        m = int(self._conn.execute("SELECT COUNT(*) FROM memory_entries").fetchone()[0])
        return {"journal_entries": j, "memory_entries": m}

    def close(self) -> None:
        self._conn.close()
