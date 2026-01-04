#!/usr/bin/env python3
import os
from datetime import datetime, timezone

from memory.scoring import composite_score, load_weights


def _mk_mem(vec, **kw):
    m = dict(kw)
    m["_vector"] = vec

    class H(dict):
        @property
        def vector(self):
            return self["_vector"]

    return H(m)


def test_belief_alignment_overlap_higher():
    os.environ["AXIOM_BELIEFS_ENABLED"] = "1"
    try:
        w = load_weights("default")
        # Active beliefs env override
        os.environ["AXIOM_ACTIVE_BELIEFS_JSON"] = '["ai.safety", "axiom.identity.core"]'
        qv = [1.0, 0.0]
        aligned = _mk_mem(
            [1.0, 0.0],
            timestamp=datetime.now(timezone.utc).isoformat(),
            beliefs=["ai.safety"],
        )
        unaligned = _mk_mem(
            [1.0, 0.0],
            timestamp=datetime.now(timezone.utc).isoformat(),
            beliefs=["sports.football"],
        )
        s_a, d_a = composite_score(aligned, qv, w=w)
        s_u, d_u = composite_score(unaligned, qv, w=w)
        assert d_a["bel"] > d_u["bel"]
    finally:
        os.environ.pop("AXIOM_BELIEFS_ENABLED", None)
        os.environ.pop("AXIOM_ACTIVE_BELIEFS_JSON", None)


def test_belief_importance_boost():
    os.environ["AXIOM_BELIEFS_ENABLED"] = "1"
    try:
        w = load_weights("default")
        w["belief_importance_boost"] = 0.1
        os.environ["AXIOM_ACTIVE_BELIEFS_JSON"] = '["axiom.identity.core"]'
        qv = [1.0, 0.0]
        base = _mk_mem(
            [1.0, 0.0],
            timestamp=datetime.now(timezone.utc).isoformat(),
            beliefs=["misc.tag"],
        )
        important = _mk_mem(
            [1.0, 0.0],
            timestamp=datetime.now(timezone.utc).isoformat(),
            beliefs=["axiom.identity.core"],
        )
        s_b, d_b = composite_score(base, qv, w=w)
        s_i, d_i = composite_score(important, qv, w=w)
        assert d_i["bel"] >= d_b["bel"]
    finally:
        os.environ.pop("AXIOM_BELIEFS_ENABLED", None)
        os.environ.pop("AXIOM_ACTIVE_BELIEFS_JSON", None)
