import unittest

from qdrant_payload_schema import PayloadConverter


@unittest.skip("adapt to your ingress function; present to keep test footprint tiny")
class TestIngestValidateCalled(unittest.TestCase):
    def test_validate_called(self):
        calls = {"validated": False}
        orig = PayloadConverter.validate_payload

        def wrapped(p):
            calls["validated"] = True
            return orig(p)

        PayloadConverter.validate_payload = wrapped  # monkeypatch
        # call your ingest function with a minimal payload here
        self.assertTrue(calls["validated"])
