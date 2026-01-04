#!/usr/bin/env python3
from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys
import urllib.request
import urllib.error
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

# Ensure repo root is importable when running from scripts/
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

# Minimize any chance an LLM client tries to run by default
os.environ.setdefault("OPENAI_API_KEY", "")
os.environ.setdefault("ANTHROPIC_API_KEY", "")
os.environ.setdefault("GEMINI_API_KEY", "")


@dataclass
class StepResult:
    name: str
    status: str  # PASS | FAIL | SKIPPED
    detail: Optional[str] = None

    def summary_row(self) -> str:
        icon = {
            "PASS": "✅",
            "FAIL": "❌",
            "SKIPPED": "⚠️",
        }.get(self.status, "ℹ️")
        note = f" ({self.detail})" if self.detail else ""
        return f"{icon} {self.name}: {self.status}{note}"


def _detect_qdrant_url() -> Optional[str]:
    url = (os.getenv("QDRANT_URL", "").strip() or None)
    if url:
        return url.rstrip("/")
    host = (os.getenv("QDRANT_HOST", "").strip() or None)
    port = (os.getenv("QDRANT_PORT", "").strip() or None)
    if host or port:
        host = host or "localhost"
        port = port or "6333"
        return f"http://{host}:{port}"
    # Default fallback used throughout the repo
    return "http://localhost:6333"


def _qdrant_available(timeout_s: float = 2.0) -> Tuple[bool, str]:
    base = _detect_qdrant_url()
    if not base:
        return False, "QDRANT_URL not configured"
    url = f"{base}/health"
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:  # nosec B310
            ok = (200 <= resp.status < 300)
            return (ok, f"HTTP {resp.status}")
    except urllib.error.URLError as e:
        return False, f"{type(e).__name__}: {e}"
    except Exception as e:  # pragma: no cover
        return False, f"{type(e).__name__}: {e}"


def run_import_test() -> StepResult:
    modules = [
        "memory_response_pipeline",
        "axiom_qdrant_client",
        "retrieval.rerank",
        "identity.preloader",
    ]
    failures: Dict[str, str] = {}
    for mod in modules:
        try:
            importlib.import_module(mod)
        except Exception as e:  # pragma: no cover
            failures[mod] = f"{type(e).__name__}: {e}"
    if failures:
        detail = "; ".join(f"{m}: {err}" for m, err in failures.items())
        return StepResult("Import test", "FAIL", detail)
    return StepResult("Import test", "PASS")


def run_coverage_gating_tests() -> StepResult:
    cmd = [sys.executable, "-m", "pytest", "-q", "tests/test_coverage_gating_examples.py"]
    env = os.environ.copy()
    env["PYTHONPATH"] = REPO_ROOT + os.pathsep + env.get("PYTHONPATH", "")
    proc = subprocess.run(cmd, cwd=REPO_ROOT, env=env, capture_output=True, text=True)
    if proc.returncode == 0:
        return StepResult("Coverage gating unit tests", "PASS")
    # Trim noisy output
    out = (proc.stdout or "") + "\n" + (proc.stderr or "")
    snippet = "\n".join(out.strip().splitlines()[-20:])
    return StepResult("Coverage gating unit tests", "FAIL", snippet)


def _parse_last_json_line(text: str) -> Optional[dict]:
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    for ln in reversed(lines):
        try:
            return json.loads(ln)
        except Exception:
            continue
    return None


def run_replay_harness() -> StepResult:
    available, reason = _qdrant_available()
    if not available:
        return StepResult("Replay test", "SKIPPED", f"Qdrant not available: {reason}")

    query = "What is Axiom's memory retrieval pipeline?"
    cmd = [sys.executable, os.path.join(REPO_ROOT, "retrieval", "test_replay.py"), "--query", query]
    env = os.environ.copy()
    env["PYTHONPATH"] = REPO_ROOT + os.pathsep + env.get("PYTHONPATH", "")
    proc = subprocess.run(cmd, cwd=REPO_ROOT, env=env, capture_output=True, text=True)

    if proc.returncode != 0:
        snippet = "\n".join(((proc.stdout or "") + "\n" + (proc.stderr or "")).strip().splitlines()[-20:])
        return StepResult("Replay test", "FAIL", f"Exited {proc.returncode}: {snippet}")

    obj = _parse_last_json_line(proc.stdout)
    if not isinstance(obj, dict):
        return StepResult("Replay test", "FAIL", "No JSON output detected")

    missing: List[str] = []
    if "coverage" not in obj:
        missing.append("coverage")
    if "top_matches" not in obj:
        missing.append("top_matches")

    if missing:
        return StepResult("Replay test", "FAIL", f"Missing keys: {', '.join(missing)}")

    return StepResult("Replay test", "PASS")


def main() -> int:
    results: List[StepResult] = []

    results.append(run_import_test())
    results.append(run_coverage_gating_tests())
    results.append(run_replay_harness())

    for r in results:
        print(r.summary_row())

    failed = any(r.status == "FAIL" for r in results)
    if not failed:
        print("🎉 Axiom smoke test complete.")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
