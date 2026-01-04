#!/usr/bin/env python3
from __future__ import annotations

import os
from typing import Dict, Optional


def _env(name: str, default: Optional[str] = None) -> str:
    v = os.getenv(name)
    return (v if v is not None else (default or "")).strip()


def _truthy(name: str, default: bool = False) -> bool:
    v = _env(name, str(default))
    return v.lower() in {"1", "true", "yes", "y"}


def resolve_llm() -> Dict[str, object]:
    """
    Resolve LLM provider configuration from environment variables.

    Returns a dict: {provider, base_url, model, api_key, ok:bool, reason?:str}
    """
    provider = _env("LLM_PROVIDER") or None
    base = _env("LLM_API_BASE") or _env("LLM_BASE_URL") or _env("OLLAMA_URL") or _env("OPENAI_BASE_URL", "https://api.openai.com")
    model = _env("LLM_MODEL_ID") or _env("LLM_MODEL_NAME") or _env("OPENAI_MODEL") or _env("OLLAMA_MODEL") or "llama3.2:1b"
    api_key = _env("OPENAI_API_KEY") or _env("LLM_API_KEY") or None

    ok = True
    reason = None
    if not base:
        ok = False
        reason = "no_base_url"
    if provider is None:
        # infer
        if "ollama" in base:
            provider = "ollama"
        else:
            provider = "openai_compatible"

    return {
        "provider": provider,
        "base_url": base.rstrip("/") if base else base,
        "model": model,
        "api_key": api_key,
        "ok": ok,
        "reason": reason,
    }


def resolve_vector() -> Dict[str, object]:
    """
    Resolve vector/Qdrant configuration from environment variables.

    Supports legacy USE_QDRANT_BACKEND and canonical QDRANT_URL/QDRANT_API_KEY.
    Returns: {url, api_key, https:bool, ok:bool, reason?:str}
    """
    # Canonical first
    url = _env("QDRANT_URL")
    if not url:
        # Legacy: QDRANT_URL host:port → assume http://host:port
        vurl = _env("QDRANT_URL")
        if vurl:
            url = vurl if "://" in vurl else f"http://{vurl}"
        else:
            host = _env("QDRANT_HOST") or "localhost"
            port = _env("QDRANT_PORT", "6333")
            url = f"http://{host}:{port}"

    api_key = _env("QDRANT_API_KEY") or _env("AX_QDRANT_API_KEY") or None
    use_https = _truthy("QDRANT_USE_HTTPS", False)

    ok = True
    reason = None
    if not url:
        ok = False
        reason = "no_vector_url"

    return {
        "url": url.rstrip("/") if url else url,
        "api_key": api_key,
        "https": bool(use_https),
        "ok": ok,
        "reason": reason,
    }


def emit_summary_once() -> None:
    try:
        from pods.cockpit.cockpit_reporter import write_signal

        llm = resolve_llm()
        vec = resolve_vector()
        write_signal("config", "resolver_summary", {"llm": llm, "vector": vec})
    except Exception:
        pass

