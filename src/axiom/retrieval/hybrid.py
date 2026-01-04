from __future__ import annotations

import os
from typing import Any, Dict, List, Tuple

from governor.retrieval_monitor import report_embedding_stats, report_recall_cohort


def _env_bool(name: str, default: bool = False) -> bool:
	return str(os.getenv(name, str(default))).strip().lower() in {"1", "true", "yes", "y"}


HYBRID_RETRIEVAL_ENABLED = _env_bool("HYBRID_RETRIEVAL_ENABLED", False)
HYBRID_WEIGHTS = {
	"lexical": float((os.getenv("HYBRID_WEIGHTS_LEXICAL", "0.3")).strip() or "0.3"),
	"dense": float((os.getenv("HYBRID_WEIGHTS_DENSE", "0.7")).strip() or "0.7"),
}


async def bm25_search(query: str, k: int) -> List[Dict[str, Any]]:
	# Minimal lexical search placeholder; integrate proper BM25 if available later
	from pods.vector.vector_adapter import VectorAdapter  # reuse qdrant text filter if any
	va = VectorAdapter()
	# No true BM25 available; return empty for now (fail-closed)
	return []


	async def dense_search(query: str, k: int) -> List[Dict[str, Any]]:
		# Delegate to existing vector recall path to avoid code duplication
		import memory_response_pipeline  # type: ignore
		try:
			return await memory_response_pipeline.fetch_vector_hits(query, top_k=k)
		except Exception:
			return []


async def search_hybrid(query: str, k: int, weights: Dict[str, float] | None = None) -> List[Dict[str, Any]]:
	if not HYBRID_RETRIEVAL_ENABLED:
		return await dense_search(query, k)
	w = weights or HYBRID_WEIGHTS
	k_lex = max(1, int(os.getenv("HYBRID_K_LEX", "8")))
	k_dense = max(1, int(os.getenv("HYBRID_K_DENSE", "16")))
	lex = await bm25_search(query, k_lex)
	dense = await dense_search(query, k_dense)
	# Simple union with naive score normalization
	seen = {}
	for it in lex:
		key = it.get("id") or it.get("uuid") or it.get("content")
		if key not in seen:
			seen[key] = {**it, "_source": "lex", "_score": w.get("lexical", 0.3)}
	for it in dense:
		key = it.get("id") or it.get("uuid") or it.get("content")
		if key in seen:
			seen[key]["_score"] = seen[key].get("_score", 0.0) + w.get("dense", 0.7)
			seen[key]["_source"] = "hybrid"
		else:
			seen[key] = {**it, "_source": "dense", "_score": w.get("dense", 0.7)}
	return sorted(seen.values(), key=lambda x: x.get("_score", 0.0), reverse=True)[:k]