from __future__ import annotations

import json
from typing import Any, Dict, List


def load_canaries(path: str) -> List[Dict[str, Any]]:
	"""Load canary queries from a JSONL file.

	Each line must be a JSON object with:
	- q: string query
	- labels: list of document ids/keys (strings)

	Bad lines are logged to stdout and skipped (fail-closed).
	"""
	items: List[Dict[str, Any]] = []
	try:
		with open(path, "r") as f:
			for ln, line in enumerate(f, start=1):
				line = line.strip()
				if not line:
					continue
				try:
					obj = json.loads(line)
					q = obj.get("q")
					labels = obj.get("labels")
					if not isinstance(q, str) or not isinstance(labels, list):
						print(f"[canary] skip invalid line {ln}")
						continue
					labels_s = [str(x) for x in labels if isinstance(x, (str, int))]
					items.append({"q": q, "labels": labels_s})
				except Exception as e:
					print(f"[canary] skip line {ln}: {e}")
	except FileNotFoundError:
		print(f"[canary] file not found: {path}")
	except Exception as e:
		print(f"[canary] load error: {e}")
	return items


def evaluate_recall_k(results: List[str], labels: List[str], k: int) -> float:
	"""Compute recall@k given retrieved ids/text keys and label ids.

	Both results and labels are treated as sets after truncation to k.
	Returns a float between 0 and 1.
	"""
	try:
		if k <= 0:
			return 0.0
		got = set([str(x) for x in (results or [])][:k])
		exp = set([str(x) for x in (labels or [])])
		if not exp:
			return 0.0
		return float(len(got & exp)) / float(len(exp))
	except Exception:
		return 0.0


__all__ = ["load_canaries", "evaluate_recall_k"]

