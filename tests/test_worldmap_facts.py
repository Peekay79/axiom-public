import unittest


from utils.worldmap_facts import extract_kurt_hard_facts


class TestWorldmapFacts(unittest.TestCase):
    def test_extract_wife_name_explicit(self):
        txt = "ExamplePerson's wife's name is Hev."
        ops = extract_kurt_hard_facts(txt)
        self.assertTrue(any(o.get("path") == "/wife_name" for o in ops))
        op = [o for o in ops if o.get("path") == "/wife_name"][0]
        self.assertEqual(op.get("op"), "replace")
        self.assertEqual(op.get("value"), "Hev")
        self.assertEqual(op.get("confidence"), 0.95)
        self.assertIn(op.get("extracted_span"), txt)

    def test_extract_kid_age_explicit(self):
        txt = "Leo is now 6."
        ops = extract_kurt_hard_facts(txt)
        self.assertTrue(any(o.get("path") == "/kids" for o in ops))
        op = [o for o in ops if o.get("path") == "/kids"][0]
        self.assertEqual(op.get("op"), "add")
        self.assertEqual(op.get("value"), {"name": "Leo", "age": 6})
        spans = op.get("extracted_spans") or []
        self.assertIn("Leo", spans)
        self.assertIn("6", spans)
        for s in spans:
            self.assertIn(s, txt)

    def test_does_not_extract_hedged_statement(self):
        txt = "I think ExamplePerson's wife's name is Hev."
        ops = extract_kurt_hard_facts(txt)
        self.assertEqual(ops, [])

    def test_extracted_span_is_literal_substring(self):
        txt = "ExamplePerson was born in Ipswich."
        ops = extract_kurt_hard_facts(txt)
        for op in ops:
            span = op.get("extracted_span")
            if isinstance(span, str) and span:
                self.assertIn(span, txt)


if __name__ == "__main__":
    unittest.main()

