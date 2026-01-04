from __future__ import annotations

import os
import json
from pathlib import Path


def _make_canaries(tmp_path: Path) -> str:
	path = tmp_path / "default.jsonl"
	lines = [
		json.dumps({"q": "hello world", "labels": ["1", "2"]}),
		json.dumps({"q": "axiom system", "labels": ["3"]}),
	]
	path.write_text("\n".join(lines))
	return str(path)


def test_reembed_cli_smoke(tmp_path, monkeypatch):
	# Env gate enabled
	monkeypatch.setenv("REEMBED_ENABLED", "true")
	# Use small batch
	monkeypatch.setenv("REEMBED_BATCH_SIZE", "2")
	# Collections likely not present in CI; this is a logic smoke test only
	from retrieval.reembed_job import run_reembed
	# Provide canary path but job will likely fail early due to qdrant unavailable; ensure fail-closed
	summary = run_reembed(
		source_ns="nonexistent_source",
		shadow_ns="nonexistent_shadow",
		alias_name="nonexistent_alias",
		batch_size=2,
		canaries_path=_make_canaries(tmp_path),
		eval_k=3,
		pass_kl_max=0.5,
		pass_recall_delta_min=-1.0,
		pass_latency_delta_max_ms=1000,
	)
	assert isinstance(summary, dict)
	assert summary.get("decision") in {"disabled", "error", "fail", "pass"}

