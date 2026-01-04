#!/usr/bin/env python3
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone


def test_provenance_required_and_normalized(monkeypatch):
    from beliefs.provenance import normalize_provenance, has_external_evidence
    from governor.belief_governance import ensure_provenance

    # Missing provenance is a violation
    ok, reason = ensure_provenance({"statement": "x"})
    assert ok is False and reason == "missing_provenance"

    # Normalization fills minimal fields
    raw = [
        {"url": "https://example.com"},
        {"type": "journal", "id": "evt123"},
        "doi:10.1000/182",
    ]
    norm = normalize_provenance(raw)
    assert all("type" in x and "ref" in x for x in norm)
    assert has_external_evidence(norm) is True


def test_contradiction_event_and_signal_emitted(monkeypatch):
    events = []
    signals = []

    # Monkeypatch internals to capture side-effects
    import beliefs.contradictions as bc

    monkeypatch.setattr(bc, "_journal_log", lambda e: events.append(e))
    monkeypatch.setattr(bc, "_write_signal", lambda pod, sig, data: signals.append((pod, sig, data)))

    rec = bc.create_contradiction("a1", "b2", {"reason": "conflict_on_statement"})
    assert rec["type"] == "contradiction"
    assert events and events[-1]["a"] == "a1"
    assert signals and signals[-1][1] == "belief_contradiction"


def test_recompute_caps_without_external(monkeypatch):
    os.environ["BELIEF_CONFIDENCE_CAP_NO_EXTERNAL"] = "0.6"
    from beliefs.model import Belief
    from beliefs.recompute import recompute_one

    b = Belief(id="x", statement="s", confidence=0.9, provenance=[], tags=[])
    out = recompute_one(b, now=datetime.now(timezone.utc))
    assert out.confidence <= 0.6


def test_recompute_dormancy_decay(monkeypatch):
    os.environ["BELIEF_DORMANCY_HALFLIFE_DAYS"] = "30"
    from beliefs.model import Belief
    from beliefs.recompute import recompute_one

    sixty_days_ago = datetime.now(timezone.utc) - timedelta(days=60)
    prov = [{"type": "external", "ref": "doc://x", "ts": sixty_days_ago.isoformat()}]
    b = Belief(id="x", statement="s", confidence=0.8, provenance=prov, tags=[])
    out = recompute_one(b, now=datetime.now(timezone.utc))
    # 60 days -> two half-lives => factor 0.25 => 0.8 * 0.25 = 0.2
    assert abs(out.confidence - 0.2) < 1e-6


def test_recompute_counterevidence_penalty(monkeypatch):
    os.environ["BELIEF_COUNTEREVIDENCE_PENALTY"] = "0.2"
    from beliefs.model import Belief
    import beliefs.recompute as br

    # Force contradiction detection to True
    monkeypatch.setattr(br, "_has_contradiction_since", lambda belief_id, since: True)

    last_rec = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    b = Belief(id="x", statement="s", confidence=0.5, provenance=[], tags=[], last_recompute=last_rec)
    out = br.recompute_one(b, now=datetime.now(timezone.utc))
    assert abs(out.confidence - 0.3) < 1e-6

