#!/usr/bin/env python3
# AUDIT: Contradiction Pipeline – metacognition.py
# - Purpose: Observe belief usage, compute abstraction score, optionally detect contradictions from failures.
# - Findings:
#   - ✅ Async: detect_contradictions awaits external engine call correctly.
#   - ⚠️ External dependency: imports top-level contradiction_engine.detect_contradictions, not memory.*; potential API skew.
#   - ⚠️ Journal schema: uses type "metacognition.generalisation"; ensure dashboards recognize it.
#   - Cleanup target: expose public API for contradiction detection through memory.* to reduce coupling.
"""
Metacognition Engine (Phase 1)

A minimal, additive metacognition subsystem that observes belief usage across domains,
computes a simple cross-domain abstraction score, and logs generalisation events via
an external journal hook.

Design goals:
- Purely in-memory state; no persistence or external dependencies
- Safe to import; does nothing unless methods are called explicitly
- Explicit TODO markers for Phase 2 work (avoid feature creep)

Inspiration: July 2025 Harvard paper "What Has a Foundation Model Found? Using
Inductive Bias to Probe for World Models" (Vafa et al.) suggesting that LLMs often
fail to form coherent world models. This module scaffolds transferable reasoning and
cross-domain abstraction by observing belief reuse and signaling generalisation opportunities.
"""
from __future__ import annotations

import json
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

JournalHook = Callable[[Dict[str, Any]], None]
BeliefLookup = Optional[Callable[[str], Optional[Dict[str, Any]]]]


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class _UsageEvent:
    belief_id: str
    domain: str
    ok: bool
    meta: Dict[str, Any]
    at: str


class MetacognitionEngine:
    """Minimal metacognition engine.

    Tracks belief usage by domain and computes a simple abstraction score: the
    Jaccard diversity of domains where distinct beliefs have been used recently.

    Public API (Phase 1):
    - observe_belief_usage(...): record success/failure usage by domain
    - record_failure(...): shortcut for failed usage
    - detect_contradictions(): stub for Phase 2 (returns [])
    - export_summary(): minimal telemetry/instrumentation
    - _demo(): smoke test for module standalone run
    """

    # In-memory state (class-level for simplicity and global visibility)
    _domain_usage: Dict[str, int] = {}
    _belief_usage_by_domain: Dict[str, Dict[str, int]] = {}
    _recent_events: List[_UsageEvent] = []
    _recent_failures: List[_UsageEvent] = []
    _last_score: float = 0.0
    _last_score_at: Optional[str] = None

    @classmethod
    def reset(cls) -> None:
        """Reset all in-memory state. Useful for tests/demo runs."""
        cls._domain_usage = {}
        cls._belief_usage_by_domain = {}
        cls._recent_events = []
        cls._recent_failures = []
        cls._last_score = 0.0
        cls._last_score_at = None

    @classmethod
    def observe_belief_usage(
        cls,
        *,
        belief_id: str,
        domain: str,
        ok: bool,
        meta: Optional[Dict[str, Any]] = None,
        journal_hook: Optional[JournalHook] = None,
        belief_lookup: BeliefLookup = None,
    ) -> None:
        """Record a belief usage event.

        - belief_id: identifier of the applied belief
        - domain: arbitrary domain/category string (e.g., "planning", "safety")
        - ok: True if application succeeded; False if failed
        - meta: optional small metadata dict (will be JSON-serialised if logged)
        - journal_hook: optional callable that accepts a dict; used for logging
        - belief_lookup: optional callable mapping belief_id -> belief dict
        """
        if not belief_id or not domain:
            return
        meta = meta or {}
        # Update usage counters
        cls._domain_usage[domain] = cls._domain_usage.get(domain, 0) + 1
        bd = cls._belief_usage_by_domain.setdefault(domain, {})
        bd[belief_id] = bd.get(belief_id, 0) + 1
        # Record event
        event = _UsageEvent(
            belief_id=belief_id, domain=domain, ok=ok, meta=meta, at=_iso_now()
        )
        cls._recent_events.append(event)
        if not ok:
            cls._recent_failures.append(event)

        # Recompute abstraction score and maybe log a generalisation event
        score = cls._compute_abstraction_score()
        cls._last_score = score
        cls._last_score_at = _iso_now()
        if score >= 0.75 and journal_hook is not None:
            payload: Dict[str, Any] = {
                "type": "metacognition.generalisation",
                "score": round(score, 3),
                "domain_usage": dict(cls._domain_usage),
                "belief": None,
                "belief_id": belief_id,
                "domain": domain,
                "at": _iso_now(),
                "meta": meta,
            }
            if belief_lookup is not None:
                try:
                    payload["belief"] = belief_lookup(belief_id)
                except Exception:
                    payload["belief"] = None
            try:
                journal_hook(payload)
            except Exception:
                # Do not raise from observer path
                pass

    @classmethod
    def record_failure(
        cls,
        *,
        belief_id: str,
        domain: str,
        meta: Optional[Dict[str, Any]] = None,
        journal_hook: Optional[JournalHook] = None,
        belief_lookup: BeliefLookup = None,
    ) -> None:
        """Convenience helper to record a failed belief application."""
        cls.observe_belief_usage(
            belief_id=belief_id,
            domain=domain,
            ok=False,
            meta=meta,
            journal_hook=journal_hook,
            belief_lookup=belief_lookup,
        )

    @classmethod
    def _compute_abstraction_score(cls) -> float:
        """Compute a simple cross-domain abstraction score in [0, 1].

                        We define cross-domain diversity as the Jaccard index of the set of domains
                        applied recently relative to the total possible domains observed historically.
                        Given we do not track a closed world of domains, we normalise by a proxy:
                        - numerator: number of domains used in the last N events (distinct)
                        - denominator: total distinct domains observed across all time

                        This produces a monotonic score that increases as usage spans multiple

        domains. It is simple, interpretable, and stable.
        """
        if not cls._domain_usage:
            return 0.0
        # Recent window: last 50 events (adjustable constant for Phase 1)
        window = cls._recent_events[-50:]
        recent_domains = {e.domain for e in window}
        all_domains = set(cls._domain_usage.keys())
        if not all_domains:
            return 0.0
        jaccard = len(recent_domains) / max(1, len(all_domains))
        return float(max(0.0, min(1.0, jaccard)))

    @classmethod
    async def detect_contradictions(cls) -> List[Dict[str, Any]]:
        """Detect contradictions from recent failures using the contradiction engine.
        Returns a list of contradiction dicts.
        """
        try:
            from contradiction_engine import detect_contradictions as _detect
        except Exception:
            return []
        # Build a minimal entry and pass recent failures as memories
        entry = {
            "type": "metacognition_probe",
            "timestamp": _iso_now(),
            "content": "metacog failure scan",
        }
        failures_as_memories: List[Dict[str, Any]] = [
            asdict(e) for e in cls._recent_failures[-25:]
        ]
        try:
            contradictions = await _detect(entry, failures_as_memories)
            if contradictions:
                import logging

                logging.getLogger("metacognition").warning(
                    f"[Metacog] Contradictions found: {len(contradictions)}"
                )
            return contradictions or []
        except Exception:
            return []

    @classmethod
    def export_summary(cls) -> Dict[str, Any]:
        """Return minimal telemetry snapshot for observability."""
        return {
            "type": "metacognition.summary",
            "at": _iso_now(),
            "abstraction_score": round(float(cls._last_score), 3),
            "abstraction_score_at": cls._last_score_at,
            "domains": dict(cls._domain_usage),
            "belief_usage_by_domain": {
                k: dict(v) for k, v in cls._belief_usage_by_domain.items()
            },
            "recent_events": [asdict(e) for e in cls._recent_events[-10:]],
            "recent_failures": [asdict(e) for e in cls._recent_failures[-10:]],
        }

    @classmethod
    def _demo(cls) -> None:
        """Run a simple smoke test demonstrating usage tracking and summary export."""
        print("[MetacognitionEngine] Demo starting...", file=sys.stderr)
        cls.reset()

        # Fake journal hook that prints to stdout
        def _journal_hook(event: Dict[str, Any]) -> None:
            payload = dict(event)
            payload["demo"] = True
            print(json.dumps(payload, ensure_ascii=False))

        # Optional fake belief lookup
        def _lookup(bid: str) -> Dict[str, Any]:
            return {"id": bid, "text": f"Belief {bid}", "scope": "general"}

        # Simulate some usage across domains
        for i in range(3):
            cls.observe_belief_usage(
                belief_id=f"b{i}",
                domain="planning" if i % 2 == 0 else "safety",
                ok=True,
                meta={"demo": i},
                journal_hook=_journal_hook,
                belief_lookup=_lookup,
            )
        # Add a third domain to trigger high abstraction
        cls.observe_belief_usage(
            belief_id="bX",
            domain="ethics",
            ok=True,
            meta={"note": "broad usage"},
            journal_hook=_journal_hook,
            belief_lookup=_lookup,
        )
        # One failure
        cls.record_failure(
            belief_id="b_fail",
            domain="planning",
            meta={"reason": "constraint_violation"},
            journal_hook=_journal_hook,
            belief_lookup=_lookup,
        )
        # Export summary
        print(json.dumps(cls.export_summary(), ensure_ascii=False))
        print("[MetacognitionEngine] Demo complete.", file=sys.stderr)


if __name__ == "__main__":
    # Simple CLI entry point: run demo
    MetacognitionEngine._demo()
