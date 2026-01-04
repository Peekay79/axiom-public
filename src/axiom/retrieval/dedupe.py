from __future__ import annotations

import hashlib
from typing import Dict, List


def _hash(text: str) -> int:
	return int(hashlib.md5(text.encode("utf-8")).hexdigest()[:8], 16)


def jaccard(a: set[str], b: set[str]) -> float:
	if not a and not b:
		return 1.0
	return float(len(a & b)) / float(len(a | b) or 1)


def cluster_drop(items: List[Dict], threshold: float = 0.85) -> List[Dict]:
	seen: list[tuple[int, set[str]]] = []
	out: List[Dict] = []
	for it in items:
		content = (it.get("content") or it.get("text") or "").strip()
		if not content:
			out.append(it)
			continue
		shingles = set(content.lower().split())
		dup = False
		for _, s in seen:
			if jaccard(shingles, s) >= threshold:
				dup = True
				break
		if not dup:
			seen.append((_hash(content), shingles))
			out.append(it)
	return out