import os

from ranking import compute_arbitration_weights


def _set_env(d: dict[str, str]):
    for k, v in d.items():
        os.environ[k] = str(v)


def test_arbitration_weights_context_modes():
    _set_env({
        "AXIOM_ARBITRATION_ENABLED": "1",
        "AXIOM_ARBITRATION_MODE": "context",
        # base weights
        "AXIOM_ARB_W_BASE": "0.30",
        "AXIOM_ARB_W_EPISODIC": "0.25",
        "AXIOM_ARB_W_PROCEDURAL": "0.30",
        "AXIOM_ARB_W_ABSTRACTION": "0.30",
        # HOW multipliers
        "AXIOM_ARB_MULT_HOW_BASE": "0.8",
        "AXIOM_ARB_MULT_HOW_EPISODIC": "1.0",
        "AXIOM_ARB_MULT_HOW_PROCEDURAL": "1.5",
        "AXIOM_ARB_MULT_HOW_ABSTRACTION": "0.9",
        # WHY multipliers
        "AXIOM_ARB_MULT_WHY_BASE": "0.8",
        "AXIOM_ARB_MULT_WHY_EPISODIC": "1.0",
        "AXIOM_ARB_MULT_WHY_PROCEDURAL": "0.9",
        "AXIOM_ARB_MULT_WHY_ABSTRACTION": "1.5",
        # FACT multipliers
        "AXIOM_ARB_MULT_FACT_BASE": "1.3",
        "AXIOM_ARB_MULT_FACT_EPISODIC": "1.3",
        "AXIOM_ARB_MULT_FACT_PROCEDURAL": "0.9",
        "AXIOM_ARB_MULT_FACT_ABSTRACTION": "0.9",
    })

    # HOW → procedural highest
    w_how = compute_arbitration_weights("how")
    assert abs(sum(w_how.values()) - 1.0) < 1e-6
    assert w_how["procedural"] == max(w_how.values())

    # WHY → abstraction highest
    w_why = compute_arbitration_weights("why")
    assert abs(sum(w_why.values()) - 1.0) < 1e-6
    assert w_why["abstraction"] == max(w_why.values())

    # FACT → base and episodic highest (tie allowed)
    w_fact = compute_arbitration_weights("fact")
    assert abs(sum(w_fact.values()) - 1.0) < 1e-6
    top = max(w_fact.values())
    tops = [k for k, v in w_fact.items() if v == top]
    assert "base" in tops and "episodic" in tops

