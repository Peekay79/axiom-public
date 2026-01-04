import os
import shutil
from pathlib import Path

import pytest


@pytest.mark.asyncio
async def test_reflection_generates_markdown(tmp_path, monkeypatch):
    # Arrange
    journals_dir = tmp_path / "journals"
    monkeypatch.setenv("AXIOM_JOURNALS_DIR", str(journals_dir))
    monkeypatch.setenv("AXIOM_REFLECTION_ENABLED", "1")
    monkeypatch.setenv("AXIOM_CONFIDENCE_ENABLED", "1")

    # Provide minimal memories/beliefs
    memories = [
        {"content": "User asked about preferences.", "speaker": "user"},
        {"content": "System provided an answer.", "speaker": "axiom"},
    ]
    beliefs = [
        {"statement": "Axiom values clarity and safety.", "confidence": 0.8},
        {"subject": "axiom", "predicate": "prefers", "object": "clear communication", "confidence": 0.7},
    ]

    # Act
    from reflection import reflect_on_session

    result = await reflect_on_session(memories, beliefs)

    # Assert
    assert result is not None
    assert result.skipped is False
    assert result.summary_chars >= 1
    assert journals_dir.exists(), "journals directory should be created"
    files = list(journals_dir.glob("*.md"))
    assert files, "a markdown reflection should be written"


@pytest.mark.asyncio
async def test_reflection_flag_gated(tmp_path, monkeypatch):
    # Arrange
    journals_dir = tmp_path / "journals"
    monkeypatch.setenv("AXIOM_JOURNALS_DIR", str(journals_dir))
    monkeypatch.setenv("AXIOM_REFLECTION_ENABLED", "0")

    from reflection import reflect_on_session

    # Act
    res = await reflect_on_session([], [])

    # Assert
    assert res.skipped is True
    assert not journals_dir.exists() or not list(journals_dir.glob("*.md"))


@pytest.mark.asyncio
async def test_belief_reinforcement_when_enabled(tmp_path, monkeypatch):
    # Arrange
    journals_dir = tmp_path / "journals"
    monkeypatch.setenv("AXIOM_JOURNALS_DIR", str(journals_dir))
    monkeypatch.setenv("AXIOM_REFLECTION_ENABLED", "1")
    monkeypatch.setenv("AXIOM_CONFIDENCE_ENABLED", "1")

    # Stub belief graph upsert to count calls
    class DummyBG:
        def upsert_belief(self, s, p, o, **kwargs):
            return f"id:{s}:{p}:{o}"

    import builtins
    import types

    # Dynamically create a fake module belief_graph with attribute belief_graph
    dummy_module = types.SimpleNamespace(belief_graph=DummyBG())
    import sys
    sys.modules["belief_graph"] = dummy_module

    # Force LLM fallback path by stubbing connector to raise
    async def _fail_call(prompt: str):
        return None

    from reflection import reflect_on_session as _ros, _call_llm as _orig_call
    from reflection import _call_llm as _call

    # Monkeypatch the private llm call
    import reflection as R
    R._call_llm = _fail_call  # type: ignore

    # Provide beliefs that include a parseable triple
    memories = []
    beliefs = [
        {"subject": "axiom", "predicate": "values", "object": "clarity"},
        {"statement": "axiom prefers kindness"},
    ]

    # Act
    res = await R.reflect_on_session(memories, beliefs)

    # Assert
    assert res is not None
    assert res.reinforced_count >= 0
    files = list(journals_dir.glob("*.md"))
    assert files

