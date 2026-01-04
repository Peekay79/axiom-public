import os


def test_subject_extraction_or_simplifier_produces_reasonable_query(monkeypatch):
    from retrieval_planner import plan_query

    # Ensure both features are enabled
    monkeypatch.setenv("AXIOM_SUBJECT_EXTRACTION_ENABLED", "1")
    monkeypatch.setenv("AXIOM_QUERY_SIMPLIFY_ENABLED", "1")

    # With subject extraction available (spaCy may be missing; both paths are acceptable)
    q = "Do you remember what Steve Jobs announced at Apple?"
    out = plan_query(q)
    assert isinstance(out, str) and len(out) > 0
    # Either subject tokens or simplified lower text without filler
    assert "remember" not in out.lower()


def test_simplifier_handles_short_questions(monkeypatch):
    from retrieval_planner import plan_query

    monkeypatch.setenv("AXIOM_SUBJECT_EXTRACTION_ENABLED", "0")
    monkeypatch.setenv("AXIOM_QUERY_SIMPLIFY_ENABLED", "1")

    out = plan_query("What is AI?")
    assert isinstance(out, str) and len(out) > 0
    # Fallback to original if simplifier strips too much; ensure not empty
    assert out

