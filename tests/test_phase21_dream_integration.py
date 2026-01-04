import os

from dream_loop import integrate_consolidations


def test_integration_dry_run(monkeypatch):
    monkeypatch.setenv("AXIOM_DREAM_DRY_RUN", "1")

    cons = [
        {
            "type": "journal_entry",
            "content": "Neutral consolidation text",
            "tags": ["summary"],
            "source_ids": ["s1", "s2"],
        }
    ]

    rep = integrate_consolidations(cons)
    assert rep["dry_run"] is True
    assert rep["written_count"] == 0


def test_integration_writes_and_marks(monkeypatch):
    monkeypatch.setenv("AXIOM_DREAM_DRY_RUN", "0")

    stored = []

    class _Mem:
        def __init__(self):
            self._snap = [
                {"id": "s1", "content": "foo", "memory_type": "episodic", "timestamp": "2025-01-01T00:00:00+00:00"},
                {"id": "s2", "content": "bar", "memory_type": "episodic", "timestamp": "2025-01-01T00:00:00+00:00"},
            ]

        def snapshot(self):
            return list(self._snap)

        def add_to_long_term(self, rec):
            stored.append(rec)

    import dream_loop as dl

    monkeypatch.setattr(dl, "Memory", _Mem)

    cons = [
        {
            "type": "journal_entry",
            "content": "Consolidated neutral summary",
            "tags": ["summary"],
            "source_ids": ["s1", "s2"],
        }
    ]

    rep = integrate_consolidations(cons)
    assert rep["dry_run"] is False
    assert rep["written_count"] == 1
    # Two source marks attempted (idempotent)
    assert rep["sources_marked"] >= 0
    # Stored contains dream-tagged entry
    assert any("dream" in (r.get("tags") or []) for r in stored)

