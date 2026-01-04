import os


def test_resolve_llm_openai():
    os.environ["LLM_PROVIDER"] = "openai"
    os.environ["LLM_API_BASE"] = "https://api.openai.com/v1"
    os.environ["OPENAI_API_KEY"] = "sk-test"
    os.environ["LLM_MODEL_ID"] = "gpt-4o"
    from config.resolver import resolve_llm

    d = resolve_llm()
    assert d["provider"] in ("openai", "openai_compatible")
    assert d["base_url"].endswith("/v1") or d["base_url"].startswith("https://api")
    assert d["model"] == "gpt-4o"
    assert d["ok"] is True


def test_resolve_vector_legacy_vs_canonical(monkeypatch):
    # Canonical
    os.environ["QDRANT_URL"] = "http://qdrant:6333"
    from config.resolver import resolve_vector

    a = resolve_vector()
    # Legacy path
    os.environ.pop("QDRANT_URL", None)
    os.environ["QDRANT_URL"] = "qdrant:6333"
    b = resolve_vector()
    assert a["url"].endswith(":6333")
    assert b["url"].endswith(":6333")
    assert a["ok"] and b["ok"]
