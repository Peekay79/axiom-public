from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Literal


Decision = Literal["act", "wait"]


@dataclass(frozen=True)
class ChampMetrics:
    """
    Synthetic CHAMP inputs for demo purposes.

    Each value is expected to be in [0.0, 1.0].
    """

    confidence: float
    payoff: float
    tempo: float


class ChampDecisionEngine:
    """
    Minimal, dependency-free CHAMP decision engine used by the demo.
    """

    def __init__(self, *, threshold: float = 0.60, weights: Dict[str, float] | None = None) -> None:
        self.threshold = float(threshold)
        self.weights = weights or {"confidence": 0.4, "payoff": 0.4, "tempo": 0.2}

    def score(self, m: ChampMetrics) -> float:
        w = self.weights
        return (
            float(m.confidence) * float(w.get("confidence", 0.0))
            + float(m.payoff) * float(w.get("payoff", 0.0))
            + float(m.tempo) * float(w.get("tempo", 0.0))
        )

    def decide(self, m: ChampMetrics) -> Decision:
        return "act" if self.score(m) >= self.threshold else "wait"

