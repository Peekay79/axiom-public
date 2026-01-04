#!/usr/bin/env python3
from __future__ import annotations

from context_allocator.allocator import allocate


def test_allocator_budget_and_diversity(monkeypatch):
    monkeypatch.setenv("CONTEXT_TOKEN_BUDGET", "200")
    monkeypatch.setenv("CONTEXT_MIN_PER_BUCKET", "1")
    monkeypatch.setenv("CONTEXT_MAX_PER_BUCKET", "2")

    items = []
    for i in range(20):
        items.append({
            "content": f"Item {i} with some content to count tokens {i}",
            "tags": [f"topic{i%3}"],
            "source": "user" if i % 2 == 0 else "model",
            "importance": 0.5,
            "confidence": 0.6,
        })

    chosen, dropped, stats = allocate(items, token_budget=200)
    assert stats["tokens_used"] <= 200
    assert stats["truncated_count"] >= 0
    assert stats["diversity_buckets"] >= 1

