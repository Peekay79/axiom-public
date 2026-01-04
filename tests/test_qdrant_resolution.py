#!/usr/bin/env python3
import os
import importlib
import json
from contextlib import contextmanager


@contextmanager
def _env(**kwargs):
    old = {k: os.environ.get(k) for k in kwargs}
    try:
        for k, v in kwargs.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = str(v)
        yield
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _reload_resolver():
    mod = importlib.import_module("config.resolved_mode")
    importlib.reload(mod)
    return mod


def test_resolver_only_qdrant_url():
    with _env(QDRANT_URL="http://example.com:6333", QDRANT_HOST=None, QDRANT_PORT=None):
        rm = _reload_resolver()
        url, source, warns = rm.resolve_qdrant_url()
        assert url == "http://example.com:6333"
        assert source == "env-url"
        assert warns == []


def test_resolver_only_host_port():
    with _env(QDRANT_URL=None, QDRANT_HOST="axiom_qdrant", QDRANT_PORT="6333"):
        rm = _reload_resolver()
        url, source, warns = rm.resolve_qdrant_url()
        assert url == "http://axiom_qdrant:6333"
        assert source == "env-hostport"
        assert warns == []


def test_resolver_conflict_env_vars():
    with _env(QDRANT_URL="http://example.com:6333", QDRANT_HOST="axiom_qdrant", QDRANT_PORT="6333"):
        rm = _reload_resolver()
        url, source, warns = rm.resolve_qdrant_url()
        assert url == "http://example.com:6333"
        assert source == "env-url"
        assert isinstance(warns, list) and len(warns) == 1
        w = warns[0]
        assert w.get("event") == "config_mismatch"
        assert w.get("chosen") == "QDRANT_URL"


def test_resolver_cli_overrides_env():
    with _env(QDRANT_URL="http://env-host:6333", QDRANT_HOST="h", QDRANT_PORT="6333"):
        rm = _reload_resolver()
        url, source, warns = rm.resolve_qdrant_url(cli_url="http://cli-host:7777")
        assert url == "http://cli-host:7777"
        assert source == "cli-url"
        # No warning on CLI override itself
        assert warns == []


def test_health_exposes_resolved_url_and_warnings(monkeypatch):
    # Simulate Flask test client
    with _env(QDRANT_URL="http://example.com:6333", QDRANT_HOST="axiom_qdrant", QDRANT_PORT="6333"):
        # Force Qdrant mode off to avoid network calls in health
        os.environ["USE_QDRANT_BACKEND"] = "0"
        os.environ["AXIOM_AUTH_ENABLED"] = "0"
        # Import app
        from pods.memory import pod2_memory_api as mod
        importlib.reload(mod)
        app = mod.app
        client = app.test_client()

        res = client.get("/health")
        assert res.status_code == 200
        data = res.get_json()
        # Field present and matches resolver
        assert data.get("resolved_qdrant_url") == "http://example.com:6333"
        warnings = data.get("config_warnings")
        assert warnings is None or isinstance(warnings, list)
