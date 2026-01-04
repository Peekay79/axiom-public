# config/llm_config.py
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

ALLOWED_LLM_MODES = {"auto", "chat", "completion"}

ENV_URL_KEYS = [
    "LLM_API_BASE",  # Preferred for openai_compatible
    "LLM_API_URL",   # Legacy alias (still supported; normalized upstream where possible)
    "LLM_BASE_URL",  # Legacy alias
    "OLLAMA_URL",    # For ollama provider
    "OPENAI_BASE_URL",  # For openai provider
    "OLLAMA_HOST",   # Legacy ollama alias
    "OLLAMA_BASE_URL",  # Legacy ollama alias
]

ENV_MODEL_KEYS = [
    "LLM_MODEL_ID",  # Preferred - exact string from /v1/models
    "LLM_MODEL",     # Legacy alias used by some .env.discord files
    "LLM_MODEL_NAME",
    "DEFAULT_LLM_MODEL",
    "OPENAI_MODEL",
    "OLLAMA_MODEL",
    "MODEL_NAME",
]


def _first_env(keys: list[str]) -> str | None:
    for k in keys:
        v = os.getenv(k)
        if v and v.strip():
            return v.strip()
    return None


def resolve_llm_base_url(fallback: str | None = "http://localhost:11434") -> str:
    base = _first_env(ENV_URL_KEYS) or fallback or ""
    base = base.strip().rstrip("/")
    return base


def resolve_llm_model(default: str = "llama3.2:1b") -> str:
    model = _first_env(ENV_MODEL_KEYS) or default
    return model.strip()


def resolve_llm_mode(default: str = "auto") -> str:
    """
    Canonical request mode for OpenAI-compatible endpoints.
    Allowed values: chat|completion|auto (default auto).
    """
    raw = (os.getenv("LLM_MODE", "") or "").strip().lower() or default
    if raw not in ALLOWED_LLM_MODES:
        return default
    return raw


def openai_v1_base(base_url: str) -> str:
    """
    Normalize an OpenAI-compatible base URL so it ends with '/v1' exactly once.
    """
    b = (base_url or "").strip().rstrip("/")
    if not b:
        return ""
    return b if b.endswith("/v1") else (b + "/v1")


def parse_openai_models_capabilities(models_json: dict, model_id: str | None) -> set[str] | None:
    """
    Extract a model's capabilities set (lowercased) from an OpenAI-style /v1/models response.

    Expected shape: {"object":"list","data":[{"id":"...","capabilities":["chat","completion"], ...}, ...]}
    Returns None if capabilities are absent/unknown.
    """
    try:
        data = (models_json or {}).get("data") or []
        if not isinstance(data, list) or not data:
            return None
        chosen = None
        mid = (model_id or "").strip()
        if mid:
            for m in data:
                if isinstance(m, dict) and (m.get("id") or "").strip() == mid:
                    chosen = m
                    break
        # If we couldn't match and there's exactly one model, assume that's the active one.
        if chosen is None and len(data) == 1 and isinstance(data[0], dict):
            chosen = data[0]
        if not isinstance(chosen, dict):
            return None
        caps = chosen.get("capabilities")
        if not caps:
            return None
        if isinstance(caps, str):
            return {caps.strip().lower()} if caps.strip() else None
        if isinstance(caps, list):
            out = {str(x).strip().lower() for x in caps if str(x).strip()}
            return out or None
        return None
    except Exception:
        return None


def decide_llm_mode_from_capabilities(caps: set[str] | None) -> str | None:
    """
    Decide chat vs completion from capabilities.
    Returns None when unknown/absent.
    """
    if not caps:
        return None
    if "chat" in caps:
        return "chat"
    if "completion" in caps:
        return "completion"
    return None


def fetch_openai_models(
    base_url: str,
    *,
    api_key: str | None = None,
    timeout: float = 2.0,
) -> dict | None:
    """
    Best-effort GET /v1/models using stdlib urllib (no extra deps).
    Returns parsed JSON dict on success, else None.
    """
    base_v1 = openai_v1_base(base_url)
    if not base_v1:
        return None
    url = f"{base_v1}/models"
    try:
        req = urllib.request.Request(url)
        if api_key:
            req.add_header("Authorization", f"Bearer {api_key}")
        with urllib.request.urlopen(req, timeout=float(timeout)) as r:
            body = r.read()
        return json.loads(body.decode("utf-8", errors="ignore"))
    except Exception:
        return None


def log_llm_config(logger=None) -> None:
    base = resolve_llm_base_url()
    model = resolve_llm_model()
    msg = f"[LLMConfig] base_url={base or '<unset>'} model={model}"
    if logger:
        try:
            logger.info(msg)
            return
        except Exception:
            pass
    print(msg)


def health_check(base_url: str | None = None, timeout: float = 2.0) -> dict:
    """
    Try Ollama-style /api/tags then OpenAI-style /v1/models.
    Returns a dict with {'ok': bool, 'style': 'ollama'|'openai'|None, 'error': str|None}.
    """
    base = (base_url or resolve_llm_base_url() or "").rstrip("/")
    if not base:
        return {"ok": False, "style": None, "error": "No base URL resolved"}

    def _get(path: str):
        req = urllib.request.Request(f"{base}{path}")
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read()

    # Try Ollama first
    try:
        _ = _get("/api/tags")
        return {"ok": True, "style": "ollama", "error": None}
    except Exception as e:
        last_err = str(e)

    # Then OpenAI style
    try:
        body = _get("/v1/models")
        # basic sanity
        try:
            _ = json.loads(body.decode("utf-8", errors="ignore"))
        except Exception:
            pass
        return {"ok": True, "style": "openai", "error": None}
    except Exception as e:
        last_err = str(e)

    return {"ok": False, "style": None, "error": last_err}
