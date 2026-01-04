from __future__ import annotations

import math
import os
import random
from pathlib import Path


def test_kl_and_shift_basic(tmp_path, monkeypatch):
	# Arrange: independent reproducible RNG
	random.seed(42)
	# Create two cosine dists: centered at 0.2 and 0.4
	from retrieval.drift import cosine_histogram, kl_divergence, compute_cosine_shift

	def synth_pairs(mu: float, n: int = 500):
		pairs = []
		for _ in range(n):
			# Build 2D vectors with desired cosine approximately
			# vector a = (1, 0); vector b = (mu, sqrt(1-mu^2))
			a = [1.0, 0.0]
			b = [mu, math.sqrt(max(0.0, 1.0 - mu * mu))]
			pairs.append((a, b))
		return pairs

	p_hist = cosine_histogram(synth_pairs(0.2))
	q_hist = cosine_histogram(synth_pairs(0.4))
	kl = kl_divergence(p_hist, q_hist)
	shift = compute_cosine_shift(p_hist, q_hist)
	assert kl >= 0.0
	assert shift > 0.0


def test_record_and_emit_fail_closed(tmp_path, monkeypatch):
	# Redirect drift state dir
	monkeypatch.setenv("DRIFT_STATE_DIR", str(tmp_path))
	monkeypatch.setenv("RETRIEVAL_DRIFT_ENABLED", "true")
	from retrieval.drift import record_vector_sample, snapshot_stats, maybe_emit_drift

	# Emit some vectors with small noise
	for i in range(200):
		v = [1.0 + random.uniform(-0.01, 0.01), 0.0]
		record_vector_sample("test_ns", v)

	# No exception and stats are available
	ss = snapshot_stats("test_ns")
	assert isinstance(ss, dict)
	stats = ss.get("stats") or {}
	assert int(stats.get("n") or 0) > 0

	# Emission should not throw even if cockpit disabled
	maybe_emit_drift("test_ns")

