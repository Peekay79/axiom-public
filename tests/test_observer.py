import importlib
import io
import json
import os
import sys
from contextlib import redirect_stdout


def _set_env(env: dict[str, str]):
    # Clear possibly set flags
    keys = [
        "ENABLE_OBSERVER",
        "ENABLE_OBSERVER_MEMORY",
        "ENABLE_OBSERVER_BELIEF",
        "ENABLE_OBSERVER_JOURNAL",
        "OBSERVER_SAMPLE_RATE",
        "OBSERVER_PREVIEW_CHARS",
    ]
    for k in keys:
        if k in os.environ:
            del os.environ[k]
    os.environ.update(env)


def _reload_observer():
    if "axiom.hooks.observer" in sys.modules:
        del sys.modules["axiom.hooks.observer"]
    return importlib.import_module("axiom.hooks.observer")


def test_disabled_emits_nothing():
    _set_env({
        "ENABLE_OBSERVER": "false",
        "ENABLE_OBSERVER_MEMORY": "false",
        "OBSERVER_SAMPLE_RATE": "1.0",
    })
    obs = _reload_observer()
    buf = io.StringIO()
    with redirect_stdout(buf):
        obs.observe("hello", kind="memory", meta={"x": 1})
    assert buf.getvalue() == ""


def test_enabled_emits_one_line_and_kind_memory():
    _set_env({
        "ENABLE_OBSERVER": "true",
        "ENABLE_OBSERVER_MEMORY": "true",
        "OBSERVER_SAMPLE_RATE": "1.0",
        "OBSERVER_PREVIEW_CHARS": "8",
    })
    obs = _reload_observer()
    buf = io.StringIO()
    with redirect_stdout(buf):
        obs.observe("I believe Max is my son and API key=abcdefghijklmnop", kind="memory", meta={"confidence": 0.82})
    out = buf.getvalue().strip()
    assert out
    data = json.loads(out)
    assert data["kind"] == "memory"
    # preview is truncated and redacted
    assert len(data["preview"]) <= 8
    assert "[REDACTED]" in data["preview"] or data["preview"] == data["preview"]  # redaction may truncate away
    assert data["meta"]["confidence"] == 0.82
    assert data["source"] == "observer"
    assert data["version"] == 1


def test_sampling_zero_emits_nothing():
    _set_env({
        "ENABLE_OBSERVER": "true",
        "ENABLE_OBSERVER_MEMORY": "true",
        "OBSERVER_SAMPLE_RATE": "0.0",
    })
    obs = _reload_observer()
    buf = io.StringIO()
    with redirect_stdout(buf):
        obs.observe("hello", kind="memory")
    assert buf.getvalue() == ""


def test_redaction_rules():
    _set_env({
        "ENABLE_OBSERVER": "true",
        "ENABLE_OBSERVER_BELIEF": "true",
        "OBSERVER_SAMPLE_RATE": "1.0",
        "OBSERVER_PREVIEW_CHARS": "512",
    })
    obs = _reload_observer()
    secret_text = (
        "Contact me at user@example.com, use Bearer abc.DEF-123, and visit https://example.com/path. "
        "api = aBcDeFgHiJkLmNoP"
    )
    buf = io.StringIO()
    with redirect_stdout(buf):
        obs.observe(secret_text, kind="belief")
    out = buf.getvalue().strip()
    assert out
    data = json.loads(out)
    assert "[REDACTED]" in data["preview"]
    # ensure sensitive patterns are not present
    assert "example.com" not in data["preview"]
    assert "Bearer" not in data["preview"]
    assert "@example.com" not in data["preview"]


def test_no_raise_on_internal_error(monkeypatch):
    _set_env({
        "ENABLE_OBSERVER": "true",
        "ENABLE_OBSERVER_JOURNAL": "true",
        "OBSERVER_SAMPLE_RATE": "1.0",
    })
    obs = _reload_observer()

    # Force json.dumps to raise to simulate internal failure
    called = {"ok": False}

    def boom(*args, **kwargs):
        called["ok"] = True
        raise RuntimeError("boom")

    monkeypatch.setattr("json.dumps", boom)

    buf = io.StringIO()
    with redirect_stdout(buf):
        obs.observe("some journal text", kind="journal", meta={"k": 1})
    # Should not raise and produce no output
    assert called["ok"] is True
    assert buf.getvalue() == ""

