from __future__ import annotations

import json
import math
import os
import random
import statistics
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple


# ──────────────────────────────────────────────────────────────────────────────
# Environment flags and knobs (fail-closed defaults)
# ──────────────────────────────────────────────────────────────────────────────


def _env_bool(name: str, default: bool) -> bool:
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


RETRIEVAL_DRIFT_ENABLED = _env_bool("RETRIEVAL_DRIFT_ENABLED", True)
DRIFT_ALERT_KL = _env_float("DRIFT_ALERT_KL", 0.15)
DRIFT_ALERT_COSINE_SHIFT = _env_float("DRIFT_ALERT_COSINE_SHIFT", 0.08)
DRIFT_WINDOW_DOCS = max(100, _env_int("DRIFT_WINDOW_DOCS", 5000))
DRIFT_DIR = Path(os.getenv("DRIFT_STATE_DIR", "drift"))


# ──────────────────────────────────────────────────────────────────────────────
# Core math utilities
# ──────────────────────────────────────────────────────────────────────────────


def sample_vector_norms(vectors: List[List[float]]) -> Dict[str, float]:
	if not vectors:
		return {"mean": 0.0, "p95": 0.0, "n": 0}
	try:
		norms: List[float] = []
		for vec in vectors:
			if not isinstance(vec, list) or not vec:
				continue
			# L2 norm
			norm = math.sqrt(sum((v or 0.0) * (v or 0.0) for v in vec))
			norms.append(float(norm))
		if not norms:
			return {"mean": 0.0, "p95": 0.0, "n": 0}
		mean_val = statistics.fmean(norms)
		try:
			qs = statistics.quantiles(norms, n=100)
			p95_val = float(qs[94])
		except Exception:
			s = sorted(norms)
			idx = int(max(0, len(s) - 1) * 0.95) or 0
			p95_val = float(s[idx])
		return {"mean": float(mean_val), "p95": float(p95_val), "n": int(len(norms))}
	except Exception:
	return {"mean": 0.0, "p95": 0.0, "n": 0}


def _cosine(a: List[float], b: List[float]) -> float:
	try:
		if not a or not b:
			return 0.0
		if len(a) != len(b):
			# best-effort: truncate to min length
			m = min(len(a), len(b))
			a = a[:m]
			b = b[:m]
		dot = 0.0
		norm_a = 0.0
		norm_b = 0.0
		for x, y in zip(a, b):
			dot += (x or 0.0) * (y or 0.0)
			norm_a += (x or 0.0) * (x or 0.0)
			norm_b += (y or 0.0) * (y or 0.0)
		da = math.sqrt(norm_a)
		db = math.sqrt(norm_b)
		if da <= 0.0 or db <= 0.0:
			return 0.0
		return float(dot / (da * db))
	except Exception:
	return 0.0


def cosine_histogram(sample_pairs: List[Tuple[List[float], List[float]]], bins: int = 21) -> List[float]:
	"""Return normalized histogram over cosine similarity in [-1, 1].

	Args:
		bins: number of buckets (default 21 → width ~0.095).
	"""
	if bins <= 1:
		bins = 21
	counts = [0] * bins
	if not sample_pairs:
		return [0.0] * bins
	for a, b in sample_pairs:
		c = _cosine(a, b)
		# Map [-1,1] → [0,bins-1]
		pos = int((c + 1.0) / 2.0 * (bins - 1))
		pos = max(0, min(bins - 1, pos))
		counts[pos] += 1
	# Normalize
	total = float(sum(counts)) or 1.0
	return [float(c) / total for c in counts]


def kl_divergence(p_hist: List[float], q_hist: List[float], eps: float = 1e-9) -> float:
	"""Compute KL(P || Q) over discrete distributions with smoothing.

	Returns 0.0 if inputs invalid.
	"""
	try:
		if not p_hist or not q_hist:
			return 0.0
		m = min(len(p_hist), len(q_hist))
		kl = 0.0
		for i in range(m):
			p = float(max(eps, p_hist[i]))
			q = float(max(eps, q_hist[i]))
			kl += p * math.log(p / q)
		return float(max(0.0, kl))
	except Exception:
	return 0.0


def compute_cosine_shift(prev_hist: List[float], curr_hist: List[float]) -> float:
	"""Approximate distribution shift as absolute difference of expected value.

	This is a lightweight proxy for EMD. We compute the expected cosine value
	under each histogram by using equally spaced bin centers in [-1, 1] and
	return |E_curr - E_prev|.
	"""
	try:
		if not prev_hist or not curr_hist:
			return 0.0
		m = min(len(prev_hist), len(curr_hist))
		# Bin centers over [-1,1]
		if m <= 1:
			return 0.0
		step = 2.0 / (m - 1)
		centers = [-1.0 + i * step for i in range(m)]
		def _exp(hist: List[float]) -> float:
			return float(sum(h * c for h, c in zip(hist[:m], centers)))
		return float(abs(_exp(curr_hist) - _exp(prev_hist)))
	except Exception:
	return 0.0


# ──────────────────────────────────────────────────────────────────────────────
# Reporters (Cockpit signals; fail-closed)
# ──────────────────────────────────────────────────────────────────────────────


def emit_embedding_stats(ns: str, stats: Dict[str, Any]) -> None:
	try:
		from pods.cockpit.cockpit_reporter import write_signal  # type: ignore
	except Exception:
		def write_signal(_pod: str, _sig: str, _payload: dict) -> None:  # type: ignore
			pass
	try:
		write_signal("governor", f"embedding_stats.{ns}", {
			"n": int(stats.get("n") or 0),
			"mean": float(stats.get("mean") or 0.0),
			"p95": float(stats.get("p95") or 0.0),
		})
	except Exception:
		pass


def emit_drift(ns: str, kl: float, cos_shift: float) -> None:
	try:
		from pods.cockpit.cockpit_reporter import write_signal  # type: ignore
	except Exception:
		def write_signal(_pod: str, _sig: str, _payload: dict) -> None:  # type: ignore
			pass
	try:
		write_signal("governor", f"retrieval_drift.{ns}", {
			"kl": float(max(0.0, kl)),
			"cos_shift": float(max(0.0, cos_shift)),
		})
	except Exception:
		pass


# ──────────────────────────────────────────────────────────────────────────────
# Local rolling state (histograms + norms), idempotent and bounded
# ──────────────────────────────────────────────────────────────────────────────


_LOCKS: Dict[str, threading.Lock] = {}


def _ns_lock(ns: str) -> threading.Lock:
	lock = _LOCKS.get(ns)
	if lock is None:
		lock = threading.Lock()
		_LOCKS[ns] = lock
	return lock


def _state_path(ns: str) -> Path:
	DRIFT_DIR.mkdir(parents=True, exist_ok=True)
	return DRIFT_DIR / f"{ns}.hist.json"


def _load_state(ns: str) -> Dict[str, Any]:
	path = _state_path(ns)
	try:
		if path.exists():
			with open(path, "r") as f:
				return json.load(f) or {}
	except Exception:
		return {}
	return {}


def _save_state(ns: str, state: Dict[str, Any]) -> None:
	try:
		with open(_state_path(ns), "w") as f:
			json.dump(state, f)
	except Exception:
		pass


def _now_iso() -> str:
	try:
		return datetime.utcnow().isoformat()
	except Exception:
		return ""


def record_vector_sample(ns: str, vector: List[float]) -> None:
	"""Record a single vector into rolling drift state (fail-closed).

	- Tracks last DRIFT_WINDOW_DOCS norms (for mean/p95 computation)
	- Maintains a small ring buffer of recent vectors to create cosine pairs
	- Updates cosine histogram counts incrementally
	"""
	if not RETRIEVAL_DRIFT_ENABLED:
		return
	if not isinstance(vector, list) or not vector:
		return
	lock = _ns_lock(ns)
	with lock:
		state = _load_state(ns)
		# Norms buffer (bounded)
		norms = state.get("norms") or []
		if not isinstance(norms, list):
			norms = []
		# Compute norm quickly
		try:
			norm_val = math.sqrt(sum((v or 0.0) * (v or 0.0) for v in vector))
		except Exception:
			norm_val = 0.0
		norms.append(float(norm_val))
		if len(norms) > DRIFT_WINDOW_DOCS:
			norms = norms[-DRIFT_WINDOW_DOCS:]
		state["norms"] = norms
		# Vector reservoir for cosine pairing
		reservoir = state.get("_reservoir") or []
		if not isinstance(reservoir, list):
			reservoir = []
		# Keep small reservoir (sqrt of window, min 50, max 500)
		cap = max(50, min(500, int(math.sqrt(DRIFT_WINDOW_DOCS))))
		if len(reservoir) < cap:
			reservoir.append(vector)
		else:
			# Reservoir sampling: replace with probability cap/seen (approx via random idx)
			idx = random.randint(0, cap - 1)
			reservoir[idx] = vector
		state["_reservoir"] = reservoir
		# Update cosine histogram counts using one random pair
		bins = int(state.get("bins") or 21)
		if bins <= 1:
			bins = 21
		counts = state.get("cos_counts") or [0] * bins
		if len(counts) != bins:
			counts = [0] * bins
		if len(reservoir) >= 2:
			try:
				other = reservoir[random.randint(0, len(reservoir) - 2)]
				c = _cosine(vector, other)
				pos = int((c + 1.0) / 2.0 * (bins - 1))
				pos = max(0, min(bins - 1, pos))
				counts[pos] += 1
				state["cos_counts"] = counts
				state["cos_seen"] = int(state.get("cos_seen") or 0) + 1
			except Exception:
				pass
		# Initialize baseline snapshot if missing and we have some data
		if not state.get("baseline") and len(norms) >= min(200, DRIFT_WINDOW_DOCS // 10):
			# Take a conservative early baseline
			try:
				p = [float(c) / float(max(1, sum(counts))) for c in counts]
				state["baseline"] = {
					"cos_hist": p,
					"created_at": _now_iso(),
				}
			except Exception:
				state["baseline"] = {"cos_hist": [0.0] * bins, "created_at": _now_iso()}
		state["updated_at"] = _now_iso()
		_save_state(ns, state)


def maybe_emit_drift(ns: str) -> None:
	"""Compute and emit drift if enough data and throttled by a local timer.

	This function reads the local state, compares current histogram to baseline,
	and emits a Cockpit signal with KL and cosine_shift. Emission is throttled to
	once every ~5 minutes per namespace.
	"""
	if not RETRIEVAL_DRIFT_ENABLED:
		return
	lock = _ns_lock(ns)
	with lock:
		state = _load_state(ns)
		if not state:
			return
		last_emit_ts = float(state.get("_last_emit_ts") or 0.0)
		now = time.time()
		if now - last_emit_ts < 300.0:  # 5 minutes
			return
		counts: List[int] = state.get("cos_counts") or []
		if not counts or sum(counts) <= 0:
			return
		curr = [float(c) / float(max(1, sum(counts))) for c in counts]
		baseline = (state.get("baseline") or {}).get("cos_hist") or []
		if not baseline:
			return
		kl = kl_divergence(baseline, curr)
		shift = compute_cosine_shift(baseline, curr)
		emit_drift(ns, kl, shift)
		state["_last_emit_ts"] = now
		_save_state(ns, state)


def snapshot_stats(ns: str) -> Dict[str, Any]:
	"""Return current stats summary for diagnostics/tests (no I/O except read)."""
	state = _load_state(ns)
	try:
		norms = state.get("norms") or []
		stats = sample_vector_norms([[n] for n in norms])
		counts = state.get("cos_counts") or []
		p = [float(c) / float(max(1, sum(counts))) for c in counts] if counts else []
		b = (state.get("baseline") or {}).get("cos_hist") or []
		return {
			"stats": stats,
			"cos_hist": p,
			"baseline": b,
		}
	except Exception:
		return {"stats": {"mean": 0.0, "p95": 0.0, "n": 0}, "cos_hist": [], "baseline": []}


__all__ = [
	"sample_vector_norms",
	"cosine_histogram",
	"kl_divergence",
	"compute_cosine_shift",
	"emit_embedding_stats",
	"emit_drift",
	"record_vector_sample",
	"maybe_emit_drift",
	"snapshot_stats",
]

