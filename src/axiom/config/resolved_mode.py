#!/usr/bin/env python3
"""
Resolved mode helper for startup validation and logging.

Reads environment variables and computes a final vector path mode with
basic validation. Produces a small dict suitable for single-line JSON logging.

Precedence:
1) If USE_QDRANT_BACKEND is truthy → vector_path = "qdrant"
2) Else VECTOR_PATH (default "qdrant").

Validation:
- If vector_path == "adapter" then QDRANT_URL must be present.
- If vector_path == "qdrant" then a Qdrant host:port must be derivable
  from QDRANT_URL or QDRANT_HOST + QDRANT_PORT; otherwise raise.

This module does not mutate any environment variables or global configuration.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, List

import os
import json
from urllib.parse import urlparse


def _truthy(val: Optional[str]) -> bool:
    if val is None:
        return False
    return str(val).strip().lower() in {"1", "true", "yes", "y"}


def _host_port_from_url(url: str) -> tuple[Optional[str], Optional[int]]:
    try:
        parsed = urlparse(url if "://" in url else f"http://{url}")
        host = parsed.hostname
        port = parsed.port
        return host, port
    except Exception:
        return None, None


@dataclass
class ResolvedMode:
    role: str
    vector_path: str  # "qdrant" or "adapter"
    qdrant: Optional[str]  # "host:port" or None
    adapter_url: Optional[str]
    composite_scoring: bool
    request_id_header: str
    retrieval_min_count: int
    retrieval_min_sim: float
    retrieval_header: str
    adapter_resiliency: Optional[Dict[str, int]] = None
    # Extended visibility
    qdrant_url: Optional[str] = None
    warnings: Optional[List[Dict[str, Any]]] = None

    def as_dict(self) -> Dict[str, Any]:
        out = {
            "role": self.role,
            "vector_path": self.vector_path,
            "qdrant": self.qdrant,
            "adapter_url": self.adapter_url,
            "composite_scoring": self.composite_scoring,
            "request_id_header": self.request_id_header,
            "retrieval_min_count": self.retrieval_min_count,
            "retrieval_min_sim": self.retrieval_min_sim,
            "retrieval_header": self.retrieval_header,
        }
        # Include authoritative qdrant_url and any config warnings in banner
        out["qdrant_url"] = self.qdrant_url
        if self.warnings:
            out["warnings"] = self.warnings
        if self.adapter_resiliency is not None:
            out["adapter_resiliency"] = self.adapter_resiliency
        return out

    @classmethod
    def from_env(cls, env: Dict[str, str], default_role: Optional[str] = None) -> "ResolvedMode":
        # Resolve role
        role = (env.get("AXIOM_POD_ROLE") or default_role or "").strip() or (default_role or "")
        if not role:
            # Best-effort: infer from process/context later; keep empty if unknown
            role = ""

        # Resolve vector path
        if _truthy(env.get("USE_QDRANT_BACKEND")):
            vector_path = "qdrant"
        else:
            vp = (env.get("VECTOR_PATH") or "qdrant").strip().lower()
            vector_path = vp if vp in {"qdrant", "adapter"} else "qdrant"

        adapter_url: Optional[str] = (env.get("QDRANT_URL", "") or "").strip() or None

        # Composite scoring flag
        composite_scoring = _truthy(env.get("AXIOM_COMPOSITE_SCORING"))
        # Request ID header name (configurable)
        request_id_header = (env.get("AXIOM_REQUEST_ID_HEADER") or "X-Request-ID").strip() or "X-Request-ID"
        # Retrieval quality config
        try:
            retrieval_min_count = int((env.get("RETRIEVAL_MIN_COUNT") or "3").strip())
        except Exception:
            retrieval_min_count = 3
        # Retrieval similarity threshold (canonical default 0.30).
        # Precedence: AXIOM_RETRIEVAL_MIN_SIM → RETRIEVAL_MIN_SIM → 0.30
        try:
            raw = (env.get("AXIOM_RETRIEVAL_MIN_SIM") or env.get("RETRIEVAL_MIN_SIM") or "0.30").strip()
            retrieval_min_sim = float(raw)
        except Exception:
            retrieval_min_sim = 0.30
        retrieval_header = (env.get("AXIOM_RETRIEVAL_HEADER") or "X-Axiom-Retrieval").strip() or "X-Axiom-Retrieval"

        # Validate and resolve qdrant host:port
        qdrant_host_port: Optional[str] = None
        if vector_path == "adapter":
            if not adapter_url:
                raise ValueError("VECTOR_PATH=adapter requires QDRANT_URL to be set")
        else:  # qdrant
            # First try QDRANT_URL
            url = (env.get("QDRANT_URL") or "").strip()
            host: Optional[str] = None
            port: Optional[int] = None
            if url:
                host, port = _host_port_from_url(url)
            # Fall back to QDRANT_HOST/PORT
            if not host:
                host = (env.get("QDRANT_HOST") or "").strip() or None
            if port is None:
                port_str = (env.get("QDRANT_PORT") or "").strip()
                if port_str.isdigit():
                    try:
                        port = int(port_str)
                    except Exception:
                        port = None
            # Validate
            if not host:
                raise ValueError("Qdrant host not resolvable (set QDRANT_URL or QDRANT_HOST/QDRANT_PORT)")
            if port is None:
                # Default to 6333 if entirely unspecified; this does not alter any prod URLs
                port = 6333
            qdrant_host_port = f"{host}:{port}"

        # Compute authoritative Qdrant URL and any configuration warnings (env-only at this stage)
        try:
            chosen_url, _source, warnings = resolve_qdrant_url(cli_url=None)
        except Exception:
            chosen_url, warnings = None, []

        # Adapter resiliency (always include to make startup banner explicit for vector role)
        def _to_int(name: str, default_val: int) -> int:
            try:
                return int((env.get(name) or str(default_val)).strip())
            except Exception:
                return default_val

        adapter_resiliency = {
            "timeout_sec": _to_int("VECTOR_ADAPTER_TIMEOUT_SEC", 8),
            "retries": _to_int("VECTOR_ADAPTER_RETRIES", 2),
            "circuit_open_sec": _to_int("VECTOR_ADAPTER_CIRCUIT_OPEN_SEC", 20),
        }

        return cls(
            role=role,
            vector_path=vector_path,
            qdrant=qdrant_host_port,
            adapter_url=adapter_url,
            composite_scoring=composite_scoring,
            request_id_header=request_id_header,
            retrieval_min_count=retrieval_min_count,
            retrieval_min_sim=retrieval_min_sim,
            retrieval_header=retrieval_header,
            adapter_resiliency=adapter_resiliency if role == "vector" else None,
            qdrant_url=chosen_url,
            warnings=warnings or None,
        )

    def json_line(self, component: str = "startup") -> str:
        payload = {"component": component, "resolved_mode": self.as_dict()}
        return json.dumps(payload, separators=(",", ":"), ensure_ascii=False)


# ──────────────────────────────────────────────────────────────────────────────
# Qdrant URL Resolver (authoritative URL computation with precedence & warnings)
# ──────────────────────────────────────────────────────────────────────────────

def _norm(url: str | None) -> str | None:
    if not url:
        return None
    u = urlparse(url)
    return url if u.scheme else f"http://{url}"


def resolve_qdrant_url(env: dict | None = None, cli_url: str | None = None):
    env = env or os.environ
    env_url = _norm((env.get("QDRANT_URL") if env else os.getenv("QDRANT_URL")))
    host = (env.get("QDRANT_HOST") if env else os.getenv("QDRANT_HOST"))
    port = (env.get("QDRANT_PORT") if env else os.getenv("QDRANT_PORT"))
    hostport_url = _norm(f"{host}:{port}") if host and port else None

    chosen = None
    source = None
    warnings = []

    if cli_url:
        chosen = _norm(cli_url)
        source = "cli-url"
    elif env_url:
        chosen = env_url
        source = "env-url"
        if hostport_url and hostport_url != env_url:
            warnings.append({
                "event": "config_mismatch",
                "chosen": "QDRANT_URL",
                "qdrant_url": env_url,
                "host_port": f"{host}:{port}",
            })
    elif hostport_url:
        chosen = hostport_url
        source = "env-hostport"
    else:
        chosen = None
        source = "unset"

    return chosen, source, warnings

