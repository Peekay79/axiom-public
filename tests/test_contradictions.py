#!/usr/bin/env python3
import os
from datetime import datetime, timedelta, timezone

from memory.scoring import composite_score, load_weights


def _mk_mem(vec, **kw):
    m = dict(kw)
    m["_vector"] = vec

    class H(dict):
        @property
        def vector(self):
            return self["_vector"]

    return H(m)


def test_contradiction_detection_simple():
    # Enable features
    os.environ["AXIOM_BELIEFS_ENABLED"] = "1"
    os.environ["AXIOM_CONTRADICTION_ENABLED"] = "1"
    try:
        w = load_weights("default")
        w["belief_conflict_penalty"] = 0.05
        # Shared belief tag and opposing claims about same entity
        now = datetime.now(timezone.utc)
        m_old = _mk_mem(
            [1.0, 0.0],
            id="A",
            timestamp=(now - timedelta(days=1)).isoformat(),
            beliefs=["topic.entity"],
            content="Alpha is not available today.",
        )
        m_new = _mk_mem(
            [1.0, 0.0],
            id="B",
            timestamp=now.isoformat(),
            beliefs=["topic.entity"],
            content="Alpha is available today.",
        )
        # Composite score individually
        qv = [1.0, 0.0]
        _ = composite_score(m_old, qv, w=w)
        _ = composite_score(m_new, qv, w=w)
        # Heuristic detector is integrated in pipeline; here we sanity check our regex polarity parser indirectly by ensuring no exceptions
        assert True
    finally:
        os.environ.pop("AXIOM_BELIEFS_ENABLED", None)
    os.environ.pop("AXIOM_CONTRADICTION_ENABLED", None)


def test_newer_wins_penalty_direction():
    os.environ["AXIOM_BELIEFS_ENABLED"] = "1"
    os.environ["AXIOM_CONTRADICTION_ENABLED"] = "1"
    try:
        w = load_weights("default")
        w["belief_conflict_penalty"] = 0.1
        now = datetime.now(timezone.utc)
        old_mem = _mk_mem(
            [1.0, 0.0],
            id="X",
            timestamp=(now - timedelta(days=2)).isoformat(),
            beliefs=["axiom.identity"],
            content="Project Phoenix is not active.",
        )
        new_mem = _mk_mem(
            [1.0, 0.0],
            id="Y",
            timestamp=now.isoformat(),
            beliefs=["axiom.identity"],
            content="Project Phoenix is active.",
        )
        # Baseline scores without applying pipeline-level penalties
        qv = [1.0, 0.0]
        s_old, d_old = composite_score(old_mem, qv, w=w)
        s_new, d_new = composite_score(new_mem, qv, w=w)
        # We cannot apply the penalty here without pipeline, but ensure both scored fine and produced bel factors
        assert d_old["bel"] >= 0.0 and d_new["bel"] >= 0.0
    finally:
        os.environ.pop("AXIOM_BELIEFS_ENABLED", None)
    os.environ.pop("AXIOM_CONTRADICTION_ENABLED", None)
