from __future__ import annotations

import os
import threading
from typing import Any, Dict, List, Optional


def _env_bool(name: str, default: bool = False) -> bool:
	return str(os.getenv(name, str(default))).strip().lower() in {"1", "true", "yes", "y"}


# Feature flag (supports both new and legacy env names)
RERANK_ENABLED = _env_bool("ENABLE_RERANKER", _env_bool("RERANK_ENABLED", False))

# Model id: prefer explicit env, otherwise default to a well-known compact CE
RERANK_MODEL = os.getenv(
	"RERANK_MODEL",
	os.getenv("RERANKER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2"),
)


# Lazy-loaded global model instance
_CE_MODEL = None  # type: ignore[var-annotated]
_MODEL_LOCK = threading.Lock()


def _get_cross_encoder():
	"""Return a singleton CrossEncoder instance (lazy-loaded)."""
	global _CE_MODEL
	if _CE_MODEL is not None:
		return _CE_MODEL
	with _MODEL_LOCK:
		if _CE_MODEL is not None:
			return _CE_MODEL
		try:
			from sentence_transformers import CrossEncoder  # type: ignore
			try:
				import torch  # type: ignore
				device = "cuda" if getattr(torch, "cuda", None) and torch.cuda.is_available() else "cpu"
			except Exception:
				device = "cpu"
			_CE_MODEL = CrossEncoder(RERANK_MODEL, device=device)
			return _CE_MODEL
		except Exception:
			# Keep None to trigger heuristic fallback on use
			return None


def heuristic_rerank(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
	# Prefer items with more content and recent timestamps
	def score(it: Dict[str, Any]) -> float:
		content = (it.get("content") or it.get("text") or "")
		base = min(1.0, len(content) / 500.0)
		recency = 0.0
		try:
			from datetime import datetime
			from dateutil import parser as dateparser  # type: ignore
			ts = it.get("timestamp") or it.get("created_at")
			if ts:
				dt = dateparser.parse(ts) if isinstance(ts, str) else ts
				age_days = max(0.0, (datetime.utcnow() - dt).total_seconds() / 86400.0)
				recency = max(0.0, 1.0 - min(1.0, age_days / 30.0))
		except Exception:
			pass
		return base * 0.7 + recency * 0.3
	return sorted(results, key=score, reverse=True)


def cross_encoder_rerank(
	results: List[Dict[str, Any]], *, query: Optional[str] = None, add_scores: bool = True
) -> List[Dict[str, Any]]:
	"""Re-rank results using a CrossEncoder if enabled, else heuristic.

	- Preserves original metadata on each item
	- Optionally annotates items with `_reranker_score`
	- Accepts an optional `query` used when items lack a `query` field
	"""
	if not RERANK_ENABLED:
		return heuristic_rerank(results)
	if not results:
		return results
	model = _get_cross_encoder()
	if model is None:
		return heuristic_rerank(results)
	try:
		pairs = []
		for it in results:
			q = (query if isinstance(query, str) and query else (it.get("query") or ""))
			t = it.get("content") or it.get("text") or ""
			pairs.append((q, t))
		scores = model.predict(pairs)
		try:
			# numpy array or list
			scores_list = [float(x) for x in (scores.tolist() if hasattr(scores, "tolist") else list(scores))]
		except Exception:
			scores_list = [float(x) for x in scores]
		# Annotate and sort by CE score desc
		for s, it in zip(scores_list, results):
			if add_scores:
				it["_reranker_score"] = float(s)
		scored = list(zip(scores_list, results))
		scored.sort(key=lambda x: x[0], reverse=True)
		return [r for _, r in scored]
	except Exception:
		return heuristic_rerank(results)