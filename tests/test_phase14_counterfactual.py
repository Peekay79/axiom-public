import os
import logging

from retrieval_planner import get_counterfactual_simulation
from counterfactual import generate_counterfactual


def test_counterfactual_operator_triggers_simulation(monkeypatch):
    os.environ["AXIOM_COUNTERFACTUAL_ENABLED"] = "1"
    sim = get_counterfactual_simulation("what_if: QA delay")
    assert isinstance(sim, dict)
    assert sim.get("enabled") is True
    # Target parsed
    assert sim.get("target") in {"QA delay", None}


def test_counterfactual_backend_respects_min_confidence(tmp_path, caplog):
    # Build a small SQLite graph to validate threshold behavior
    from belief_graph.sqlite_backend import SQLiteBeliefGraph

    db_path = tmp_path / "belief_graph.sqlite"
    g = SQLiteBeliefGraph(str(db_path))

    # Create cause and effect beliefs
    qa_id = g.upsert_belief("QA delay", "is", "event", confidence=0.9)
    slip_id = g.upsert_belief("Project Slip", "is", "outcome", confidence=0.9)
    assert qa_id and slip_id

    # Link QA delay cause_of Project Slip
    _ = g.link_beliefs(qa_id, slip_id, "cause_of")

    with caplog.at_level(logging.INFO):
        os.environ["AXIOM_COUNTERFACTUAL_MIN_CONFIDENCE"] = "0.4"
        effects = g.simulate_counterfactual("QA delay", remove_edge=("QA delay", "cause_of", "Project Slip"))
        # Should log required messages
        assert any("[RECALL][Counterfactual] starting simulation for node=QA delay" in r.message for r in caplog.records)
        assert any("removed edge" in r.message for r in caplog.records)
        assert any("alternate path" in r.message for r in caplog.records)
        # Should produce at least one plausible effect
        assert isinstance(effects, list)
        assert any("avoided" in (e.get("effect") or "") for e in effects)


def test_llm_overlay_expansion_log(monkeypatch, caplog):
    # Verify that the log marker is emitted when overlay expansion runs
    from judger import expand_counterfactual
    import asyncio

    async def _fake_llm(**kwargs):
        class R(dict):
            pass
        return [R({"response": "If QA hadn’t been late, the project would likely have stayed on track."})]

    # Patch llm connector used in judger
    class _MC:
        def __init__(self):
            pass

        async def __call__(self, *_, **__):
            return await _fake_llm()

    monkeypatch.setitem(__import__("sys").modules, "llm_connector", type("X", (), {"safe_multiquery_context_pipeline": _MC()})())

    caplog.set_level(logging.INFO)
    text = asyncio.get_event_loop().run_until_complete(
        expand_counterfactual({"removed": ["QA delay → Project Slip"], "effects": ["Project Slip avoided"]})
    )
    assert text is not None
    assert any("[RECALL][Counterfactual] LLM overlay expanded simulation" in r.message for r in caplog.records)


def test_disable_counterfactual_returns_baseline(monkeypatch):
    os.environ["AXIOM_COUNTERFACTUAL_ENABLED"] = "0"
    sim = get_counterfactual_simulation("what_if: QA delay")
    assert sim.get("enabled") is False


def test_low_confidence_edges_excluded(tmp_path):
    from belief_graph.sqlite_backend import SQLiteBeliefGraph

    db_path = tmp_path / "belief_graph.sqlite"
    g = SQLiteBeliefGraph(str(db_path))

    # Low-confidence cause/effect
    a = g.upsert_belief("Minor hiccup", "is", "event", confidence=0.2)
    b = g.upsert_belief("Project Slip", "is", "outcome", confidence=0.3)
    assert a and b
    _ = g.link_beliefs(a, b, "cause_of")

    os.environ["AXIOM_COUNTERFACTUAL_MIN_CONFIDENCE"] = "0.4"
    effects = g.simulate_counterfactual("Minor hiccup", remove_edge=("Minor hiccup", "cause_of", "Project Slip"))
    assert effects == []

