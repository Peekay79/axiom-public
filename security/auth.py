from __future__ import annotations

import os
from typing import Any, Tuple


def _truthy(name: str, default: bool = False) -> bool:
    return str(os.getenv(name, str(default))).strip().lower() in {"1", "true", "yes", "y", "on"}


def verify_request(flask_request) -> Tuple[bool, dict[str, Any]]:
    """
    Optional bearer-token guard for Flask endpoints.

    - Disabled by default (`AXIOM_AUTH_ENABLED=false`)
    - When enabled, requires:
        - `Authorization: Bearer <AXIOM_AUTH_TOKEN>`

    Returns:
      (ok, error_json)
    """
    if not _truthy("AXIOM_AUTH_ENABLED", False):
        return True, {}

    expected = (os.getenv("AXIOM_AUTH_TOKEN", "") or "").strip()
    if not expected:
        return False, {"error": "auth_enabled_but_token_missing"}

    try:
        hdr = flask_request.headers.get("Authorization", "") or ""
    except Exception:
        hdr = ""

    prefix = "bearer "
    token = hdr[len(prefix) :].strip() if hdr.lower().startswith(prefix) else ""
    if token != expected:
        return False, {"error": "unauthorized"}

    return True, {}

