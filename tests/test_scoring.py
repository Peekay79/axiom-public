import math
import os
from datetime import datetime, timedelta, timezone

from memory.scoring import composite_score, load_weights, mmr_select, utc_now


def _mk_mem(vector, **payload):
    m = dict(payload)
    m["_vector"] = vector

    # Support Hit-like access pattern
    class H(dict):
        @property
        def vector(self):
            return self["_vector"]

    return H(m)


def test_similarity_higher_is_better():
    qv = [1.0, 0.0]
    m1 = _mk_mem([1.0, 0.0], timestamp=datetime.now(timezone.utc).isoformat())
    m2 = _mk_mem([0.0, 1.0], timestamp=datetime.now(timezone.utc).isoformat())
    w = load_weights("default")
    s1, _ = composite_score(m1, qv, w=w)
    s2, _ = composite_score(m2, qv, w=w)
    assert s1 > s2


def test_recency_boost_newer_when_wrec_positive():
    now = datetime.now(timezone.utc)
    qv = [1.0, 0.0]
    m_new = _mk_mem([1.0, 0.0], timestamp=now.isoformat())
    m_old = _mk_mem([1.0, 0.0], timestamp=(now - timedelta(days=30)).isoformat())
    w = load_weights("default")
    s_new, _ = composite_score(m_new, qv, w=w, now_fn=lambda: now)
    s_old, _ = composite_score(m_old, qv, w=w, now_fn=lambda: now)
    assert s_new > s_old


def test_source_trust_increases_score():
    qv = [1.0, 0.0]
    base = _mk_mem(
        [1.0, 0.0], timestamp=datetime.now(timezone.utc).isoformat(), source_trust=0.3
    )
    cred = _mk_mem(
        [1.0, 0.0], timestamp=datetime.now(timezone.utc).isoformat(), source_trust=0.9
    )
    w = load_weights("default")
    s_base, _ = composite_score(base, qv, w=w)
    s_cred, _ = composite_score(cred, qv, w=w)
    assert s_cred > s_base


def test_usage_increases_score():
    qv = [1.0, 0.0]
    m0 = _mk_mem(
        [1.0, 0.0], timestamp=datetime.now(timezone.utc).isoformat(), times_used=0
    )
    m10 = _mk_mem(
        [1.0, 0.0], timestamp=datetime.now(timezone.utc).isoformat(), times_used=10
    )
    w = load_weights("default")
    s0, _ = composite_score(m0, qv, w=w)
    s10, _ = composite_score(m10, qv, w=w)
    assert s10 > s0


def test_mmr_diversity_selection():
    qv = [1.0, 0.0]
    items = [
        _mk_mem([1.0, 0.0], timestamp=datetime.now(timezone.utc).isoformat()),
        _mk_mem([0.9, 0.1], timestamp=datetime.now(timezone.utc).isoformat()),
        _mk_mem([0.0, 1.0], timestamp=datetime.now(timezone.utc).isoformat()),
    ]
    idxs = mmr_select(items, qv, k=2, lambda_=0.5)
    assert len(idxs) == 2
    # Expect that a diverse item is included (likely the [0,1])
    assert any(items[i]["_vector"][1] > 0.5 for i in idxs)


def test_integration_ordering_default():
    # 6 synthetic memories
    now = datetime.now(timezone.utc)
    qv = [1.0, 0.0]
    mems = [
        _mk_mem(
            [1.0, 0.0],
            timestamp=now.isoformat(),
            source_trust=0.8,
            confidence=0.7,
            times_used=5,
            importance=0.6,
        ),
        _mk_mem(
            [0.8, 0.2],
            timestamp=now.isoformat(),
            source_trust=0.9,
            confidence=0.9,
            times_used=2,
            importance=0.7,
        ),
        _mk_mem(
            [0.5, 0.5],
            timestamp=(now - timedelta(days=1)).isoformat(),
            source_trust=0.6,
            confidence=0.5,
            times_used=0,
            importance=0.5,
        ),
        _mk_mem(
            [0.9, 0.1],
            timestamp=(now - timedelta(days=10)).isoformat(),
            source_trust=0.4,
            confidence=0.4,
            times_used=1,
            importance=0.4,
        ),
        _mk_mem(
            [0.2, 0.8],
            timestamp=now.isoformat(),
            source_trust=0.7,
            confidence=0.6,
            times_used=0,
            importance=0.3,
        ),
        _mk_mem(
            [0.95, 0.05],
            timestamp=(now - timedelta(days=2)).isoformat(),
            source_trust=0.5,
            confidence=0.5,
            times_used=0,
            importance=0.5,
        ),
    ]
    w = load_weights("default")
    scored = [
        (composite_score(m, qv, w=w, now_fn=lambda: now)[0], i)
        for i, m in enumerate(mems)
    ]
    scored.sort(key=lambda x: x[0], reverse=True)
    # The most similar and trusted recent ones should be near the top
    top_idx = scored[0][1]
    assert top_idx in {0, 1, 5}


def test_composite_score_kwarg_name():
    qv = [1.0, 0.0]
    m = _mk_mem([1.0, 0.0], timestamp=datetime.now(timezone.utc).isoformat())
    w = load_weights("default")
    # Accepts 'w' named argument
    s, d = composite_score(m, qv, w=w)
    assert isinstance(s, float) and isinstance(d, dict)
    # If someone tries 'weights=', Python should raise TypeError
    try:
        composite_score(m, qv, weights=w)  # type: ignore
        assert False, "composite_score unexpectedly accepted 'weights=' kwarg"
    except TypeError:
        assert True


def test_beliefs_enabled_aligned_item_ranks_higher():
    os.environ["AXIOM_BELIEFS_ENABLED"] = "1"
    os.environ["AXIOM_ACTIVE_BELIEFS_JSON"] = (
        '["ai.should_help_people", "axiom.identity.core"]'
    )
    try:
        qv = [1.0, 0.0]
        aligned = _mk_mem(
            [1.0, 0.0],
            timestamp=datetime.now(timezone.utc).isoformat(),
            beliefs=["ai.should_help_people"],
        )
        unaligned = _mk_mem(
            [1.0, 0.0],
            timestamp=datetime.now(timezone.utc).isoformat(),
            beliefs=["sports.football"],
        )
        w = load_weights("default")
        s_a, d_a = composite_score(aligned, qv, w=w)
        s_u, d_u = composite_score(unaligned, qv, w=w)
        assert d_a["bel"] > d_u["bel"]
        assert s_a >= s_u
    finally:
        os.environ.pop("AXIOM_BELIEFS_ENABLED", None)
        os.environ.pop("AXIOM_ACTIVE_BELIEFS_JSON", None)
