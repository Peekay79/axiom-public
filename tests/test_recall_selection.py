import json
import os
from contextlib import contextmanager

import builtins

from vector.recall_utils import (
    RecallHit,
    RecallCfg,
    load_recall_cfg,
    apply_threshold,
    dynamic_threshold,
    top1_fallback,
    keyword_boost,
    mmr_rerank,
    select_recall_candidates,
    emit_recall_telemetry,
)


@contextmanager
def envset(mapping):
    old = {k: os.environ.get(k) for k in mapping}
    try:
        for k, v in mapping.items():
            if v is None and k in os.environ:
                del os.environ[k]
            elif v is not None:
                os.environ[k] = str(v)
        yield
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _make_hits(scores, texts=None, tags=None, with_vec=False):
    texts = texts or [f"t{i}" for i in range(len(scores))]
    tags = tags or [[] for _ in scores]
    hits = []
    for i, s in enumerate(scores):
        hits.append(
            RecallHit(
                id=str(i), similarity=float(s), text=texts[i], tags=list(tags[i]), embedding=([1.0, 0.0] if with_vec else None), raw={"_similarity": float(s), "text": texts[i], "tags": tags[i]},
            )
        )
    return hits


def test_threshold_pass_fail():
    hits = _make_hits([0.29, 0.31])
    kept = apply_threshold(hits, 0.30)
    assert len(kept) == 1
    assert kept[0].similarity == 0.31


def test_dynamic_threshold_floor_allows_some():
    hits = _make_hits([0.28, 0.22, 0.10])
    used, after = dynamic_threshold(hits, primary=0.30, floor=0.15)
    assert used <= 0.30
    assert used >= 0.15
    assert len(after) >= 1  # at least top candidate


def test_top1_fallback_returns_best():
    hits = _make_hits([0.11, 0.49, 0.33])
    t1 = top1_fallback(hits)
    assert len(t1) == 1
    assert abs(t1[0].similarity - 0.49) < 1e-9


def test_keyword_boost_promotes_match():
    hits = _make_hits([0.60, 0.58], texts=["alpha beta", "Hev is here"], tags=[[], []])
    boosted = keyword_boost(hits, query="Who is Hev?", fields=["content"])  # content maps to text
    assert boosted[0].text.lower().startswith("hev") or boosted[0].text.lower().endswith("here")


def test_mmr_changes_order_with_lambda():
    # Two items equally relevant but similar embeddings cause diversity tradeoff
    a = RecallHit(id="a", similarity=0.9, text="a", tags=[], embedding=[1.0, 0.0], raw={})
    b = RecallHit(id="b", similarity=0.89, text="b", tags=[], embedding=[0.99, 0.01], raw={})
    c = RecallHit(id="c", similarity=0.70, text="c", tags=[], embedding=[0.0, 1.0], raw={})
    base = [a, b, c]
    r_high_rel = mmr_rerank(base, k=3, lam=0.95)
    r_div = mmr_rerank(base, k=3, lam=0.30)
    # High relevance keeps a first; higher diversity should bring c earlier than b in some cases
    assert r_high_rel[0].id == "a"
    assert r_div[0].id == "a"
    # Diversity-leaning lambda should not be identical ordering to relevance-only
    assert [h.id for h in r_high_rel] != [h.id for h in r_div]


def test_selection_pipeline_with_env_flags_and_telemetry(capsys):
    hits = _make_hits([0.27, 0.26, 0.15], texts=["no match", "Hev mention", "low"], tags=[[], [], []])
    with envset({
        "SIMILARITY_THRESHOLD": "0.30",
        "RECALL_DYNAMIC_THRESHOLD": "true",
        "RECALL_DYNAMIC_FLOOR": "0.18",
        "RECALL_TOP1_FALLBACK": "true",
        "RECALL_MIN_RESULTS": "1",
        "RECALL_KEYWORD_BOOST": "true",
        "RECALL_KEYWORD_FIELDS": "content,tags",
        "RECALL_MMR_ENABLED": "false",
        "RECALL_LOG_TELEMETRY": "true",
        "RECALL_LOG_PREVIEW_CHARS": "80",
    }):
        cfg = load_recall_cfg()
        selected = select_recall_candidates("Who is Hev?", hits, cfg)
        # Should include at least one due to dynamic or top1/min_results
        assert len(selected) >= 1
        # Emit telemetry and verify basic structure
        emit_recall_telemetry("Who is Hev?", hits, selected, cfg)
        out = capsys.readouterr().out.strip().splitlines()
        assert out, "expected telemetry line"
        parsed = json.loads(out[-1])
        assert parsed.get("event") == "vector_recall"
        assert "counts" in parsed and "top_samples" in parsed


def test_honesty_guard_in_build_context_block_integration():
    # Minimal import for the function; verify it includes internal hint when no context
    from memory_response_pipeline import build_context_block

    # No memories/beliefs/facts → should inject signal
    ctx = build_context_block([], [])
    assert "MEMORY_CONTEXT: none" in ctx

