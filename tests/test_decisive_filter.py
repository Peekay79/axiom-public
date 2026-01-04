import unittest

try:
    from memory_response_pipeline import call_llm_decisive_filter

    _MRP_OK = True
except Exception:
    _MRP_OK = False
    call_llm_decisive_filter = None  # type: ignore


@unittest.skipUnless(
    _MRP_OK, "memory_response_pipeline unavailable; skipping decisive filter tests"
)
class TestDecisiveFilter(unittest.TestCase):
    def test_parse_ids(self):
        # This test just ensures the helper tolerates empty input and returns list
        import asyncio

        res = asyncio.get_event_loop().run_until_complete(
            call_llm_decisive_filter([], target_n=4)
        )
        self.assertEqual(res, [])


if __name__ == "__main__":
    unittest.main()
