import os
import unittest

try:
    from memory.scoring import composite_score, load_weights

    _SCORING_OK = True
except Exception:
    _SCORING_OK = False
    composite_score = None  # type: ignore
    load_weights = None  # type: ignore


@unittest.skipUnless(
    _SCORING_OK, "scoring module unavailable; skipping belief signal tests"
)
class TestBeliefSignals(unittest.TestCase):
    def setUp(self):
        # Minimal query vector
        self.qv = [1.0, 0.0, 0.0]
        self.weights = load_weights("default")
        self.weights["w_sim"] = 0.0  # isolate multiplier effects
        self.weights["w_bel"] = 1.0
        self.weights["beliefs_enabled"] = True
        self.weights["contradictions_enabled"] = True
        self.weights["belief_conflict_penalty"] = 0.08

    def _mk(self, beliefs=None, extra=None):
        m = {
            "id": "m1",
            "timestamp": "2025-01-01T00:00:00Z",
            "source_trust": 0.6,
            "confidence": 0.5,
            "times_used": 0,
            "beliefs": beliefs or [],
            "_vector": self.qv,
        }
        if extra:
            m.update(extra)
        return m

    def test_belief_overlap_increases_score(self):
        os.environ["AXIOM_CONTRADICTION_ENABLED"] = "0"
        # Seed cache directly
        from memory import scoring as sc

        sc._ACTIVE_BELIEFS = {"safety", "alignment"}
        m_neutral = self._mk(beliefs=["unrelated"])
        m_overlap = self._mk(beliefs=["alignment"])  # overlaps active
        score_neutral, _ = composite_score(m_neutral, self.qv, w=self.weights)
        score_overlap, _ = composite_score(m_overlap, self.qv, w=self.weights)
        self.assertGreater(score_overlap, score_neutral)

    def test_contradiction_penalty_reduces_score(self):
        os.environ["AXIOM_CONTRADICTION_ENABLED"] = "1"
        from memory import scoring as sc

        sc._ACTIVE_BELIEFS = {"core"}
        base = self._mk(beliefs=["core"])
        penalized = self._mk(beliefs=["core"], extra={"contradiction_flag": True})
        b_score, _ = composite_score(base, self.qv, w=self.weights)
        p_score, _ = composite_score(penalized, self.qv, w=self.weights)
        self.assertLess(p_score, b_score)


if __name__ == "__main__":
    unittest.main()
