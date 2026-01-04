#!/usr/bin/env python3
"""
Smoke test: verify LLM server reachability and chat→completion fallback.

Behavior:
- GET {LLM_API_BASE}/health
- GET {LLM_API_BASE}/v1/models
- POST {LLM_API_BASE}/v1/chat/completions with a *short* timeout (default 3s)
  - if chat hangs/404/405/unsupported: fall back to POST /v1/completions

Env:
- LLM_API_BASE (preferred), LLM_API_URL (legacy): base URL WITHOUT trailing slash.
- LLM_MODEL_ID / LLM_MODEL: model id string from /v1/models (optional).
- AXIOM_REQUIRE_CHAT=true|false: if true, do not fallback (fail loudly).
- SMOKE_CHAT_TIMEOUT_SEC (default 3)
- SMOKE_COMPLETION_TIMEOUT_SEC (default 15)
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request


def _base() -> str:
    b = (os.getenv("LLM_API_BASE") or os.getenv("LLM_API_URL") or "http://127.0.0.1:11434").strip().rstrip("/")
    return b


def _v1(base: str) -> str:
    return base if base.endswith("/v1") else (base + "/v1")


def _model() -> str:
    return (os.getenv("LLM_MODEL_ID") or os.getenv("LLM_MODEL") or "").strip()


def _bool(name: str, default: bool = False) -> bool:
    v = (os.getenv(name) or ("true" if default else "false")).strip().lower()
    return v in {"1", "true", "yes", "y", "on"}


def _timeout(name: str, default: float) -> float:
    try:
        return float(os.getenv(name) or default)
    except Exception:
        return float(default)


def _req(url: str, *, method: str = "GET", payload: dict | None = None, timeout: float = 5.0) -> tuple[int, str]:
    headers = {"Accept": "application/json"}
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    api_key = (os.getenv("OPENAI_API_KEY") or os.getenv("LLM_API_KEY") or "").strip()
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=float(timeout)) as r:
        body = r.read().decode("utf-8", errors="ignore")
        return int(getattr(r, "status", 0) or 0), body


def main() -> int:
    base = _base()
    v1 = _v1(base)
    require_chat = _bool("AXIOM_REQUIRE_CHAT", False)
    chat_timeout = _timeout("SMOKE_CHAT_TIMEOUT_SEC", 3.0)
    completion_timeout = _timeout("SMOKE_COMPLETION_TIMEOUT_SEC", 15.0)

    print(f"base={base} v1={v1} require_chat={require_chat}")

    # 1) /health
    try:
        code, _ = _req(f"{base}/health", timeout=2.0)
        print(f"GET /health -> {code}")
    except Exception as e:
        print(f"GET /health failed: {type(e).__name__}: {e}")
        return 2

    # 2) /v1/models
    try:
        code, body = _req(f"{v1}/models", timeout=2.0)
        print(f"GET /v1/models -> {code} (len={len(body)})")
    except Exception as e:
        print(f"GET /v1/models failed: {type(e).__name__}: {e}")
        return 3

    model = _model()
    if not model:
        # best-effort: let server pick default if it supports it
        model = "unknown"

    prompt = "Say 'ok' in one word."

    # 3) chat (short timeout) then fallback to completion
    chat_payload = {"model": model, "messages": [{"role": "user", "content": prompt}], "stream": False}
    try:
        code, body = _req(f"{v1}/chat/completions", method="POST", payload=chat_payload, timeout=chat_timeout)
        print(f"POST /v1/chat/completions -> {code} (len={len(body)})")
        return 0
    except urllib.error.HTTPError as e:
        status = int(getattr(e, "code", 0) or 0)
        print(f"POST /v1/chat/completions HTTPError -> {status}")
        if require_chat:
            return 4
        if status not in {404, 405}:
            # Still allow fallback for other common "unsupported" responses.
            pass
    except Exception as e:
        print(f"POST /v1/chat/completions failed: {type(e).__name__}: {e}")
        if require_chat:
            return 4

    completion_payload = {"model": model, "prompt": f"User: {prompt}\n\nAssistant:"}
    try:
        code, body = _req(f"{v1}/completions", method="POST", payload=completion_payload, timeout=completion_timeout)
        print(f"POST /v1/completions (fallback) -> {code} (len={len(body)})")
        # best-effort: show a short preview
        try:
            j = json.loads(body)
            txt = (((j.get("choices") or [{}])[0].get("text") or "")[:120]).strip()
            print("completion_preview:", txt)
        except Exception:
            pass
        return 0
    except Exception as e:
        print(f"POST /v1/completions failed: {type(e).__name__}: {e}")
        return 5


if __name__ == "__main__":
    raise SystemExit(main())

