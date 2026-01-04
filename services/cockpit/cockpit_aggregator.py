#!/usr/bin/env python3
"""
Project Cockpit – Aggregator (Phase 1)

Reads readiness/error/heartbeat/custom JSON signals and prints a concise health summary.

Example:
    python pods/cockpit/cockpit_aggregator.py --summary
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from pathlib import Path

SIGNAL_DIR = Path(os.environ.get("COCKPIT_SIGNAL_DIR", "axiom_boot"))
PODS = ["llm", "vector", "memory", "belief", "journal"]

# Tuning knobs
LATENCY_WARN_MS = int(os.environ.get("COCKPIT_LATENCY_WARN_MS", "250") or 250)
BLACKOUT_FAILS = int(os.environ.get("COCKPIT_BLACKOUT_FAILS", "3") or 3)
BLACKOUT_WINDOW_SEC = int(
    os.environ.get("COCKPIT_BLACKOUT_WINDOW_SEC", "30") or 30
)
WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()
STARTUP_SLOW_SEC = int(os.environ.get("COCKPIT_STARTUP_SLOW_SEC", "60") or 60)
DRIFT_WINDOW_SEC = int(os.environ.get("COCKPIT_DRIFT_WINDOW_SEC", "300") or 300)
# Retrieval drift alert thresholds (optional)
DRIFT_ALERT_KL = float(os.environ.get("DRIFT_ALERT_KL", "0.15") or 0.15)
DRIFT_ALERT_COSINE_SHIFT = float(os.environ.get("DRIFT_ALERT_COSINE_SHIFT", "0.08") or 0.08)


def _read_text(path: Path) -> str | None:
    try:
        if path.exists():
            return path.read_text().strip()
    except Exception:
        return None
    return None


def read_status(pod: str) -> dict:
    status = {"pod": pod, "ready": False, "error": None, "heartbeat_ok": False}
    ready_file = SIGNAL_DIR / f"{pod}.ready"
    error_file = SIGNAL_DIR / f"{pod}.error"
    hb_file = SIGNAL_DIR / f"{pod}.last_heartbeat"

    if ready_file.exists():
        status["ready"] = True

    if error_file.exists():
        try:
            status["error"] = error_file.read_text().strip()
        except Exception:
            status["error"] = "<unreadable error file>"

    if hb_file.exists():
        try:
            ts = datetime.fromisoformat(hb_file.read_text().strip())
            status["heartbeat_ok"] = (datetime.utcnow() - ts) < timedelta(seconds=90)
        except Exception:
            status["heartbeat_ok"] = False

    return status


def _color(msg: str, kind: str) -> str:
    # Simple ANSI coloring (works in most terminals)
    colors = {
        "ok": "\033[92m",       # green
        "warn": "\033[93m",     # yellow
        "err": "\033[91m",      # red
        "reset": "\033[0m",
    }
    if kind not in colors:
        return msg
    return f"{colors[kind]}{msg}{colors['reset']}"


def summary() -> int:
    statuses = [read_status(p) for p in PODS]
    exit_code = 0
    for s in statuses:
        if not s["ready"]:
            print(_color(f"❌ {s['pod']} not ready", "err"))
            exit_code = max(exit_code, 1)
        elif s["error"]:
            print(_color(f"⚠️ {s['pod']} error: {s['error']}", "warn"))
            exit_code = max(exit_code, 1)
        elif not s["heartbeat_ok"]:
            print(_color(f"⚠️ {s['pod']} heartbeat stale", "warn"))
            exit_code = max(exit_code, 1)
        else:
            print(_color(f"✅ {s['pod']} healthy", "ok"))
    return exit_code


# ─────────────────────────────────────────────────────────────
# Phase 2: Aggregation, blackout/degrade detection, alerts
# ─────────────────────────────────────────────────────────────


def _iter_signal_files(prefix: str) -> List[Path]:
    try:
        if not SIGNAL_DIR.exists():
            return []
        return sorted(SIGNAL_DIR.glob(prefix), key=lambda p: p.stat().st_mtime)
    except Exception:
        return []


def _read_json(path: Path) -> Optional[Dict[str, Any]]:
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception:
        return None


def _vector_recall_samples() -> List[Dict[str, Any]]:
    files = _iter_signal_files("vector.vector_recall*.json")
    samples: List[Dict[str, Any]] = []
    for fp in files[-200:]:  # cap read to last 200 to bound cost
        data = _read_json(fp)
        if not data:
            continue
        payload = data.get("data") if isinstance(data, dict) else None
        if not isinstance(payload, dict):
            continue
        samples.append(payload)
    return samples


def _blocked_write_count() -> int:
    files = _iter_signal_files("*.blocked_write*.json")
    return len(files)


def _journal_write_failures() -> int:
    files = _iter_signal_files("*.journal_write_failure*.json")
    return len(files)


def _belief_insert_failures() -> int:
    files = _iter_signal_files("*.belief_insert_failure*.json")
    return len(files)


def _detect_vector_blackout(samples: List[Dict[str, Any]]) -> bool:
    if not samples:
        return False
    now = datetime.utcnow()
    fail_recent = 0
    for s in reversed(samples):
        ts_iso = s.get("ts") or None  # some writers may duplicate ts
        ok = s.get("ok")
        # Use file mtime window if ts not present in payload
        # Since we don't carry per-record time here, assume all files are latest; conservative approach: count last N failures.
        if ok is False:
            fail_recent += 1
        # Stop early if threshold met
        if fail_recent >= BLACKOUT_FAILS:
            return True
    return False


def _mean_latency_ms(samples: List[Dict[str, Any]], limit: int = 20) -> Optional[float]:
    latencies: List[int] = []
    for s in reversed(samples):
        if len(latencies) >= limit:
            break
        v = s.get("latency_ms")
        if isinstance(v, (int, float)) and v >= 0:
            latencies.append(int(v))
    if not latencies:
        return None
    return sum(latencies) / float(len(latencies))


def aggregate_status() -> Dict[str, Any]:
    pods_status = {p: read_status(p) for p in PODS}

    samples = _vector_recall_samples()
    blackout_active = _detect_vector_blackout(samples)
    mean_latency = _mean_latency_ms(samples)
    recall_degraded = bool(mean_latency is not None and mean_latency > LATENCY_WARN_MS)
    last_latency_ms = None
    for s in reversed(samples):
        if isinstance(s.get("latency_ms"), (int, float)):
            last_latency_ms = int(s["latency_ms"])  # take most recent
            break

    vector_ok = pods_status.get("vector", {}).get("ready") and not pods_status.get(
        "vector", {}
    ).get("error")
    memory_ok = pods_status.get("memory", {}).get("ready") and not pods_status.get(
        "memory", {}
    ).get("error")
    belief_ok = pods_status.get("belief", {}).get("ready") and not pods_status.get(
        "belief", {}
    ).get("error")
    journal_ok = pods_status.get("journal", {}).get("ready") and not pods_status.get(
        "journal", {}
    ).get("error")

    cognitive_ok = bool(
        vector_ok and memory_ok and belief_ok and journal_ok and not blackout_active
    )

    blocked_writes = _blocked_write_count()
    journal_failures = _journal_write_failures()
    belief_failures = _belief_insert_failures()

    # Startup slow per pod: if both start and ready timestamps exist
    startup_slow: Dict[str, bool] = {}
    try:
        for pod in PODS:
            start_file = SIGNAL_DIR / f"{pod}.start"
            ready_file = SIGNAL_DIR / f"{pod}.ready"
            slow = False
            try:
                if start_file.exists() and ready_file.exists():
                    t0 = datetime.fromisoformat(start_file.read_text().strip())
                    t1 = datetime.fromisoformat(ready_file.read_text().strip())
                    slow = (t1 - t0).total_seconds() > STARTUP_SLOW_SEC
            except Exception:
                slow = False
            startup_slow[pod] = bool(slow)
    except Exception:
        pass
    startup_slow_any = any(startup_slow.values()) if startup_slow else False

    # Schema normalization events (drift window)
    drift_count = 0
    try:
        now = datetime.utcnow()
        for fp in _iter_signal_files("*.schema_normalization.*.json"):
            data = _read_json(fp)
            if not data:
                continue
            ts = data.get("ts")
            try:
                if ts and (now - datetime.fromisoformat(ts)).total_seconds() <= DRIFT_WINDOW_SEC:
                    drift_count += 1
            except Exception:
                # If timestamp missing/invalid, ignore
                pass
    except Exception:
        pass

    # Governor signals aggregation (additive)
    governor = {
        "sagas": {},
        "retrieval": {
            "embedding_norms": {},
            "recall_cohorts": {},
            "drift": {},
            "reembed_summary": {},
        },
        "contract_violations": {
            "missing_correlation_id": 0,
            "missing_idempotency_key": 0,
            "missing_provenance": 0,
        },
        "belief": {
            "contradictions": 0,
        },
    }

    # Summarize saga begin/end
    try:
        begins = _iter_signal_files("governor.saga_begin.*.json")
        ends = _iter_signal_files("governor.saga_end.*.json")
        # Count by saga type
        def _saga_name(p: Path) -> str:
            name = p.name
            # governor.saga_begin.WriteMemorySaga.json
            try:
                parts = name.split(".")
                # ['governor','saga_begin','WriteMemorySaga','json']
                return parts[2]
            except Exception:
                return "unknown"

        began: Dict[str, int] = {}
        ended_ok: Dict[str, int] = {}
        ended_err: Dict[str, int] = {}

        for fp in begins[-500:]:
            began[_saga_name(fp)] = began.get(_saga_name(fp), 0) + 1
        for fp in ends[-500:]:
            data = _read_json(fp) or {}
            saga = _saga_name(fp)
            ok = bool((data.get("data") or {}).get("ok"))
            if ok:
                ended_ok[saga] = ended_ok.get(saga, 0) + 1
            else:
                ended_err[saga] = ended_err.get(saga, 0) + 1
        for saga in set(list(began.keys()) + list(ended_ok.keys()) + list(ended_err.keys())):
            governor["sagas"][saga] = {
                "began": int(began.get(saga, 0)),
                "ended_ok": int(ended_ok.get(saga, 0)),
                "ended_err": int(ended_err.get(saga, 0)),
            }
    except Exception:
        pass

    # Embedding stats per namespace (keep last record)
    try:
        for fp in _iter_signal_files("governor.embedding_stats.*.json")[-200:]:
            name = fp.name
            # governor.embedding_stats.<ns>.json
            try:
                ns = name.split(".")[2]
            except Exception:
                ns = "default"
            data = _read_json(fp) or {}
            payload = data.get("data") or {}
            governor["retrieval"]["embedding_norms"][ns] = {
                "mean": float(payload.get("mean") or 0.0),
                "p95": float(payload.get("p95") or 0.0),
                "n": int(payload.get("n") or 0),
            }
    except Exception:
        pass

    # Recall cohorts
    try:
        for fp in _iter_signal_files("governor.recall_cohort.*.json")[-500:]:
            name = fp.name
            # governor.recall_cohort.<ns>.<cohort>.json
            try:
                parts = name.split(".")
                ns, cohort = parts[2], parts[3]
            except Exception:
                ns, cohort = "default", "default"
            data = _read_json(fp) or {}
            payload = data.get("data") or {}
            key = f"{cohort}@{int(payload.get('k') or 0)}"
            rec = float(payload.get("recall") or 0.0)
            if ns not in governor["retrieval"]["recall_cohorts"]:
                governor["retrieval"]["recall_cohorts"][ns] = {}
            governor["retrieval"]["recall_cohorts"][ns][key] = rec
    except Exception:
        pass
    # Retrieval drift per namespace (keep last record)
    try:
        for fp in _iter_signal_files("governor.retrieval_drift.*.json")[-200:]:
            name = fp.name
            # governor.retrieval_drift.<ns>.json
            try:
                ns = name.split(".")[2]
            except Exception:
                ns = "default"
            data = _read_json(fp) or {}
            payload = data.get("data") or {}
            governor["retrieval"]["drift"][ns] = {
                "kl": float(payload.get("kl") or 0.0),
                "cos_shift": float(payload.get("cos_shift") or 0.0),
                "at": data.get("ts"),
            }
    except Exception:
        pass
    # Re-embed summary (last)
    try:
        files = _iter_signal_files("governor.reembed.summary.json")
        if files:
            data = _read_json(files[-1]) or {}
            payload = data.get("data") or {}
            governor["retrieval"]["reembed_summary"] = payload
    except Exception:
        pass

    # Contract violations (soft counters emitted as signals)
    try:
        # Count correlation/idempotency violations
        corr_missing = _iter_signal_files("governor.contract_violation.missing_correlation_id*.json")
        idem_missing = _iter_signal_files("governor.contract_violation.missing_idempotency_key*.json")
        prov_missing = _iter_signal_files("governor.contract_violation.missing_provenance*.json")
        governor["contract_violations"]["missing_correlation_id"] = int(len(corr_missing))
        governor["contract_violations"]["missing_idempotency_key"] = int(len(idem_missing))
        governor["contract_violations"]["missing_provenance"] = int(len(prov_missing))
        # Belief contradiction count
        governor["belief"]["contradictions"] = int(len(_iter_signal_files("governor.belief_contradiction*.json")))
        # Schema violations
        governor["contract_violations"]["schema_violation"] = int(len(_iter_signal_files("governor.contract_violation.schema_violation*.json")))
    except Exception:
        pass

    # Prompt Contracts aggregation (violations in last 5 minutes)
    prompt_contracts: Dict[str, Any] = {"violations_last_5m": {"invalid_json": 0, "schema": 0, "unknown_tool": 0}}
    try:
        now = datetime.utcnow()
        def _count_recent(kind: str) -> int:
            files = _iter_signal_files(f"governor.prompt_contracts.violation.{kind}*.json")
            count = 0
            for fp in files[-500:]:
                data = _read_json(fp) or {}
                ts = data.get("ts")
                try:
                    if ts and (now - datetime.fromisoformat(ts)).total_seconds() <= 300:
                        count += 1
                except Exception:
                    # If timestamp missing/invalid, ignore to keep windowed semantics
                    pass
            return count
        v_inv = _count_recent("invalid_json")
        v_sch = _count_recent("schema")
        v_unk = _count_recent("unknown_tool")
        prompt_contracts["violations_last_5m"]["invalid_json"] = int(v_inv)
        prompt_contracts["violations_last_5m"]["schema"] = int(v_sch)
        prompt_contracts["violations_last_5m"]["unknown_tool"] = int(v_unk)
        prompt_contracts["violations_total"] = int(v_inv + v_sch + v_unk)
    except Exception:
        pass

    # Contracts v2 aggregation (violations in last 5 minutes + version mix)
    contracts_v2: Dict[str, Any] = {
        "violations_5m": {"journal": 0, "memory": 0, "belief": 0},
        "version_mix": {"v2": 0.0, "v1": 0.0},
    }
    try:
        now = datetime.utcnow()
        def _count_recent_contract(kind: str) -> int:
            files = _iter_signal_files(f"contracts_v2.violation.{kind}*.json")
            count = 0
            for fp in files[-500:]:
                data = _read_json(fp) or {}
                ts = data.get("ts")
                try:
                    if ts and (now - datetime.fromisoformat(ts)).total_seconds() <= 300:
                        count += 1
                except Exception:
                    pass
            return count
        contracts_v2["violations_5m"]["journal"] = int(_count_recent_contract("journal"))
        contracts_v2["violations_5m"]["memory"] = int(_count_recent_contract("memory_write"))
        contracts_v2["violations_5m"]["belief"] = int(_count_recent_contract("belief_update"))
        # Version mix from version_seen signals
        seen = _iter_signal_files("contracts_v2.version_seen*.json")
        v2 = 0
        v1 = 0
        total = 0
        for fp in seen[-1000:]:
            data = _read_json(fp) or {}
            vers = (data.get("data") or {}).get("version")
            total += 1
            if vers == "v2":
                v2 += 1
            elif vers == "v1":
                v1 += 1
        if total > 0:
            contracts_v2["version_mix"]["v2"] = float(v2) / float(total)
            contracts_v2["version_mix"]["v1"] = float(v1) / float(total)
    except Exception:
        pass

    # Resilience signals (best-effort)
    try:
        # degraded.active
        degraded_files = _iter_signal_files("resilience.degraded*.json")
        degraded_active = False
        degraded_depth = None
        if degraded_files:
            data = _read_json(degraded_files[-1]) or {}
            d = data.get("data") or {}
            degraded_active = bool(d.get("active"))
            try:
                if d.get("depth") is not None:
                    degraded_depth = int(d.get("depth"))
            except Exception:
                degraded_depth = None
        # budget exceeded counts (windowed by files present)
        be_tokens = len(_iter_signal_files("resilience.budget_exceeded.tokens*.json"))
        be_tools = len(_iter_signal_files("resilience.budget_exceeded.tools*.json"))
        breaker_vector_open = len(_iter_signal_files("resilience.breaker.vector.open*.json"))
        breaker_memory_open = len(_iter_signal_files("resilience.breaker.memory.open*.json"))
        resilience = {
            "budgets": {"tokens_exceeded": be_tokens, "tools_exceeded": be_tools},
            "breakers": {"vector_open_events": breaker_vector_open, "memory_open_events": breaker_memory_open},
            "degraded": {"active": degraded_active, "depth": degraded_depth},
        }
    except Exception:
        resilience = {"budgets": {}, "breakers": {}, "degraded": {"active": False, "depth": None}}

    # Boot signals: last boot_complete/boot_incomplete and version banners (additive)
    boot: Dict[str, Dict[str, Any]] = {}
    try:
        for pod in PODS:
            # version banner (attach inside pods map)
            vb_files = _iter_signal_files(f"{pod}.version_banner.json")
            if vb_files:
                data = _read_json(vb_files[-1]) or {}
                payload = data.get("data") or {}
                try:
                    if pod in pods_status and isinstance(pods_status[pod], dict):
                        pods_status[pod]["version_banner"] = payload
                except Exception:
                    pass
            # boot mode
            bc_files = _iter_signal_files(f"{pod}.boot_complete.json")
            bi_files = _iter_signal_files(f"{pod}.boot_incomplete.json")
            rec = None
            if bc_files:
                data = _read_json(bc_files[-1]) or {}
                rec = {"mode": (data.get("data") or {}).get("mode") or "normal", "at": data.get("ts")}
            elif bi_files:
                data = _read_json(bi_files[-1]) or {}
                rec = {"mode": (data.get("data") or {}).get("mode") or "safe", "at": data.get("ts")}
            if rec:
                boot[pod] = rec
    except Exception:
        pass

    # Lifecycle aggregation (compaction + snapshot) – best-effort
    lifecycle = {
        "compaction": {"last_run": None, "kept": 0, "archived": 0, "bytes_saved": 0},
        "snapshot": {"last_taken_at": None, "last_path": None, "size_bytes": 0, "kept": None},
    }
    try:
        # compaction: look for last completed/ planned signals
        comp_files = _iter_signal_files("lifecycle.lifecycle.compaction.completed*.json")
        if not comp_files:
            comp_files = _iter_signal_files("lifecycle.compaction.completed*.json")
        if comp_files:
            data = _read_json(comp_files[-1]) or {}
            d = (data.get("data") or {})
            lifecycle["compaction"] = {
                "last_run": data.get("ts"),
                "kept": int(d.get("kept") or 0),
                "archived": int(d.get("archived") or 0),
                "bytes_saved": int(d.get("bytes_saved") or 0),
            }
        # snapshot: last taken and prune records
        snap_files = _iter_signal_files("lifecycle.lifecycle.snapshot.taken*.json")
        if not snap_files:
            snap_files = _iter_signal_files("lifecycle.snapshot.taken*.json")
        if snap_files:
            data = _read_json(snap_files[-1]) or {}
            d = (data.get("data") or {})
            lifecycle["snapshot"]["last_taken_at"] = data.get("ts")
            lifecycle["snapshot"]["last_path"] = d.get("path")
            lifecycle["snapshot"]["size_bytes"] = int(d.get("size_bytes") or 0)
        prn_files = _iter_signal_files("lifecycle.lifecycle.snapshot.pruned*.json")
        if not prn_files:
            prn_files = _iter_signal_files("lifecycle.snapshot.pruned*.json")
        if prn_files:
            data = _read_json(prn_files[-1]) or {}
            d = (data.get("data") or {})
            lifecycle["snapshot"]["kept"] = int(d.get("kept") or 0)
    except Exception:
        pass

    # Chaos drill aggregation (best-effort)
    chaos: Dict[str, Any] = {"last_drill": None}
    try:
        # Prefer ended records for outcome; use latest by mtime
        files = _iter_signal_files("chaos.drill.ended*.json")
        if files:
            data = _read_json(files[-1]) or {}
            chaos["last_drill"] = (data.get("data") or {})
        else:
            # Fallback to began record for visibility
            files_b = _iter_signal_files("chaos.drill.began*.json")
            if files_b:
                data = _read_json(files_b[-1]) or {}
                chaos["last_drill"] = (data.get("data") or {})
    except Exception:
        pass

    # CI Canary aggregation (best-effort)
    ci: Dict[str, Any] = {"canary": {"recall": None, "delta": None}}
    try:
        # recall@k
        files_r = _iter_signal_files("ci.canary.recall_at_k*.json")
        if files_r:
            data = _read_json(files_r[-1]) or {}
            payload = data.get("data") or {}
            ci["canary"]["recall"] = float(payload.get("recall") or 0.0)
            ci["canary"]["k"] = int(payload.get("k") or 0)
            ci["canary"]["n"] = int(payload.get("n") or 0)
        # delta
        files_d = _iter_signal_files("ci.canary.delta*.json")
        if files_d:
            data = _read_json(files_d[-1]) or {}
            payload = data.get("data") or {}
            ci["canary"]["delta"] = float(payload.get("delta") or 0.0)
    except Exception:
        pass

    # Blue/Green snapshot (best-effort)
    bluegreen = {"last_switch": None}
    try:
        files = _iter_signal_files("bluegreen.switch*.json")
        if files:
            data = _read_json(files[-1]) or {}
            bluegreen["last_switch"] = data.get("ts")
    except Exception:
        pass

    # Retrieval snapshot (last hits & fallback)
    retrieval_snapshot = {"last_hits": 0, "fallback_used": False, "embedder": None}
    try:
        files = _iter_signal_files("memory.retrieval.json")
        if files:
            data = _read_json(files[-1]) or {}
            payload = (data.get("data") or {})
            retrieval_snapshot["last_hits"] = int(payload.get("last_hits") or 0)
            retrieval_snapshot["fallback_used"] = bool(payload.get("fallback_used"))
    except Exception:
        pass
    # Governor retrieval embedder snapshot (best-effort)
    try:
        files = _iter_signal_files("governor.retrieval.embedder.json")
        if files:
            data = _read_json(files[-1]) or {}
            retrieval_snapshot["embedder"] = (data.get("data") or {})
    except Exception:
        pass

    # Belief backend & patch errors
    beliefs_snapshot = {"backend": None, "patch_errors": 0}
    try:
        files = _iter_signal_files("beliefs.backend.json")
        if files:
            data = _read_json(files[-1]) or {}
            payload = (data.get("data") or {})
            beliefs_snapshot["backend"] = payload.get("backend")
    except Exception:
        pass
    try:
        files = _iter_signal_files("beliefs.patch_error*.json")
        beliefs_snapshot["patch_errors"] = int(len(files))
    except Exception:
        pass

    # Boot canary snapshot
    boot_canary = {"k": None, "recall": None, "min": None, "passed": None}
    try:
        files = _iter_signal_files("memory.boot_canary.json")
        if files:
            data = _read_json(files[-1]) or {}
            payload = (data.get("data") or {})
            boot_canary = {
                "k": int(payload.get("k") or 0),
                "recall": float(payload.get("recall") or 0.0),
                "min": float(payload.get("min") or 0.0) if payload.get("min") is not None else None,
                "passed": bool(payload.get("passed")) if payload.get("passed") is not None else None,
            }
    except Exception:
        pass

    # Config resolver snapshot (best-effort)
    config_snapshot = {"llm": None, "vector": None}
    try:
        files = _iter_signal_files("config.resolver_summary.json")
        if files:
            data = _read_json(files[-1]) or {}
            payload = data.get("data") or {}
            config_snapshot["llm"] = payload.get("llm")
            config_snapshot["vector"] = payload.get("vector")
    except Exception:
        pass

    # Liveness snapshot (best-effort)
    # Eventlog aggregation (best-effort)
    eventlog = {"lag": 0, "processed_5m": 0, "errors_5m": 0}
    try:
        # lag latest value
        files = _iter_signal_files("eventlog.lag*.json")
        if files:
            data = _read_json(files[-1]) or {}
            eventlog["lag"] = int(((data.get("data") or {}).get("value") or 0))
        # windowed counts
        now = datetime.utcnow()
        def _count5(prefix: str) -> int:
            cnt = 0
            for fp in _iter_signal_files(prefix)[-1000:]:
                d = _read_json(fp) or {}
                ts = d.get("ts")
                try:
                    if ts and (now - datetime.fromisoformat(ts)).total_seconds() <= 300:
                        cnt += 1
                except Exception:
                    pass
            return cnt
        eventlog["processed_5m"] = _count5("eventlog.processed*.json")
        eventlog["errors_5m"] = _count5("eventlog.errors*.json")
    except Exception:
        pass

    # Quarantine aggregation (best-effort)
    quarantine = {"flagged_5m": 0, "released_5m": 0, "last_ids": []}
    try:
        now = datetime.utcnow()
        def _count5_q(sig: str) -> int:
            cnt = 0
            for fp in _iter_signal_files(f"quarantine.{sig}*.json")[-500:]:
                d = _read_json(fp) or {}
                ts = d.get("ts")
                try:
                    if ts and (now - datetime.fromisoformat(ts)).total_seconds() <= 300:
                        cnt += 1
                except Exception:
                    pass
            return cnt
        quarantine["flagged_5m"] = _count5_q("flagged")
        quarantine["released_5m"] = _count5_q("released")
    except Exception:
        pass
    liveness = {"recall_ok": None, "recall": None, "belief_patch_ok": None, "belief_status": None}
    try:
        ro = _iter_signal_files("liveness.recall_ok.json")
        rv = _iter_signal_files("liveness.recall_value.json")
        bo = _iter_signal_files("liveness.belief_patch_ok.json")
        bs = _iter_signal_files("liveness.belief_patch_status.json")
        if ro:
            d = _read_json(ro[-1]) or {}
            liveness["recall_ok"] = bool((d.get("data") or {}).get("ok"))
        if rv:
            d = _read_json(rv[-1]) or {}
            liveness["recall"] = float((d.get("data") or {}).get("recall") or 0.0)
        if bo:
            d = _read_json(bo[-1]) or {}
            liveness["belief_patch_ok"] = bool((d.get("data") or {}).get("ok"))
        if bs:
            d = _read_json(bs[-1]) or {}
            liveness["belief_status"] = int((d.get("data") or {}).get("status") or 0)
    except Exception:
        pass

    resp = {
        "pods": pods_status,
        "blackouts": BLACKOUT_FAILS,
        "vector_blackout_active": bool(blackout_active),
        "recall_degraded": bool(recall_degraded),
        "last_vector_latency_ms": last_latency_ms,
        "cognitive_ok": cognitive_ok,
        "config": config_snapshot,
        "liveness": liveness,
        "retrieval": retrieval_snapshot,
        "beliefs": beliefs_snapshot,
        "boot_canary": boot_canary,
        "blocked_writes_by_role": blocked_writes,
        "journal_write_failures": journal_failures,
        "belief_insert_failures": belief_failures,
        "startup_slow": startup_slow,
        "startup_slow_any": bool(startup_slow_any),
        "schema_normalization_events": int(drift_count),
        "governor": governor,
        "prompt_contracts": prompt_contracts,
        "contracts_v2": contracts_v2,
        "generated_at": datetime.utcnow().isoformat(),
        "resilience": resilience,
        "boot": boot,
        "lifecycle": lifecycle,
        "chaos": chaos,
        "ci": ci,
        "bluegreen": bluegreen,
        "eventlog": eventlog,
        "quarantine": quarantine,
    }

    # Attach degradation flags (single source of truth)
    try:
        from .degradation_flags import compute_degradation

        resp["degradation"] = compute_degradation(resp)
    except Exception:
        pass

    # Dispatch alerts if configured (best-effort, throttled)
    try:
        if WEBHOOK_URL:
            _maybe_send_discord_alert(resp)
    except Exception:
        pass

    return resp


_alert_limiters: Dict[str, Any] = {}


def _limiter(name: str, interval_sec: int) -> Any:
    try:
        from .rate_limit import RateLimiter  # relative import
    except Exception:
        # Fallback simple limiter
        class _RL:
            def __init__(self, sec: int):
                self.sec = sec
                self.last = 0

            def allow(self) -> bool:
                import time as _t

                now = _t.time()
                if now - self.last >= self.sec:
                    self.last = now
                    return True
                return False

        RateLimiter = _RL  # type: ignore

    lim = _alert_limiters.get(name)
    if lim is None:
        lim = RateLimiter(300)
        _alert_limiters[name] = lim
    return lim


def _post_webhook(url: str, content: str) -> None:
    try:
        import urllib.request as _rq

        data = json.dumps({"content": content}).encode("utf-8")
        req = _rq.Request(url, data=data, headers={"Content-Type": "application/json"})
        with _rq.urlopen(req, timeout=5) as _:
            return
    except Exception:
        # Log once by suppressing repeated failures via limiter
        if _limiter("webhook_error", 300).allow():
            try:
                print("[cockpit] webhook post failed")
            except Exception:
                pass


def _maybe_send_discord_alert(status: Dict[str, Any]) -> None:
    critical = (
        bool(status.get("vector_blackout_active"))
        or int(status.get("blocked_writes_by_role", 0)) > 0
        or int(status.get("journal_write_failures", 0)) > 0
        or int(status.get("belief_insert_failures", 0)) > 0
    )
    if not critical:
        return
    if not _limiter("degrade_alert", 300).allow():
        return
    pods = status.get("pods", {}) or {}
    def _state(p: str) -> str:
        s = pods.get(p, {})
        if not s:
            return "unknown"
        if not s.get("ready"):
            return "not_ready"
        if s.get("error"):
            return "error"
        if not s.get("heartbeat_ok"):
            return "stale"
        return "ready"

    msg_lines = [
        "🚨 Axiom Degradation",
        f"- vector_blackout_active: {status.get('vector_blackout_active')}",
        f"- blocked_writes_by_role: {status.get('blocked_writes_by_role')}",
        f"- journal_write_failures: {status.get('journal_write_failures')}",
        f"- belief_insert_failures: {status.get('belief_insert_failures')}",
        f"- startup_slow_any: {status.get('startup_slow_any')}",
        f"- schema_normalization_events: {status.get('schema_normalization_events')}",
        f"- recall_degraded: {status.get('recall_degraded')}",
        f"- last_vector_latency_ms: {status.get('last_vector_latency_ms')}",
        f"- pods: llm={_state('llm')}, vector={_state('vector')}, memory={_state('memory')}, belief={_state('belief')}, journal={_state('journal')}",
    ]
    # Optional: include retrieval drift if thresholds exceeded
    try:
        gov = (status.get("governor") or {}).get("retrieval") or {}
        drift = (gov.get("drift") or {})
        max_kl = 0.0
        max_cs = 0.0
        for rec in (drift.values() if isinstance(drift, dict) else []):
            try:
                max_kl = max(max_kl, float((rec or {}).get("kl") or 0.0))
                max_cs = max(max_cs, float((rec or {}).get("cos_shift") or 0.0))
            except Exception:
                continue
        if max_kl > DRIFT_ALERT_KL or max_cs > DRIFT_ALERT_COSINE_SHIFT:
            msg_lines.append(f"- retrieval_drift_kl_max: {max_kl:.4f} (thr {DRIFT_ALERT_KL})")
            msg_lines.append(f"- retrieval_drift_cosine_shift_max: {max_cs:.4f} (thr {DRIFT_ALERT_COSINE_SHIFT})")
    except Exception:
        pass
    _post_webhook(WEBHOOK_URL, "\n".join(msg_lines))


def main() -> int:
    parser = argparse.ArgumentParser(description="Project Cockpit Aggregator")
    parser.add_argument("--summary", action="store_true", help="Print 5-line health summary")
    args = parser.parse_args()
    if args.summary:
        return summary()
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

