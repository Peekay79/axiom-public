import os

import retrieval_planner as rp


def _set_env(d: dict[str, str]):
    for k, v in d.items():
        os.environ[k] = str(v)


def test_intent_heuristic_classification():
    _set_env({
        "AXIOM_ARBITRATION_ENABLED": "1",
        "AXIOM_ARBITRATION_INTENT_MODEL": "heuristic",
    })
    assert rp.detect_query_intent("How do I fix docker?") == "how"
    assert rp.detect_query_intent("why is the service crashing?") == "why"
    assert rp.detect_query_intent("what is the status?") == "fact"
    assert rp.detect_query_intent("when did the deploy finish?") == "fact"
    assert rp.detect_query_intent("who owns the job?") == "fact"

    # Unknown input falls back safely
    assert rp.detect_query_intent("") == "fact"

