import unittest

import memory_response_pipeline

_MRP_OK = True


@unittest.skipUnless(
    _MRP_OK, "memory_response_pipeline unavailable; skipping auto profile tests"
)
class TestAutoProfile(unittest.TestCase):
    def test_news(self):
        self.assertEqual(memory_response_pipeline._auto_profile("What happened today?"), "news")

    def test_evergreen(self):
        self.assertEqual(
            memory_response_pipeline._auto_profile("prove the theorem of complexity"), "evergreen"
        )

    def test_code(self):
        self.assertEqual(
            memory_response_pipeline._auto_profile("python stack trace error: ValueError"), "code"
        )

    def test_personal(self):
        self.assertEqual(
            memory_response_pipeline._auto_profile("In my journal I wrote about how I feel today"),
            "personal",
        )

    def test_default(self):
        self.assertEqual(memory_response_pipeline._auto_profile("random query"), "default")


if __name__ == "__main__":
    unittest.main()
