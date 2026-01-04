import unittest

try:
    from memory_response_pipeline import _auto_profile

    export_ok = True
except Exception:
    export_ok = False
    _auto_profile = None  # type: ignore


@unittest.skipUnless(
    export_ok, "memory_response_pipeline unavailable; skipping auto profile test"
)
class TestAutoProfile(unittest.TestCase):
    def test_auto_profile_rules(self):
        self.assertEqual(_auto_profile("latest jobs report today"), "news")
        self.assertEqual(_auto_profile("stack trace error: TypeError"), "code")
        self.assertEqual(_auto_profile("prove the lemma of"), "evergreen")


if __name__ == "__main__":
    unittest.main()
