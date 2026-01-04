#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
from typing import Any, Dict


def _env(name: str, default: str | None = None) -> str:
    v = os.getenv(name)
    return (v if v is not None else (default or "")).strip()


def _truthy(name: str, default: bool = False) -> bool:
    v = _env(name, str(default))
    return v.lower() in {"1", "true", "yes", "y", "on"}


def current() -> Dict[str, Any]:
    name = _env("EMBEDDER_NAME", "text-embedding-3-large")
    version = _env("EMBEDDER_VERSION", "3.0.0")
    dim = int(_env("EMBEDDER_DIM", "3072") or "3072")
    # Optional normalization flags can be added later; include in hash inputs
    flags = {"normalize": True}
    h = hashlib.sha256()
    h.update(name.encode("utf-8"))
    h.update(version.encode("utf-8"))
    h.update(str(dim).encode("utf-8"))
    h.update(json.dumps(flags, sort_keys=True).encode("utf-8"))
    return {"name": name, "version": version, "dim": dim, "hash": h.hexdigest(), "flags": flags}


def with_registry(payload: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(payload or {})
    out.setdefault("embedder", {})
    out["embedder"].update(current())
    return out


__all__ = ["current", "with_registry"]

