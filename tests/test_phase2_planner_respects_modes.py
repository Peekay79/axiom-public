def test_planner_subject_first_then_simplifier_then_raw(monkeypatch):
    from retrieval_planner import plan_query, extract_subjects

    # Force subject extraction to return a known token
    def fake_extract(text: str):
        return ["Alpha", "Project"]

    monkeypatch.setenv("AXIOM_SUBJECT_EXTRACTION_ENABLED", "1")
    monkeypatch.setenv("AXIOM_QUERY_SIMPLIFY_ENABLED", "1")
    monkeypatch.setattr("retrieval_planner.extract_subjects", fake_extract, raising=True)

    out = plan_query("Please tell me about Alpha project timeline?")
    assert out == "Alpha Project"

    # Disable subject extraction → use simplifier
    monkeypatch.setenv("AXIOM_SUBJECT_EXTRACTION_ENABLED", "0")
    out2 = plan_query("Do you remember the Alpha project timeline?")
    assert "remember" not in out2.lower()
    assert len(out2) > 0

    # Disable both → raw
    monkeypatch.setenv("AXIOM_QUERY_SIMPLIFY_ENABLED", "0")
    out3 = plan_query("What is the Alpha project?")
    assert out3 == "What is the Alpha project?"

