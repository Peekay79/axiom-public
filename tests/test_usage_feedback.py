import types
import unittest

import memory_response_pipeline

_MRP_OK = True


class DummyRes:
    def __init__(self, payload=None, vector=None):
        self.payload = payload or {}
        self.vector = vector or [0.0, 0.0, 0.0]


class DummyClient:
    def __init__(self):
        self.updated = {}

    def get_memory_by_id(self, coll, mid, include_vector=False):
        return DummyRes({"times_used": 2, "source_trust": 0.6}, [1.0, 0.0, 0.0])

    def upsert_memory(self, coll, mid, v, p):
        self.updated[mid] = dict(p)
        return True


@unittest.skipUnless(
    _MRP_OK, "memory_response_pipeline unavailable; skipping usage feedback test"
)
class TestUsageFeedback(unittest.TestCase):
    def test_updates_dispatched(self):
        # Patch vector adapter client
        client = DummyClient()
        memory_response_pipeline.vector_adapter.qdrant_client = client  # type: ignore
        # Call updater (non-blocking; give it a moment)
        memory_response_pipeline._async_update_usage(["id-1", "id-2"], trust_nudge=True)
        import time

        time.sleep(0.1)
        self.assertIn("id-1", client.updated)
        self.assertGreaterEqual(client.updated["id-1"].get("times_used", 0), 3)
        self.assertGreaterEqual(client.updated["id-1"].get("source_trust", 0.0), 0.61)


if __name__ == "__main__":
    unittest.main()
