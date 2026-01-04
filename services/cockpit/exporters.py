from __future__ import annotations

from typing import Dict, Any


def as_metrics(status_json: Dict[str, Any]) -> Dict[str, float]:
    d = status_json.get("degradation", {}) or {}
    def _g(name: str) -> float:
        return 1.0 if bool(d.get(name)) else 0.0

    metrics = {
        "cockpit.cognitive_ok": 1.0 if d.get("cognitive_ok") else 0.0,
        "cockpit.vector_blackout_active": _g("vector_blackout_active"),
        "cockpit.recall_degraded": _g("recall_degraded"),
        "cockpit.memory_persistence_blocked": _g("memory_persistence_blocked"),
        "cockpit.belief_pipeline_unready": _g("belief_pipeline_unready"),
        "cockpit.journal_pipeline_unready": _g("journal_pipeline_unready"),
        "cockpit.startup_slow_any": _g("startup_slow_any"),
        "cockpit.memory_schema_drift_active": _g("memory_schema_drift_active"),
        "cockpit.last_vector_latency_ms": float(status_json.get("last_vector_latency_ms") or 0),
        "cockpit.governor.contracts_weak": _g("contracts_weak"),
    }
    # Chaos optional gauges
    try:
        ch = status_json.get("chaos", {}) or {}
        last = ch.get("last_drill") or {}
        if isinstance(last, dict):
            dur = last.get("duration")
            if dur is not None:
                try:
                    metrics["cockpit.chaos.last_duration_sec"] = float(dur)
                except Exception:
                    metrics["cockpit.chaos.last_duration_sec"] = 0.0
    except Exception:
        pass
    # CI canary optional gauges
    try:
        ci = status_json.get("ci", {}) or {}
        can = (ci.get("canary") or {})
        rec = can.get("recall")
        if rec is not None:
            metrics["cockpit.ci.canary_recall"] = float(rec)
        delt = can.get("delta")
        if delt is not None:
            metrics["cockpit.ci.canary_delta"] = float(delt)
    except Exception:
        pass
    # Boot gauges (additive)
    try:
        boot = status_json.get("boot", {}) or {}
        # Flatten: count modes per pod into simple gauges
        for pod, rec in (boot.items() if isinstance(boot, dict) else []):
            mode = (rec or {}).get("mode")
            if mode:
                key = f"cockpit.boot.mode_normal.{pod}"
                metrics[key] = 1.0 if mode == "normal" else 0.0
        # Degraded active from resilience is already exported; also surface any degraded mode present
        any_degraded = any((isinstance(rec, dict) and rec.get("mode") == "degraded") for rec in (boot.values() if isinstance(boot, dict) else []))
        metrics["cockpit.boot.degraded_active"] = 1.0 if any_degraded else 0.0
    except Exception:
        pass
    # Resilience gauges (best-effort)
    try:
        r = status_json.get("resilience", {}) or {}
        dg = (r.get("degraded") or {})
        metrics["cockpit.resilience.degraded_active"] = 1.0 if bool(dg.get("active")) else 0.0
        # breaker open gauges (presence of recent open events)
        brk = (r.get("breakers") or {})
        metrics["cockpit.resilience.breaker_open_vector"] = 1.0 if int(brk.get("vector_open_events") or 0) > 0 else 0.0
        metrics["cockpit.resilience.breaker_open_memory"] = 1.0 if int(brk.get("memory_open_events") or 0) > 0 else 0.0
        # budget exceeded counts as counters this scrape
        bud = (r.get("budgets") or {})
        metrics["cockpit.resilience.budget_exceeded_tokens"] = float(int(bud.get("tokens_exceeded") or 0))
        metrics["cockpit.resilience.budget_exceeded_tools"] = float(int(bud.get("tools_exceeded") or 0))
    except Exception:
        pass
    # Optional Belief Governance gauge
    try:
        bm = status_json.get("belief_metrics", {}) or {}
        avg = bm.get("avg_confidence")
        if avg is not None:
            metrics["beliefs.avg_confidence"] = float(avg)
    except Exception:
        pass
    # Retrieval gauges (optional)
    try:
        gov = (status_json.get("governor") or {}).get("retrieval") or {}
        reb = gov.get("reembed_summary") or {}
        decision = (reb.get("decision") or "").lower()
        metrics["cockpit.retrieval.reembed_last_pass"] = 1.0 if decision == "pass" else 0.0
        # Prefer KL from reembed summary; else max drift KL across namespaces
        kl = reb.get("kl")
        if kl is None:
            drift = gov.get("drift") or {}
            kl_vals = []
            for rec in (drift.values() if isinstance(drift, dict) else []):
                try:
                    kl_vals.append(float((rec or {}).get("kl") or 0.0))
                except Exception:
                    continue
            kl = max(kl_vals) if kl_vals else 0.0
        metrics["cockpit.retrieval.kl"] = float(kl or 0.0)
        metrics["cockpit.retrieval.recall_delta"] = float(reb.get("recall_delta") or 0.0)
        # Embedder registry counters (best-effort)
        try:
            rs = status_json.get("retrieval") or {}
            emb = rs.get("embedder") or {}
            if emb:
                metrics["cockpit.governor.retrieval.embedder_dim"] = float(int(emb.get("dim") or 0))
        except Exception:
            pass
    except Exception:
        pass
    # Lifecycle optional gauges
    try:
        lc = status_json.get("lifecycle", {}) or {}
        comp = lc.get("compaction", {}) or {}
        snap = lc.get("snapshot", {}) or {}
        metrics["cockpit.lifecycle.compaction_bytes_saved"] = float(comp.get("bytes_saved") or 0.0)
        metrics["cockpit.lifecycle.snapshot_last_size_bytes"] = float(snap.get("size_bytes") or 0.0)
    except Exception:
        pass
    # Prompt Contracts gauges (optional)
    try:
        pc = status_json.get("prompt_contracts", {}) or {}
        v = (pc.get("violations_last_5m") or {})
        total = float(int(pc.get("violations_total") or 0))
        metrics["cockpit.prompt_contracts.violations_total"] = total
        metrics["cockpit.prompt_contracts.invalid_json_5m"] = float(int(v.get("invalid_json") or 0))
        metrics["cockpit.prompt_contracts.schema_5m"] = float(int(v.get("schema") or 0))
        metrics["cockpit.prompt_contracts.unknown_tool_5m"] = float(int(v.get("unknown_tool") or 0))
    except Exception:
        pass
    # Contracts v2 gauges (optional)
    try:
        c2 = status_json.get("contracts_v2", {}) or {}
        vio = (c2.get("violations_5m") or {})
        metrics["cockpit.contracts_v2.violations_5m.journal"] = float(int(vio.get("journal") or 0))
        metrics["cockpit.contracts_v2.violations_5m.memory"] = float(int(vio.get("memory") or 0))
        metrics["cockpit.contracts_v2.violations_5m.belief"] = float(int(vio.get("belief") or 0))
        vm = (c2.get("version_mix") or {})
        metrics["cockpit.contracts_v2.version_mix.v2"] = float(vm.get("v2") or 0.0)
        metrics["cockpit.contracts_v2.version_mix.v1"] = float(vm.get("v1") or 0.0)
    except Exception:
        pass
    # Liveness gauges (optional)
    try:
        liv = status_json.get("liveness", {}) or {}
        metrics["cockpit.liveness.recall_ok"] = 1.0 if bool(liv.get("recall_ok")) else 0.0
        if liv.get("recall") is not None:
            metrics["cockpit.liveness.recall"] = float(liv.get("recall") or 0.0)
        metrics["cockpit.liveness.belief_patch_ok"] = 1.0 if bool(liv.get("belief_patch_ok")) else 0.0
        if liv.get("belief_status") is not None:
            metrics["cockpit.liveness.belief_patch_status"] = float(int(liv.get("belief_status") or 0))
    except Exception:
        pass
    # Blue/Green switch event counter (optional; exported as 1 on last switch scrape)
    try:
        # Represent last switch presence as a gauge for simplicity
        bg = status_json.get("bluegreen", {}) or {}
        last_switched = 1.0 if bool(bg.get("last_switch")) else 0.0
        metrics["cockpit.bluegreen.last_switch"] = float(last_switched)
    except Exception:
        pass
    # Eventlog gauges
    try:
        ev = status_json.get("eventlog", {}) or {}
        metrics["cockpit.eventlog.lag"] = float(int(ev.get("lag") or 0))
        metrics["cockpit.eventlog.processed_5m"] = float(int(ev.get("processed_5m") or 0))
        metrics["cockpit.eventlog.errors_5m"] = float(int(ev.get("errors_5m") or 0))
    except Exception:
        pass
    # Quarantine gauges
    try:
        q = status_json.get("quarantine", {}) or {}
        metrics["cockpit.quarantine.flagged_5m"] = float(int(q.get("flagged_5m") or 0))
        metrics["cockpit.quarantine.released_5m"] = float(int(q.get("released_5m") or 0))
    except Exception:
        pass
    return metrics

