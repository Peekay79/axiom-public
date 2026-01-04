#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from axiom_agent.champ.engine import ChampDecisionEngine, ChampMetrics
from axiom_agent.champ.explainability import explain_champ_decision
from axiom_agent.memory.local_store import LocalStoreAdapter


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _env_truthy(name: str) -> bool:
    return str(os.getenv(name, "")).strip().lower() in {"1", "true", "yes", "y", "on"}


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    db_path = os.getenv("AXIOM_DEMO_DB_PATH") or str(root / ".axiom_demo" / "demo.sqlite")
    force_fail = _env_truthy("AXIOM_DEMO_FORCE_FAIL")

    store = LocalStoreAdapter(db_path=db_path)

    metrics = ChampMetrics(confidence=0.72, payoff=0.60, tempo=0.40)
    engine = ChampDecisionEngine()
    decision = engine.decide(metrics)
    explanation = explain_champ_decision(metrics, decision)

    try:
        store.begin()
        store.append_journal(
            {
                "type": "demo_start",
                "created_at": _utc_now_iso(),
                "message": "synthetic demo journal entry",
            }
        )
        store.append_memory(
            {
                "type": "synthetic_memory",
                "created_at": _utc_now_iso(),
                "summary": "remembered: demo ran locally with no network",
                "tags": ["demo", "local", "offline"],
            }
        )
        store.append_journal(
            {
                "type": "champ_decision",
                "created_at": _utc_now_iso(),
                "metrics": metrics.__dict__,
                "decision": decision,
                "explanation": explanation,
            }
        )

        if force_fail:
            raise RuntimeError("AXIOM_DEMO_FORCE_FAIL=1 set; demonstrating rollback")

        store.commit()

        counts = store.counts()
        print("AXIOM demo OK")
        print(json.dumps({"db_path": db_path, "counts": counts, "decision": decision}, indent=2))
        return 0
    except Exception as e:
        try:
            store.rollback()
        except Exception:
            pass
        print(f"AXIOM demo rolled back: {e}", file=sys.stderr)
        return 1
    finally:
        try:
            store.close()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
