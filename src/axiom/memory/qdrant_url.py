import os
from typing import Optional, Tuple

_DEF_HOST = "axiom_qdrant"
_DEF_PORT = 6333


def _normalize_host(host: str) -> str:
    if host in ("localhost", "127.0.0.1", "::1"):
        # In a container, "localhost" is itself — use the service name instead
        return os.getenv("QDRANT_SERVICE_NAME", _DEF_HOST)
    return host


def resolve_qdrant(
    cli_host: Optional[str] = None, cli_port: Optional[int | str] = None
) -> Tuple[str, int]:
    """
    Single source of truth for Qdrant host/port.
    Precedence: CLI args > env > safe defaults.
    Also normalizes localhost -> axiom_qdrant for in-container calls.
    """
    host = cli_host or os.getenv("QDRANT_HOST") or _DEF_HOST
    port_raw = cli_port or os.getenv("QDRANT_PORT") or str(_DEF_PORT)
    try:
        port = int(port_raw)
    except Exception:
        port = _DEF_PORT
    return _normalize_host(str(host)), port
