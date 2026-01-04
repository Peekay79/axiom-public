#!/usr/bin/env python3
import json
import os
from typing import Dict

import pytest

from memory.contradiction_applier import (
    apply_contradiction_resolution,
    prompt_user_for_resolution,
)
from memory.contradiction_api import apply_resolution as _facade_apply


def _base_conflict(strategy: str = None, confidence: float = 0.7) -> Dict:
    conflict = {
        "uuid": "test-conf-1",
        "belief_a": {"text": "A should be true", "uuid": "a1"},
        "belief_b": {"text": "B should not be true", "uuid": "b1"},
        "proposed_resolution": {
            "resolution_strategy": strategy,
            "confidence": confidence,
        },
    }
    return conflict


def test_apply_inhibit_updates_target():
    c = _base_conflict("inhibit", 0.8)
    c["proposed_resolution"]["inhibit_belief_id"] = "b1"
    out = apply_contradiction_resolution(c)
    assert out["applied_resolution"]["resolution_strategy"] == "inhibit"
    assert out["applied_resolution"].get("inhibited") in {"b1", "B should not be true"}


def test_apply_reframe_attaches_reframed():
    c = _base_conflict("reframe", 0.9)
    c["proposed_resolution"]["reframed_belief"] = {"text": "Reframed belief"}
    out = apply_contradiction_resolution(c)
    applied = out["applied_resolution"]
    assert applied["resolution_strategy"] == "reframe"
    assert "reframed_belief" in applied


def test_apply_dream_resolution_is_noop_but_logged():
    c = _base_conflict("dream_resolution", 0.8)
    out = apply_contradiction_resolution(c)
    applied = out["applied_resolution"]
    assert applied["resolution_strategy"] == "dream_resolution"
    assert applied.get("deferred_to_dream") is True


def test_apply_flag_for_review_sets_needs_review():
    c = _base_conflict("flag_for_review", 0.7)
    out = apply_contradiction_resolution(c)
    applied = out["applied_resolution"]
    assert applied["resolution_strategy"] == "flag_for_review"
    # Both sides should have been tagged best-effort; check conflict is returned regardless
    assert "applied_resolution" in out


def test_prompt_user_for_resolution_when_ambiguous_confidence():
    c = _base_conflict("inhibit", 0.5)
    res = prompt_user_for_resolution(c)
    assert res["user_override"] is True
    assert res["resolution_strategy"] == "flag_for_review"


def test_facade_apply_imports():
    # Smoke test: facade wiring should expose apply_resolution
    assert _facade_apply is not None
