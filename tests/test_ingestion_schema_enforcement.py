from qdrant_payload_schema import PayloadConverter


def test_validate_payload_injects_defaults():
    p = {"text": "hello"}
    out = PayloadConverter.validate_payload(p.copy())
    for k in (
        "source_trust",
        "confidence",
        "times_used",
        "beliefs",
        "memory_type",
        "schema_version",
    ):
        assert k in out
    assert out["beliefs"] == [] and out["memory_type"] == "default"
