#!/usr/bin/env python3
import json
import unittest
from typing import Any, Dict, List

from memory.metacognition import MetacognitionEngine


class TestMetacognitionEngine(unittest.TestCase):
    def setUp(self):
        MetacognitionEngine.reset()

    def test_usage_tracking_and_summary(self):
        events: List[Dict[str, Any]] = []

        def _hook(ev: Dict[str, Any]) -> None:
            events.append(ev)

        # Use in two distinct domains to drive diversity
        MetacognitionEngine.observe_belief_usage(
            belief_id="b1",
            domain="planning",
            ok=True,
            meta={"i": 1},
            journal_hook=_hook,
        )
        MetacognitionEngine.observe_belief_usage(
            belief_id="b2",
            domain="safety",
            ok=True,
            meta={"i": 2},
            journal_hook=_hook,
        )

        summary = MetacognitionEngine.export_summary()
        self.assertIn("domains", summary)
        self.assertGreaterEqual(summary.get("abstraction_score", 0.0), 0.0)
        self.assertLessEqual(summary.get("abstraction_score", 1.0), 1.0)
        self.assertEqual(summary["domains"].get("planning", 0), 1)
        self.assertEqual(summary["domains"].get("safety", 0), 1)

        # With 2 domains observed and 2 total, abstraction_score should be high and trigger at least one event
        self.assertTrue(
            any(ev.get("type") == "metacognition.generalisation" for ev in events)
        )


if __name__ == "__main__":
    unittest.main()
