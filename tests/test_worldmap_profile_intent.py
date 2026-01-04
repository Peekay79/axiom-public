import unittest

from utils.worldmap_profile import is_profile_intent, resolve_profile_entity_id


class TestWorldMapProfileIntent(unittest.TestCase):
    def test_profile_intent_startswith(self):
        self.assertTrue(is_profile_intent("Who is ExamplePerson?"))
        self.assertTrue(is_profile_intent("tell me about axiom"))

    def test_profile_intent_contains(self):
        self.assertTrue(is_profile_intent("what about my kids lately"))
        self.assertTrue(is_profile_intent("AXIOM status"))

    def test_profile_intent_negative(self):
        self.assertFalse(is_profile_intent("please write a scene where they travel"))
        self.assertFalse(is_profile_intent("hello there"))

    def test_entity_resolution(self):
        self.assertEqual(resolve_profile_entity_id("Tell me about ExamplePerson"), "example_person")
        self.assertEqual(resolve_profile_entity_id("axiom, what is your role"), "axiom")
        self.assertEqual(resolve_profile_entity_id("maxi is great"), "max")
        self.assertEqual(resolve_profile_entity_id("Max is great"), "max")
        self.assertEqual(resolve_profile_entity_id("Leo did it"), "leo")
        self.assertEqual(resolve_profile_entity_id("Heather is here"), "hev")
        self.assertEqual(resolve_profile_entity_id("hev says hi"), "hev")

    def test_entity_resolution_none(self):
        self.assertIsNone(resolve_profile_entity_id("tell me about our plans"))


if __name__ == "__main__":
    unittest.main()
