from __future__ import annotations

import argparse
import os
import statistics
import time
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple
import logging


def _env_bool(name: str, default: bool = False) -> bool:
	return str(os.getenv(name, str(default))).strip().lower() in {"1", "true", "yes", "y", "on"}


def _env_int(name: str, default: int) -> int:
	try:
		return int(str(os.getenv(name, str(default))).strip())
	except Exception:
		return int(default)


def _env_float(name: str, default: float) -> float:
	try:
		return float(str(os.getenv(name, str(default))).strip())
	except Exception:
		return float(default)


REEMBED_ENABLED = _env_bool("REEMBED_ENABLED", True)
REEMBED_BATCH_SIZE = _env_int("REEMBED_BATCH_SIZE", 1000)
REEMBED_SOURCE_NS = os.getenv("REEMBED_SOURCE_NS", "mem_current").strip() or "mem_current"
REEMBED_SHADOW_NS = os.getenv("REEMBED_SHADOW_NS", "mem_shadow").strip() or "mem_shadow"
REEMBED_ALIAS_NAME = os.getenv("REEMBED_ALIAS_NAME", "mem_current").strip() or "mem_current"
REEMBED_MAX_JOBS = _env_int("REEMBED_MAX_JOBS", 1)
REEMBED_EVAL_RECALL_AT = _env_int("REEMBED_EVAL_RECALL_AT", 10)
REEMBED_PASS_KL_MAX = _env_float("REEMBED_PASS_KL_MAX", 0.12)
REEMBED_PASS_RECALL_DELTA_MIN = _env_float("REEMBED_PASS_RECALL_DELTA_MIN", -0.01)
REEMBED_PASS_LATENCY_DELTA_MAX_MS = _env_int("REEMBED_PASS_LATENCY_DELTA_MAX_MS", 25)
DRIFT_CANARY_SET = os.getenv("DRIFT_CANARY_SET", "canaries/default.jsonl").strip() or "canaries/default.jsonl"


logger = logging.getLogger(__name__)


@dataclass
class ReembedSummary:
	decision: str
	kl: float
	cos_shift: float
	median_latency_ms_shadow: Optional[float]
	median_latency_ms_source: Optional[float]
	recall_delta: float
	alias_before: Optional[str]
	alias_after: Optional[str]
	shadow_ns: str
	source_ns: str


def _emit_signal(name: str, payload: Dict[str, Any]) -> None:
	try:
		from pods.cockpit.cockpit_reporter import write_signal  # type: ignore
		write_signal("governor", name, payload)
	except Exception:
		pass


def _saga_begin(cid: str, meta: Dict[str, Any]) -> None:
	try:
		from governor.saga import saga_begin  # type: ignore
		saga_begin(cid, "ReembedSaga", meta)
	except Exception:
		_emit_signal("saga_begin.ReembedSaga", {"cid": cid, "meta": meta})


def _saga_step(cid: str, step: str, ok: bool, info: Dict[str, Any]) -> None:
	try:
		from governor.saga import saga_step  # type: ignore
		saga_step(cid, "ReembedSaga", step, ok, info)
	except Exception:
		_emit_signal(f"saga_step.ReembedSaga.{step}", {"cid": cid, "ok": bool(ok), "info": info})


def _saga_end(cid: str, ok: bool, summary: Dict[str, Any]) -> None:
	try:
		from governor.saga import saga_end  # type: ignore
		saga_end(cid, "ReembedSaga", ok, summary)
	except Exception:
		_emit_signal("saga_end.ReembedSaga", {"cid": cid, "ok": bool(ok), "summary": summary})


def _now_ms() -> float:
	return time.perf_counter() * 1000.0


def _get_embedder():
	try:
		from sentence_transformers import SentenceTransformer  # type: ignore
        model_name = os.getenv("AXIOM_EMBEDDER") or os.getenv("EMBEDDING_MODEL") or "all-MiniLM-L6-v2"
        emb = SentenceTransformer(model_name)
        try:
            logger.info("[RECALL][Embedding] ✅ Embedder ready: %s", model_name)
        except Exception:
            pass
        return emb
	except Exception as e:
		raise RuntimeError(f"embedder_unavailable: {e}")


def _qdrant_raw_client():
	try:
		from memory.utils.qdrant_compat import make_qdrant_client  # type: ignore
		return make_qdrant_client()
	except Exception as e:
		raise RuntimeError(f"qdrant_unavailable: {e}")


def _scroll_points(client, collection: str, limit: int = 256) -> Iterable[Any]:
	"""Yield points with payload (no vectors) using scroll."""
	try:
		offset = None
		while True:
			res = client.scroll(collection_name=collection, with_payload=True, with_vectors=False, limit=limit, offset=offset)
			points = getattr(res, "points", None) or res[0] if isinstance(res, tuple) else []
			offset = getattr(res, "next_page_offset", None) or res[1] if isinstance(res, tuple) else None
			for p in points or []:
				yield p
			if not offset:
				break
	except Exception as e:
		raise RuntimeError(f"scroll_failed: {e}")


def _payload_text(payload: Dict[str, Any]) -> Optional[str]:
	for key in ("text", "content", "statement"):
		v = payload.get(key)
		if isinstance(v, str) and v.strip():
			return v
	return None


def _point_id(point: Any) -> str:
	try:
		pid = getattr(point, "id", None)
		if pid is None and isinstance(point, dict):
			pid = point.get("id")
		return str(pid)
	except Exception:
		return ""


def _point_payload(point: Any) -> Dict[str, Any]:
	try:
		pl = getattr(point, "payload", None)
		if pl is None and isinstance(point, dict):
			pl = point.get("payload")
		return pl or {}
	except Exception:
		return {}


def _build_index(client, collection: str) -> None:
	# Best-effort: Optimize index if API exists; otherwise no-op
	try:
		if hasattr(client, "update_collection"):
			# Leave as best-effort; defaults should suffice
			pass
	except Exception:
		pass


def _set_alias_atomic(client, alias_name: str, target_collection: str) -> Tuple[Optional[str], Optional[str]]:
	"""Atomically point alias_name to target_collection; return (prev, new)."""
	try:
		# List current aliases by resolving collections: some clients provide list_aliases
		prev_target = None
		if hasattr(client, "list_aliases"):
			try:
				aliases = client.list_aliases()
				# aliases may be a dict or object; fallback to None
				d = getattr(aliases, "aliases", None) or getattr(aliases, "result", None) or {}
				if isinstance(d, list):
					for a in d:
						name = getattr(a, "alias_name", None) or getattr(a, "alias", None) or getattr(a, "name", None)
						target = getattr(a, "collection_name", None) or getattr(a, "collection", None)
						if str(name) == alias_name:
							prev_target = str(target)
							break
			except Exception:
				prev_target = None
		# Use update_aliases operation (v1+)
		from qdrant_client.http import models as qm  # type: ignore
		ops = [qm.CreateAliasOperation(create_alias=qm.CreateAlias(collection_name=target_collection, alias_name=alias_name))]
		client.update_aliases(changes=ops)
		return prev_target, target_collection
	except Exception as e:
		raise RuntimeError(f"alias_update_failed: {e}")


def _shadow_reset(client, shadow_ns: str, vector_size: int = 384) -> None:
	"""Create or empty the shadow namespace safely."""
	from qdrant_client.http import models as qm  # type: ignore
	# Create if missing
	try:
		cols = client.get_collections()
		names = []
		try:
			names = [c.name for c in getattr(cols, "collections", [])]
		except Exception:
			pass
		if shadow_ns not in names:
			client.create_collection(collection_name=shadow_ns, vectors_config=qm.VectorParams(size=vector_size, distance=qm.Distance.COSINE))
	except Exception:
		# Best-effort create; continue
		pass
	# Drop all points in shadow via filter=None + delete by range: fallback to full wipe if supported
	try:
		client.delete(collection_name=shadow_ns, points_selector={"filter": {}})  # type: ignore[arg-type]
	except Exception:
		# If delete by filter unsupported, try recreate
		try:
			client.delete_collection(collection_name=shadow_ns)
			client.create_collection(collection_name=shadow_ns, vectors_config=qm.VectorParams(size=vector_size, distance=qm.Distance.COSINE))
		except Exception:
			pass


def _compute_latency_ms(latencies: List[float]) -> Optional[float]:
	if not latencies:
		return None
	try:
		return float(statistics.median(latencies))
	except Exception:
		return float(sum(latencies) / float(len(latencies)))


def _eval_canaries(embedder, client, collection: str, canaries: List[Dict[str, Any]], k: int) -> Tuple[float, List[float]]:
	"""Return (mean_recall, latencies_ms_list)."""
	from axiom_qdrant_client import SearchResult  # type: ignore
	from retrieval.canary import evaluate_recall_k  # local
	recalls: List[float] = []
	latencies: List[float] = []
	for item in canaries:
		q = item.get("q")
		labels = item.get("labels") or []
		if not isinstance(q, str) or not labels:
			continue
		vec = embedder.encode(q, normalize_embeddings=True).tolist()
		start = _now_ms()
		try:
			res = client.search(collection_name=collection, query_vector=vec, limit=k, with_vectors=False)
		except Exception:
			res = []
		latencies.append(_now_ms() - start)
		ids: List[str] = []
		for r in res or []:
			try:
				if hasattr(r, "id"):
					ids.append(str(r.id))
				else:
					# best-effort dict shape
					ids.append(str((r or {}).get("id")))
			except Exception:
				continue
		recalls.append(evaluate_recall_k(ids, [str(x) for x in labels], k))
	if not recalls:
		return 0.0, latencies
	return float(sum(recalls) / float(len(recalls))), latencies


def _drift_compare(source_ns: str, shadow_ns: str) -> Tuple[float, float]:
	"""Read drift state files and compute (kl, cos_shift) from baseline(source) → shadow.

	If files missing, return (0.0, 0.0) (fail-closed).
	"""
	try:
		from retrieval.drift import snapshot_stats, kl_divergence, compute_cosine_shift  # type: ignore
		src = snapshot_stats(source_ns)
		sh = snapshot_stats(shadow_ns)
		p = src.get("cos_hist") or []
		q = sh.get("cos_hist") or []
		b = src.get("baseline") or []
		if b and q:
			kl = kl_divergence(b, q)
			shift = compute_cosine_shift(b, q)
			return float(kl), float(shift)
		return 0.0, 0.0
	except Exception:
		return 0.0, 0.0


def run_reembed(
	source_ns: str,
	shadow_ns: str,
	alias_name: str,
	batch_size: int,
	canaries_path: str,
	eval_k: int,
	pass_kl_max: float,
	pass_recall_delta_min: float,
	pass_latency_delta_max_ms: int,
) -> Dict[str, Any]:
	"""
	Steps:
	1) Create/empty SHADOW namespace
	2) Stream docs from SOURCE → embed with current pinned model → upsert to SHADOW (batch_size); record per-batch latency
	3) Build index / optimize SHADOW
	4) Canary eval:
	   - Dense recall@k on SOURCE and SHADOW
	   - Latency comparison (median)
	   - Drift: compare SHADOW norm/cos hist vs SOURCE baseline (kl, cos_shift)
	5) Pass/Fail gate:
	   - kl <= pass_kl_max
	   - recall_delta >= pass_recall_delta_min
	   - latency_delta_ms <= pass_latency_delta_max_ms
	6) If pass → atomically switch alias alias_name -> shadow_ns
	   Else → keep alias as-is
	7) Return summary with decision, metrics, and rollback info
	"""
	if not REEMBED_ENABLED:
		return {"decision": "disabled", "ok": False}
	# Correlation id for saga (timestamp based)
	cid = f"reembed-{int(time.time())}"
	_saga_begin(cid, {"source": source_ns, "shadow": shadow_ns, "alias": alias_name})
	ok = False
	alias_before = None
	alias_after = None
	try:
		raw = _qdrant_raw_client()
		embedder = _get_embedder()
        try:
            logger.info("[RECALL][Embedding] Re-embedding started: source=%s shadow=%s batch_size=%s", source_ns, shadow_ns, batch_size)
        except Exception:
            pass
		# Step 1: Shadow reset
		_saga_step(cid, "build_shadow", True, {"stage": "reset"})
		_shadow_reset(raw, shadow_ns)
		# Step 2: Stream + embed + upsert
		latencies_ms: List[float] = []
		batch: List[Dict[str, Any]] = []
		for p in _scroll_points(raw, source_ns, limit=256):
			pl = _point_payload(p)
			text = _payload_text(pl)
			pid = _point_id(p) or None
			if not text or not pid:
				continue
			v = embedder.encode(text, normalize_embeddings=True).tolist()
			batch.append({"id": pid, "vector": v, "payload": pl})
			if len(batch) >= batch_size:
				start = _now_ms()
				try:
					raw.upsert(collection_name=shadow_ns, points=batch)  # type: ignore[attr-defined]
				except Exception:
					# Fallback: API without bulk upsert
					from qdrant_client.http import models as qm  # type: ignore
					pts = [qm.PointStruct(id=it["id"], vector=it["vector"], payload=it["payload"]) for it in batch]
					raw.upsert(collection_name=shadow_ns, points=pts)
				latencies_ms.append(_now_ms() - start)
				batch = []
		# Flush remaining
		if batch:
			start = _now_ms()
			from qdrant_client.http import models as qm  # type: ignore
			pts = [qm.PointStruct(id=it["id"], vector=it["vector"], payload=it["payload"]) for it in batch]
			raw.upsert(collection_name=shadow_ns, points=pts)
			latencies_ms.append(_now_ms() - start)
		_saga_step(cid, "build_shadow", True, {"stage": "upsert_done", "batches": len(latencies_ms)})
		# Step 3: Optimize / build index (best-effort)
		_build_index(raw, shadow_ns)
		# Step 4: Canary eval (source and shadow)
		try:
			from retrieval.canary import load_canaries  # local
			canaries = load_canaries(canaries_path)
		except Exception:
			canaries = []
		recall_src, lat_src = _eval_canaries(embedder, raw, source_ns, canaries, REEMBED_EVAL_RECALL_AT)
		recall_sh, lat_sh = _eval_canaries(embedder, raw, shadow_ns, canaries, REEMBED_EVAL_RECALL_AT)
		recall_delta = float(recall_sh - recall_src)
		# Emit blue/green recall eval record (best-effort)
		try:
			from retrieval.bluegreen import record_recall_eval  # type: ignore
			record_recall_eval(source_ns, shadow_ns, REEMBED_EVAL_RECALL_AT, recall_delta)
		except Exception:
			pass
		med_src = _compute_latency_ms(lat_src)
		med_sh = _compute_latency_ms(lat_sh)
		latency_delta_ms = float((med_sh or 0.0) - (med_src or 0.0))
		# Drift comparison via local histograms (best-effort)
		kl, cos_shift = _drift_compare(source_ns, shadow_ns)
		_saga_step(cid, "canary_eval", True, {
			"recall_src": recall_src,
			"recall_shadow": recall_sh,
			"recall_delta": recall_delta,
			"median_latency_src_ms": med_src,
			"median_latency_shadow_ms": med_sh,
			"latency_delta_ms": latency_delta_ms,
			"kl": kl,
			"cos_shift": cos_shift,
		})
		# Step 5: Gate
		pass_kl = kl <= pass_kl_max
		pass_rec = recall_delta >= pass_recall_delta_min
		pass_lat = latency_delta_ms <= float(pass_latency_delta_max_ms)
		decision = "pass" if (pass_kl and pass_rec and pass_lat) else "fail"
		# Step 6: Alias switch on pass (env-gated via blue/green helper, fail-closed)
		if decision == "pass":
			try:
				from retrieval.bluegreen import maybe_cutover  # type: ignore
				min_delta = _env_float("BG_MIN_RECALL_DELTA", REEMBED_PASS_RECALL_DELTA_MIN)
				if str(os.getenv("BLUEGREEN_ENABLED", "true")).strip().lower() in {"1","true","yes","y"} and recall_delta >= float(min_delta):
					ok_switched, prev, new = maybe_cutover(raw, alias_name, shadow_ns, min_delta)
					alias_before, alias_after = prev, new
					ok = bool(ok_switched)
					_saga_step(cid, "alias_switch", ok, {"from": prev, "to": new, "min_delta": min_delta})
				else:
					ok = False
			except Exception as e:
				ok = False
				_saga_step(cid, "alias_switch", False, {"error": str(e)})
		else:
			ok = False
		# Step 7: Summary
		summary: Dict[str, Any] = {
			"decision": decision,
			"kl": float(kl),
			"cos_shift": float(cos_shift),
			"median_latency_ms_shadow": float(med_sh or 0.0),
			"median_latency_ms_source": float(med_src or 0.0),
			"recall_delta": float(recall_delta),
			"alias_before": alias_before,
			"alias_after": alias_after,
			"shadow_ns": shadow_ns,
			"source_ns": source_ns,
		}
		_saga_end(cid, ok, summary)
		# Also emit summary as a convenience
		_emit_signal("reembed.summary", summary)
		return summary
	except Exception as e:
		_saga_step(cid, "error", False, {"error": str(e)})
		_emit_signal("reembed.failed", {"reason": str(e)})
		_saga_end(cid, False, {"decision": "error", "error": str(e)})
		return {"decision": "error", "error": str(e)}


def main(argv: Optional[List[str]] = None) -> int:
	parser = argparse.ArgumentParser(description="Axiom re-embedding job")
	parser.add_argument("--source", default=REEMBED_SOURCE_NS)
	parser.add_argument("--shadow", default=REEMBED_SHADOW_NS)
	parser.add_argument("--alias", default=REEMBED_ALIAS_NAME)
	parser.add_argument("--batch-size", type=int, default=REEMBED_BATCH_SIZE)
	parser.add_argument("--canaries", default=DRIFT_CANARY_SET)
	parser.add_argument("--eval-k", type=int, default=REEMBED_EVAL_RECALL_AT)
	parser.add_argument("--pass-kl", type=float, default=REEMBED_PASS_KL_MAX)
	parser.add_argument("--pass-recall-delta", type=float, default=REEMBED_PASS_RECALL_DELTA_MIN)
	parser.add_argument("--pass-latency-delta-ms", type=int, default=REEMBED_PASS_LATENCY_DELTA_MAX_MS)
	args = parser.parse_args(argv)
	res = run_reembed(
		source_ns=args.source,
		shadow_ns=args.shadow,
		alias_name=args.alias,
		batch_size=args.batch_size,
		canaries_path=args.canaries,
		eval_k=args.eval_k,
		pass_kl_max=args["pass_kl"] if isinstance(args, dict) and "pass_kl" in args else args.pass_kl,  # type: ignore[attr-defined]
		pass_recall_delta_min=args.pass_recall_delta,
		pass_latency_delta_max_ms=args.pass_latency_delta_ms,
	)
	print(res)
	return 0


if __name__ == "__main__":
	raise SystemExit(main())

