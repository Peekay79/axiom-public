import asyncio
from unittest.mock import patch


class _FakeTripwires:
    def __init__(self, allow_wonder=True, allow_dream=True):
        self._wonder = allow_wonder
        self._dream = allow_dream

    def is_wonder_allowed(self):
        return bool(self._wonder)

    def is_dream_allowed(self):
        return bool(self._dream)


class _MemStub:
    def __init__(self):
        self.calls = []

    def store_memory(self, **kwargs):
        self.calls.append(("store_memory", kwargs))
        # return a dict with id like real Memory.store_memory mock in wonder_engine
        rec_id = kwargs.get("metadata", {}).get("id", "stub_id")
        return {"id": rec_id}

    def query_random_memories(self, count=2, exclude_tags=None):
        return [
            {"content": "Ant colonies exhibit swarm intelligence"},
            {"content": "Blockchain uses distributed consensus"},
        ]


class _BeliefGraphStub:
    def __init__(self, create_edge: bool):
        self._new_edge = False
        self._should_create = create_edge
        self._linked = []

    def get_related_beliefs(self, subject: str, depth: int = 1):
        base = 1
        bonus = 1 if self._new_edge else 0
        # return list of dicts with ids
        return [{"id": f"{subject}_rel_{i}"} for i in range(base + bonus)]

    def link_beliefs(self, id1: str, id2: str, relation: str):
        self._linked.append((id1, id2, relation))
        if self._should_create:
            self._new_edge = True
        return "edge_id"


def test_wonder_skips_when_tripwire_blocks():
    from wonder_engine import trigger_wonder

    mem = _MemStub()
    tw = _FakeTripwires(allow_wonder=False)
    out = trigger_wonder(mem, belief_graph=None, journal=None, past_thoughts=[], tripwires=tw)
    assert out["status"] == "aborted"
    assert out["reason"] == "tripwire_block"
    assert all(call[0] != "store_memory" for call in mem.calls)


def test_wonder_persists_only_on_new_edges_created():
    # Call reflect_and_store directly to bypass scoring/safety randomness
    from wonder_engine import reflect_and_store

    mem = _MemStub()

    # Case 1: new edge created -> store called
    bg_yes = _BeliefGraphStub(create_edge=True)
    res_yes = reflect_and_store(
        thought="Alpha Beta",
        scores={"novelty": 1.0, "coherence": 1.0, "delight": 1.0},
        memory=mem,
        journal=None,
        belief_graph=bg_yes,
        tripwires=_FakeTripwires(allow_wonder=True),
    )
    assert res_yes["status"] == "stored_with_containment"
    assert any(call[0] == "store_memory" for call in mem.calls)

    # Reset memory calls
    mem.calls.clear()

    # Case 2: no new edges -> do not store
    bg_no = _BeliefGraphStub(create_edge=False)
    res_no = reflect_and_store(
        thought="Alpha Beta",
        scores={"novelty": 1.0, "coherence": 1.0, "delight": 1.0},
        memory=mem,
        journal=None,
        belief_graph=bg_no,
        tripwires=_FakeTripwires(allow_wonder=True),
    )
    assert res_no["status"] == "pruned"
    assert all(call[0] != "store_memory" for call in mem.calls)


def test_dream_stored_only_when_allowed(monkeypatch):
    import json
    from dream_engine import DreamEngine

    engine = DreamEngine()

    # Patch LLM client to return minimal valid JSON array
    class _LLM:
        async def call_llm(self, prompt):
            return {"content": json.dumps([{"content": "d1", "type": "dream", "confidence": 0.9, "tags": []}])}

    monkeypatch.setattr("dream_engine.llm_client", _LLM())

    stored = {}

    def _store(entry):
        # Capture containment constraints
        stored["last"] = dict(entry)
        return entry.get("id", "id1")

    monkeypatch.setattr(engine.memory, "store", _store)

    # Allowed path: should store and enforce containment
    from dream_engine import _tripwires as _tw_mod

    class _TW:
        def is_dream_allowed(self):
            return True

    monkeypatch.setattr("dream_engine._tripwires", _TW())

    out = asyncio.get_event_loop().run_until_complete(engine.generate_dream())
    assert out["success"] is True
    # Ensure containment: no belief promotion, is_dream true, confidence <= 0.5
    assert stored["last"]["is_dream"] is True
    assert str(stored["last"].get("memory_type", "")).lower() != "belief"
    assert stored["last"].get("type") != "belief"
    assert float(stored["last"].get("confidence", 1.0)) <= 0.5


def test_dream_tripwire_blocks(monkeypatch):
    import json
    from dream_engine import DreamEngine

    engine = DreamEngine()

    class _LLM:
        async def call_llm(self, prompt):
            return {"content": json.dumps([{"content": "d1", "type": "dream"}])}

    monkeypatch.setattr("dream_engine.llm_client", _LLM())

    class _TW:
        def is_dream_allowed(self):
            return False

    monkeypatch.setattr("dream_engine._tripwires", _TW())

    out = asyncio.get_event_loop().run_until_complete(engine.generate_dream())
    assert out["success"] is False
    assert out["error"] == "tripwire_block"

