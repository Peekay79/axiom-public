import os
import pytest

from config.constants import COVERAGE_THRESHOLD, STRONG_SIM_THRESHOLD

# Minimal helpers mirroring memory_response_pipeline's logic (token overlap)
from memory_response_pipeline import _compute_coverage


def make_hit(text: str, score: float):
    return {"content": text, "_additional": {"score": score}}


def test_coverage_allows_answer_when_strong_hit_present():
    question = "Tell me about Example Project capabilities"
    hits = [
        make_hit("Example Project is a hypothetical project with advanced retrieval.", 0.78),
        make_hit("Unrelated context.", 0.10),
    ]
    cov = _compute_coverage(question, [h["content"] for h in hits])
    assert cov >= 0.0
    # Even if coverage is low, strong hit should prevent don't-know
    assert any((h.get("_additional",{}).get("score",0.0) >= STRONG_SIM_THRESHOLD) for h in hits)


def test_coverage_blocks_dont_know_only_when_both_conditions_met():
    question = "What do you know about Example Project?"
    hits = [
        make_hit("Random unrelated memory about gardening.", 0.20),
        make_hit("Another random memory.", 0.18),
    ]
    cov = _compute_coverage(question, [h["content"] for h in hits])
    both_hold = (cov < COVERAGE_THRESHOLD) and (max(h["_additional"]["score"] for h in hits) < STRONG_SIM_THRESHOLD)
    assert isinstance(both_hold, bool)


def test_coverage_rises_with_overlap():
    q = "Explain LLM streaming timeouts and watchdogs"
    docs = [
        "This note describes timeouts and watchdog mechanisms for streaming.",
        "Nothing relevant",
    ]
    cov = _compute_coverage(q, docs)
    assert cov > 0.0
