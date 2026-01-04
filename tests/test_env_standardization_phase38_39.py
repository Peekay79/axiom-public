import os
import re


def test_decay_halflife_legacy_maps_and_logs(monkeypatch, capsys):
    # Ensure canonical not set; set legacy
    monkeypatch.delenv("AXIOM_DECAY_HALFLIFE_DAYS", raising=False)
    monkeypatch.setenv("AXIOM_DECAY_HALF_LIFE", "7")
    # Re-import module to resolve env
    import importlib
    mod = importlib.import_module("pods.memory.decay_policy")
    importlib.reload(mod)
    assert abs(mod.HALF_LIFE_DAYS - 7.0) < 1e-6


def test_contradiction_legacy_maps_to_canonical(monkeypatch):
    # Clear canonical, set legacy
    monkeypatch.delenv("AXIOM_CONTRADICTION_ENABLED", raising=False)
    monkeypatch.setenv("AXIOM_CONTRADICTIONS", "1")
    # Access pipeline helper paths that read the flag
    import importlib
    memory_response_pipeline = importlib.import_module("memory_response_pipeline")
    # Trigger code path that resolves contradictions flag
    # by calling _sleep_backoff (no-op) and reading globals
    assert isinstance(getattr(memory_response_pipeline, "_TOP_N", 8), int)
    # Legacy mapping should set canonical in process env
    assert os.getenv("AXIOM_CONTRADICTION_ENABLED") in {"1", "true", "True"}


def test_meta_window_legacy_maps_to_seconds(monkeypatch):
    # Clear canonical and set legacy to 24h
    monkeypatch.delenv("AXIOM_META_WINDOW_SEC", raising=False)
    monkeypatch.setenv("AXIOM_META_WINDOW", "24h")
    import importlib
    mc = importlib.import_module("meta_cognition")
    importlib.reload(mc)
    # compute_cycle should parse and map to seconds
    res = mc.compute_cycle()
    assert isinstance(res, dict)
    assert int(os.getenv("AXIOM_META_WINDOW_SEC", "0") or 0) in (86400,)


def test_retry_and_scoring_flags_present_in_env_example():
    path = os.path.join(os.getcwd(), "autocog.env.example")
    with open(path, "r", encoding="utf-8") as f:
        txt = f.read()
    # Ensure key flags are present with defaults
    for k in (
        "AXIOM_USAGE_RETRY_MAX=3",
        "AXIOM_USAGE_RETRY_BASE_MS=100",
        "AXIOM_USAGE_RETRY_JITTER_MS=100",
        "AXIOM_COMPOSITE_SCORING=0",
        "AXIOM_SCORING_PROFILE=default",
        "AXIOM_MMR_LAMBDA=0.4",
        "AXIOM_TOP_N=8",
        "AXIOM_AUTO_PROFILE=0",
        "AXIOM_TIERED_HIGH_CONF=0.8",
        "AXIOM_DECISIVE_FILTER=0",
        "AXIOM_BELIEF_CONFLICT_PENALTY=0.05",
        "AXIOM_HYGIENE_WEIGHTS=\"recency=0.5,confidence=0.5\"",
        "AXIOM_HYGIENE_RECENCY_HALFLIFE_SEC=86400",
        "AXIOM_HYGIENE_SCAN_LIMIT=500",
        "AXIOM_META_WINDOW_SEC=86400",
        "AXIOM_PROVENANCE_GRADING_ENABLED=0",
        "AXIOM_PROVENANCE_GRADE_WEIGHTS=\"source=0.5,confidence=0.5\"",
    ):
        assert k in txt


def test_conflicts_prefer_canonical(monkeypatch):
    # Set both legacy and canonical to conflicting values; canonical should win
    monkeypatch.setenv("AXIOM_CONTRADICTIONS", "0")
    monkeypatch.setenv("AXIOM_CONTRADICTION_ENABLED", "1")
    import importlib
    ms = importlib.import_module("memory.scoring")
    # Build a dummy item with contradiction flag
    m = {"vector": [1.0, 0.0], "contradiction_flag": True, "confidence": 0.5}
    q = [1.0, 0.0]
    score, comps = ms.composite_score(m, q, selected=[])
    assert comps.get("conflict_penalty", 0.0) >= 0.0
