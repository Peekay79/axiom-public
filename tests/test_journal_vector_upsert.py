from types import SimpleNamespace


def test_journal_vector_disabled(monkeypatch):
    # Ensure flag is off
    monkeypatch.setenv("JOURNAL_VECTOR_ENABLED", "0")

    called = {"upsert": 0}

    class FakeClient:
        def __init__(self, env):
            pass
        def upsert(self, collection, items):
            called["upsert"] += 1
            return {"inserted": len(items)}

    monkeypatch.setitem(__import__("sys").modules, "vector.unified_client", SimpleNamespace(UnifiedVectorClient=FakeClient))

    from importlib import reload
    import journaling_enhancer as je
    reload(je)

    # Build minimal entry
    entry = SimpleNamespace(
        title="T",
        summary="S",
        timestamp=__import__("datetime").datetime.utcnow(),
        metadata=SimpleNamespace(tags=["x"]) ,
    )
    # Simulate method call (should not call upsert)
    try:
        import asyncio
        asyncio.get_event_loop().run_until_complete(je.JournalingEnhancer()._store_entry(entry))
    except Exception:
        pass
    assert called["upsert"] == 0


def test_journal_vector_enabled(monkeypatch):
    monkeypatch.setenv("JOURNAL_VECTOR_ENABLED", "1")

    called = {"upsert": 0, "items": []}

    class FakeClient:
        def __init__(self, env):
            pass
        def upsert(self, collection, items):
            called["upsert"] += 1
            called["items"] = items
            return {"inserted": len(items)}

    monkeypatch.setitem(__import__("sys").modules, "vector.unified_client", SimpleNamespace(UnifiedVectorClient=FakeClient))

    from importlib import reload
    import journaling_enhancer as je
    reload(je)

    entry = SimpleNamespace(
        title="T",
        summary="S",
        timestamp=__import__("datetime").datetime.utcnow(),
        metadata=SimpleNamespace(tags=["x"]) ,
    )
    try:
        import asyncio
        asyncio.get_event_loop().run_until_complete(je.JournalingEnhancer()._store_entry(entry))
    except Exception:
        pass

    assert called["upsert"] == 1
    assert len(called["items"]) == 1
    it = called["items"][0]
    assert "content" in it and "metadata" in it
    assert "journal_entry" in it["metadata"]["tags"]
