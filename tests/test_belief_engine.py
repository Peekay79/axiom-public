#!/usr/bin/env python3

import os
import unittest

os.environ["AXIOM_BELIEF_TAGGER"] = "heuristic"

from memory.belief_engine import (
    KEY_VERSION,
    belief_alignment_score,
    canonicalize_belief_text,
    detect_contradictions,
    ensure_structured_beliefs,
    extract_beliefs_from_text,
)


class TestBeliefEngine(unittest.TestCase):
    def test_canonicalize(self):
        k1, n1, v1 = canonicalize_belief_text("Humans should guide AI development")
        k2, n2, v2 = canonicalize_belief_text(
            "humans SHOULD guide artificial intelligence development"
        )
        self.assertEqual(k1, k2)
        self.assertIn("should", n1)
        self.assertEqual(v1, KEY_VERSION)
        self.assertEqual(v2, KEY_VERSION)

    def test_extract_beliefs(self):
        bs = extract_beliefs_from_text("AI should be helpful to people")
        self.assertTrue(bs)
        b = bs[0]
        self.assertIn(b.polarity, (-1, 0, 1))
        self.assertTrue(0.0 <= b.confidence <= 1.0)
        self.assertEqual(b.key_version, KEY_VERSION)
        self.assertTrue(b.scope and isinstance(b.scope, str))

    def test_alignment_scope(self):
        # aligned in same scope ~1.0
        cand = ensure_structured_beliefs(
            [
                {
                    "key": "ai_should_help_people",
                    "text": "",
                    "polarity": 1,
                    "confidence": 0.8,
                    "scope": "general",
                    "source": "ingest",
                    "last_updated": "2025-01-02T00:00:00Z",
                    "key_version": KEY_VERSION,
                }
            ]
        )
        active = ensure_structured_beliefs(
            [
                {
                    "key": "ai_should_help_people",
                    "text": "",
                    "polarity": 1,
                    "confidence": 0.8,
                    "scope": "general",
                    "source": "seed",
                    "last_updated": "2025-01-01T00:00:00Z",
                    "key_version": KEY_VERSION,
                }
            ]
        )
        self.assertAlmostEqual(belief_alignment_score(cand, active), 1.0, places=3)
        # conflicting within same scope reduces score
        active_conflict = ensure_structured_beliefs(
            [
                {
                    "key": "ai_should_help_people",
                    "text": "",
                    "polarity": -1,
                    "confidence": 0.8,
                    "scope": "general",
                    "source": "seed",
                    "last_updated": "2025-01-01T00:00:00Z",
                    "key_version": KEY_VERSION,
                }
            ]
        )
        self.assertLess(belief_alignment_score(cand, active_conflict), 1.0)
        # neutral across different scopes
        active_other_scope = ensure_structured_beliefs(
            [
                {
                    "key": "ai_should_help_people",
                    "text": "",
                    "polarity": -1,
                    "confidence": 0.8,
                    "scope": "project:123",
                    "source": "seed",
                    "last_updated": "2025-01-01T00:00:00Z",
                    "key_version": KEY_VERSION,
                }
            ]
        )
        same = belief_alignment_score(cand, active_other_scope)
        self.assertAlmostEqual(same, 1.0, places=3)

    def test_contradictions(self):
        items = ensure_structured_beliefs(
            [
                {
                    "key": "ai_should_help_people",
                    "text": "",
                    "polarity": 1,
                    "confidence": 0.8,
                    "scope": "general",
                    "source": "seed",
                    "last_updated": "2025-01-01T00:00:00Z",
                    "key_version": KEY_VERSION,
                },
                {
                    "key": "ai_should_help_people",
                    "text": "",
                    "polarity": -1,
                    "confidence": 0.8,
                    "scope": "general",
                    "source": "seed",
                    "last_updated": "2025-01-02T00:00:00Z",
                    "key_version": KEY_VERSION,
                },
            ]
        )
        cons = detect_contradictions(items)
        self.assertTrue(cons)
        self.assertEqual(cons[0]["key"], "ai_should_help_people")
        self.assertEqual(cons[0]["key_version"], KEY_VERSION)


if __name__ == "__main__":
    unittest.main()
