import os
import asyncio

from retrieval import HYBRID_RETRIEVAL_ENABLED, search_hybrid
from retrieval.dedupe import cluster_drop
from retrieval.rerank import heuristic_rerank


def test_dedupe_clusters():
	items = [
		{"content": "hello world"},
		{"content": "hello   world"},
		{"content": "different text altogether"},
	]
	out = cluster_drop(items, threshold=0.9)
	assert len(out) == 2


def test_heuristic_rerank_orders_by_length():
	items = [
		{"content": "short"},
		{"content": "this is a considerably longer content string that should rank higher"},
	]
	ranked = heuristic_rerank(items)
	assert ranked[0]["content"].startswith("this is a considerably")


async def _run_hybrid():
	os.environ["HYBRID_RETRIEVAL_ENABLED"] = "true"
	res = await search_hybrid("test", k=5, weights={"lexical": 0.3, "dense": 0.7})
	assert isinstance(res, list)


def test_hybrid_runs_event_loop():
	asyncio.get_event_loop().run_until_complete(_run_hybrid())