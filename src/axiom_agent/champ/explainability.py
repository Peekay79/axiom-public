from __future__ import annotations

from typing import Any, Dict

from .engine import ChampDecisionEngine, ChampMetrics, Decision


def explain_champ_decision(metrics: ChampMetrics, decision: Decision) -> Dict[str, Any]:
    """
    Explain the demo CHAMP decision in a simple, structured way.
    """
    engine = ChampDecisionEngine()
    score = engine.score(metrics)
    w = engine.weights
    contributions = {
        "confidence": float(metrics.confidence) * float(w.get("confidence", 0.0)),
        "payoff": float(metrics.payoff) * float(w.get("payoff", 0.0)),
        "tempo": float(metrics.tempo) * float(w.get("tempo", 0.0)),
    }
    return {
        "decision": decision,
        "threshold": engine.threshold,
        "score": score,
        "contributions": contributions,
        "weights": dict(w),
        "inputs": {"confidence": metrics.confidence, "payoff": metrics.payoff, "tempo": metrics.tempo},
    }

