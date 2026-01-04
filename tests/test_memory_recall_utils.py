import unittest
from dataclasses import dataclass

from utils.memory_recall import build_memory_banner, select_hits_for_recall_block


@dataclass
class _Hit:
    score: float
    content: str
    raw: dict


class TestMemoryRecallUtils(unittest.TestCase):
    def test_banner_none_only_when_retrieved_zero(self) -> None:
        msg = build_memory_banner(
            retrieved_count=0,
            selected_count=0,
            top_score=0.0,
            conf_threshold=0.25,
        )
        self.assertIn("(none)", msg)

        msg2 = build_memory_banner(
            retrieved_count=6,
            selected_count=6,
            top_score=0.9,
            conf_threshold=0.25,
        )
        self.assertNotIn("(none)", msg2)

        msg3 = build_memory_banner(
            retrieved_count=6,
            selected_count=0,
            top_score=0.9,
            conf_threshold=0.25,
        )
        self.assertNotIn("(none)", msg3)

    def test_banner_moderate_confidence_message_only_when_selected_and_below_threshold(self) -> None:
        msg = build_memory_banner(
            retrieved_count=3,
            selected_count=2,
            top_score=0.2,
            conf_threshold=0.25,
        )
        self.assertIn("confidence is moderate", msg)
        self.assertIn("2 selected of 3 retrieved", msg)

        msg2 = build_memory_banner(
            retrieved_count=3,
            selected_count=2,
            top_score=0.25,
            conf_threshold=0.25,
        )
        self.assertNotIn("confidence is moderate", msg2)
        self.assertIn("2 selected of 3 retrieved", msg2)

    def test_select_hits_dedup_by_fingerprint_and_keep_diversity(self) -> None:
        hits = [
            _Hit(
                score=0.9,
                content="Max has a fossil collection: trilobite, ammonite, megalodon tooth.",
                raw={"payload": {"fingerprint": "fp1"}},
            ),
            _Hit(
                score=0.85,
                content="Max has a fossil collection: trilobite, ammonite, megalodon tooth.",
                raw={"payload": {"fingerprint": "fp1"}},
            ),
            _Hit(
                score=0.8,
                content="Other items include amber with insect inclusions and a stone-age arrowhead.",
                raw={"payload": {"fingerprint": "fp2"}},
            ),
        ]

        selected, block = select_hits_for_recall_block(
            hits, max_items=6, max_chars=1600, per_item_max_chars=220
        )
        # fp1 should appear once, fp2 once
        self.assertEqual(len(selected), 2)
        self.assertIn("Relevant memories:", block)


if __name__ == "__main__":
    unittest.main()
