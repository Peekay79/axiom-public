from __future__ import annotations

import os
from urllib.parse import urlparse, urlunparse


def _env_bool(name: str, default: bool = False) -> bool:
    try:
        return str(os.getenv(name, "true" if default else "false")).strip().lower() in {
            "1",
            "true",
            "yes",
            "y",
            "on",
        }
    except Exception:
        return bool(default)


def ensure_scheme(url_or_host: str, default_scheme: str = "http") -> str:
    """
    If value has no scheme, prepend default scheme.
    """
    s = (url_or_host or "").strip()
    if not s:
        return ""
    # If it already looks like a URL scheme, leave it.
    if "://" in s:
        return s
    return f"{default_scheme}://{s}"


def strip_trailing_slashes(url: str) -> str:
    return (url or "").strip().rstrip("/")


def mask_url_userinfo(url: str) -> str:
    """
    Hide userinfo if present: https://user:pass@host -> https://***@host
    """
    s = (url or "").strip()
    if not s:
        return s
    try:
        u = urlparse(s)
        if u.username is None and u.password is None:
            return s
        # Rebuild netloc without exposing user/pass.
        host = u.hostname or ""
        netloc = "***@" + host
        if u.port is not None:
            netloc += f":{u.port}"
        return urlunparse((u.scheme, netloc, u.path, u.params, u.query, u.fragment))
    except Exception:
        return s


def join_host_port(
    host_or_url: str,
    port: int | str | None,
    *,
    default_scheme: str = "http",
    keep_existing_port: bool = True,
) -> str:
    """
    Safely join host + port with ':' while preserving an existing port when present.

    Examples:
      - ("example.com", 8002) -> "http://example.com:8002"
      - ("http://example.com", 8002) -> "http://example.com:8002"
      - ("http://example.com:8002", 8002) -> "http://example.com:8002" (unchanged)
    """
    h = (host_or_url or "").strip()
    if not h:
        return ""
    p = None
    if port is not None and str(port).strip():
        try:
            p = int(str(port).strip())
        except Exception:
            p = None

    u = urlparse(ensure_scheme(h, default_scheme=default_scheme))
    scheme = u.scheme or default_scheme

    # If there is already a port and we want to keep it, do not override.
    if keep_existing_port and u.port is not None:
        netloc = u.hostname or ""
        if u.port is not None:
            netloc += f":{u.port}"
        return urlunparse((scheme, netloc, u.path, u.params, u.query, u.fragment)).rstrip("/")

    # No existing port: append if provided.
    host = u.hostname or ""
    if not host:
        return ""
    netloc = host
    if p is not None:
        netloc += f":{p}"
    return urlunparse((scheme, netloc, u.path, u.params, u.query, u.fragment)).rstrip("/")


def normalize_base_url(url_or_host: str, *, default_scheme: str = "http") -> str:
    """
    Normalize a base URL for service endpoints:
    - ensure scheme (default http)
    - strip trailing slashes
    - preserve path/query if present
    """
    s = (url_or_host or "").strip()
    if not s:
        return ""
    s = ensure_scheme(s, default_scheme=default_scheme)
    # urlparse will normalize structure; we keep whatever path/query is present.
    try:
        u = urlparse(s)
        if not u.scheme or not u.netloc:
            return strip_trailing_slashes(s)
        return urlunparse((u.scheme, u.netloc, u.path, u.params, u.query, u.fragment)).rstrip("/")
    except Exception:
        return strip_trailing_slashes(s)


def debug_assert_url_normalization() -> None:
    """
    Unit-test-like assertions gated by AXIOM_DEBUG_URLS=true.
    """
    if not _env_bool("AXIOM_DEBUG_URLS", False):
        return

    a = join_host_port("http://127.0.0.1", 8002)
    assert a == "http://127.0.0.1:8002", a
    b = join_host_port("http://127.0.0.1:8002", 8002)
    assert b == "http://127.0.0.1:8002", b
    # Guard against malformed concatenations like "2508002"
    assert "2508002" not in a and "2508002" not in b

