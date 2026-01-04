import os

from ranking import rank_candidates


def _set_env(d: dict[str, str]):
    for k, v in d.items():
        os.environ[k] = str(v)


def test_arbitration_ranking_applies_weights():
    _set_env({
        "AXIOM_ARBITRATION_ENABLED": "1",
        "AXIOM_ARBITRATION_MODE": "context",
        # Make ranking base weights equal and rely on arbitration to differentiate
        "AXIOM_RETRIEVAL_WEIGHTS": "vector=0.0,confidence=1.0,judger=0.0",
    })
    judger = {}
    # Candidates with same confidence but different provenance types
    base = {"id": "b", "confidence": 0.5, "type": "memory"}
    epi = {"id": "e", "confidence": 0.5, "tags": ["episodic_active"]}
    proc = {"id": "p", "confidence": 0.5, "tags": ["procedural_active"]}
    absx = {"id": "a", "confidence": 0.5, "type": "abstraction", "tags": ["abstraction_active"]}

    # HOW should prioritize procedural
    ranked_how = rank_candidates([base, epi, proc, absx], [], judger_scores=judger, weights=None, confidence_only=False, arbitration_intent="how")
    assert ranked_how[0]["id"] == "p"

    # WHY should prioritize abstraction
    ranked_why = rank_candidates([base, epi, proc, absx], [], judger_scores=judger, weights=None, confidence_only=False, arbitration_intent="why")
    assert ranked_why[0]["id"] == "a"

    # FACT should favor base/episodic
    ranked_fact = rank_candidates([base, epi, proc, absx], [], judger_scores=judger, weights=None, confidence_only=False, arbitration_intent="fact")
    assert ranked_fact[0]["id"] in {"b", "e"}


def test_arbitration_disabled_no_change():
    # With arbitration disabled, ordering should be by confidence only (equal order but deterministic by stable sort)
    _set_env({
        "AXIOM_ARBITRATION_ENABLED": "0",
        "AXIOM_RETRIEVAL_WEIGHTS": "vector=0.0,confidence=1.0,judger=0.0",
    })
    hits = [
        {"id": "1", "confidence": 0.2},
        {"id": "2", "confidence": 0.4},
        {"id": "3", "confidence": 0.3},
    ]
    ranked = rank_candidates(hits, [], judger_scores={}, weights=None, confidence_only=False)
    ids = [h["id"] for h in ranked]
    assert ids == ["2", "3", "1"]

