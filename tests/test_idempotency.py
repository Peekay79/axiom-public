from pods.memory.idempotency import canonical_fingerprint, stable_point_id


def test_fingerprint_stable_whitespace_case():
    a = {"content": "  ExamplePerson   created  Axiom ", "type": "event", "source": "chat"}
    b = {"content": "example_person created axiom", "type": "event", "source": "CHAT"}
    assert canonical_fingerprint(a) == canonical_fingerprint(b)


def test_stable_point_id_changes_when_content_changes():
    a = {"content": "foo", "type": "event"}
    b = {"content": "bar", "type": "event"}
    assert stable_point_id(a) != stable_point_id(b)

