#!/usr/bin/env python3

import os
import unittest

from pods.memory.pod2_memory_api import app


class TestApiDebug(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def tearDown(self):
        for k in ["AXIOM_BELIEF_ENGINE", "AXIOM_CONTRADICTION_ENABLED", "AXIOM_CONTRADICTIONS", "AXIOM_DEBUG_VERBOSE"]:
            os.environ.pop(k, None)

    def test_belief_debug_flag_off(self):
        os.environ["AXIOM_BELIEF_ENGINE"] = "0"
        r = self.client.get("/belief-debug")
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertIn("belief_engine", data)

    def test_contradictions_redaction_default(self):
        os.environ["AXIOM_BELIEF_ENGINE"] = "1"
        os.environ["AXIOM_CONTRADICTION_ENABLED"] = "1"
        r = self.client.get("/contradictions")
        self.assertIn(r.status_code, (200, 429))  # allow rate-limit in CI
        if r.status_code == 200:
            data = r.get_json()
            self.assertIn("items", data)
            for it in data.get("items", []):
                self.assertNotIn("text", it)

    def test_contradictions_verbose(self):
        os.environ["AXIOM_BELIEF_ENGINE"] = "1"
        os.environ["AXIOM_CONTRADICTION_ENABLED"] = "1"
        os.environ["AXIOM_DEBUG_VERBOSE"] = "1"
        r = self.client.get("/contradictions")
        self.assertIn(r.status_code, (200, 429))


if __name__ == "__main__":
    unittest.main()
