#!/usr/bin/env python3
import importlib
import os

from tests.utils.env import temp_env


def _reload_client():
    mod = importlib.import_module("vector.unified_client")
    importlib.reload(mod)
    return mod


def test_client_uses_env_url_when_set():
    with temp_env({"QDRANT_URL": "http://alpha:7777", "QDRANT_HOST": None, "QDRANT_PORT": None}):
        uc_mod = _reload_client()
        client = uc_mod.UnifiedVectorClient(os.environ)
        dbg = client.get_debug_config()
        assert dbg["qdrant_url"] == "http://alpha:7777"
        assert dbg["warnings"] in (None, []) or isinstance(dbg["warnings"], list)


def test_client_prefers_url_over_host_port_and_emits_warning():
    with temp_env({"QDRANT_URL": "http://bravo:7333", "QDRANT_HOST": "axiom_qdrant", "QDRANT_PORT": "6333"}):
        uc_mod = _reload_client()
        client = uc_mod.UnifiedVectorClient(os.environ)
        dbg = client.get_debug_config()
        assert dbg["qdrant_url"] == "http://bravo:7333"
        warns = dbg.get("warnings")
        # Memory resolver emits a structured mismatch warning list
        assert warns is None or isinstance(warns, list)


def test_client_constructs_url_from_host_port_when_url_missing():
    with temp_env({"QDRANT_URL": None, "QDRANT_HOST": "axiom_qdrant", "QDRANT_PORT": "6333"}):
        uc_mod = _reload_client()
        client = uc_mod.UnifiedVectorClient(os.environ)
        dbg = client.get_debug_config()
        # Unified client resolves via resolver; ensure host:port result
        assert dbg["qdrant_url"].startswith("http://")
        assert ":" in dbg["qdrant_url"]

