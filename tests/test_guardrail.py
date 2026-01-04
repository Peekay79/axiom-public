import unittest

from utils.guardrail import (
    GroundingStatus,
    build_guardrail_reply,
    build_canon_disambiguation_reply,
    build_world_map_persist_reply,
    is_world_map_persist_request,
    should_trigger_guardrail,
    should_trigger_canon_disambiguation,
)


class TestGuardrail(unittest.TestCase):
    def test_guardrail_triggers_on_factual_low_conf_no_world(self):
        g = GroundingStatus(world_injected=False, selected_count=0, retrieved_count=3, top_score=0.40)
        self.assertTrue(
            should_trigger_guardrail(
                enabled=True,
                allow_general_knowledge=False,
                message="Have you heard of Example Project?",
                grounding=g,
                low_score_threshold=0.78,
                min_selected=1,
            )
        )

    def test_guardrail_not_on_creative(self):
        g = GroundingStatus(world_injected=False, selected_count=0, retrieved_count=0, top_score=None)
        self.assertFalse(
            should_trigger_guardrail(
                enabled=True,
                allow_general_knowledge=False,
                message="Write a scene where Douglas arrives.",
                grounding=g,
                low_score_threshold=0.78,
                min_selected=1,
            )
        )

    def test_guardrail_not_when_world_injected(self):
        g = GroundingStatus(world_injected=True, selected_count=0, retrieved_count=0, top_score=None)
        self.assertFalse(
            should_trigger_guardrail(
                enabled=True,
                allow_general_knowledge=False,
                message="What do you know about Alice?",
                grounding=g,
                low_score_threshold=0.78,
                min_selected=1,
            )
        )

    def test_guardrail_not_when_high_conf_vector(self):
        g = GroundingStatus(world_injected=False, selected_count=1, retrieved_count=5, top_score=0.92)
        self.assertFalse(
            should_trigger_guardrail(
                enabled=True,
                allow_general_knowledge=False,
                message="What do you know about the CHAMP algorithm?",
                grounding=g,
                low_score_threshold=0.78,
                min_selected=1,
            )
        )

    def test_guardrail_reply_is_short_and_helpful(self):
        r = build_guardrail_reply("Have you heard of Example Project?")
        self.assertIn("high-confidence", r)
        self.assertIn("world map", r)
        self.assertIn("alias", r)

    def test_meta_questions_do_not_trigger_guardrail(self):
        g = GroundingStatus(world_injected=False, selected_count=0, retrieved_count=0, top_score=None)
        for msg in (
            "What are you interested in talking about?",
            "What info would be useful for your world map?",
            "Tell me a personal memory.",
            "What should we do next?",
        ):
            self.assertFalse(
                should_trigger_guardrail(
                    enabled=True,
                    allow_general_knowledge=False,
                    message=msg,
                    grounding=g,
                    low_score_threshold=0.78,
                    min_selected=1,
                ),
                msg,
            )

    def test_canon_disambiguation_triggers_for_named_entity_when_recall_weak(self):
        g = GroundingStatus(world_injected=False, selected_count=0, retrieved_count=0, top_score=None)
        msg = "What do you know about Example Creature?"
        self.assertTrue(
            should_trigger_canon_disambiguation(message=msg, grounding=g, conf_threshold=0.25)
        )
        r = build_canon_disambiguation_reply(msg)
        self.assertIn("canon", r.lower())
        self.assertIn("real", r.lower())

    def test_world_map_persist_request_detection_and_reply(self):
        self.assertTrue(is_world_map_persist_request("Save this to world map"))
        self.assertTrue(is_world_map_persist_request("Can you update the world map with this?"))
        self.assertFalse(is_world_map_persist_request("What I'm pulling from world map: alice"))
        r = build_world_map_persist_reply()
        self.assertIn("read-only", r.lower())
        self.assertIn("world_map.json".lower(), r.lower())


if __name__ == "__main__":
    unittest.main()
