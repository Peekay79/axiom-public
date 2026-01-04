Context Budgets & Allocator
===========================

Overview
--------
The allocator enforces a token budget for LLM context using a weighted score across Recency, Salience, Trust, and Diversity. It seeds diversity per bucket and fills greedily by score/tokens.

Env Flags
---------
- CONTEXT_ALLOCATOR_ENABLED: true
- CONTEXT_TOKEN_BUDGET: 6000
- CONTEXT_WEIGHTS_RECENCY: 0.35
- CONTEXT_WEIGHTS_SALIENCE: 0.35
- CONTEXT_WEIGHTS_TRUST: 0.20
- CONTEXT_WEIGHTS_DIVERSITY: 0.10
- CONTEXT_MIN_PER_BUCKET: 1
- CONTEXT_MAX_PER_BUCKET: 4

Implementation
--------------
- `context_allocator/scoring.py`: score(item, now)
- `context_allocator/buckets.py`: bucketize(items)
- `context_allocator/allocator.py`: allocate(items, token_budget) -> (chosen, dropped, stats)

Wire-Up
-------
- `memory_response_pipeline.py` applies allocator before building the context block when enabled and emits Cockpit `context.snapshot` with `{tokens_used,truncated_count,diversity_buckets}`.

Tests
-----
See `tests/test_context_allocator.py`.

