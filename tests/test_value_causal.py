import logging

import pytest

from tests.utils.env import temp_env


@pytest.mark.phase("subsystems")
def test_value_causal_env_gating_and_logs(caplog):
    caplog.set_level(logging.INFO)

    # Disabled gates → functions noop and log canonical tags
    with temp_env({
        "AXIOM_VALUE_ENGINE_ENABLED": "0",
        "AXIOM_CAUSAL_ENGINE_ENABLED": "0",
    }):
        import importlib
        import value_inference_engine as vie
        import causal_reasoner as cr

        importlib.reload(vie)
        importlib.reload(cr)

        engine = vie.ValueInferenceEngine()
        # No beliefs/goals imported here; just ensure noop returns and logs
        import asyncio

        async def run_v():
            out1 = await engine.infer_values_from_beliefs([])
            out2 = await engine.infer_values_from_goals([])
            return out1, out2

        o1, o2 = asyncio.get_event_loop().run_until_complete(run_v())
        assert o1 == [] and o2 == []

        # Causal add should noop
        ce = cr.get_causal_engine()
        assert ce.add_causal_link("a", "b", 0.5) is None

        msgs = [r.getMessage() for r in caplog.records]
        # Canonical tags present
        assert any("[RECALL][Value]" in m for m in msgs)
        assert any("[RECALL][Causal]" in m for m in msgs)

    # Enabled gates → non-noop logs
    with temp_env({
        "AXIOM_VALUE_ENGINE_ENABLED": "1",
        "AXIOM_CAUSAL_ENGINE_ENABLED": "1",
    }):
        import importlib
        import value_inference_engine as vie
        import causal_reasoner as cr
        importlib.reload(vie)
        importlib.reload(cr)

        engine = vie.ValueInferenceEngine()
        import asyncio

        async def run_v2():
            out = await engine.get_value_influences()
            return out

        _ = asyncio.get_event_loop().run_until_complete(run_v2())

        ce = cr.get_causal_engine()
        _ = ce.get_effects("nonexist")

        msgs = [r.getMessage() for r in caplog.records]
        assert any("[RECALL][Value]" in m for m in msgs)
        assert any("[RECALL][Causal]" in m for m in msgs)
