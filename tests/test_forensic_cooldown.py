import os
import time
import logging


def _set_env_defaults(monkeypatch):
    monkeypatch.setenv("AXIOM_CONTRADICTION_RESOLUTION_ENABLED", "true")
    monkeypatch.setenv("AXIOM_CONTRADICTION_SEVERITY_ESCALATE", "0.7")
    monkeypatch.setenv("AXIOM_CONTRADICTION_REPEAT_ESCALATE", "1")
    monkeypatch.setenv("AXIOM_FORENSIC_COOLDOWN_MIN_SEC", "2")
    monkeypatch.setenv("AXIOM_FORENSIC_COOLDOWN_MAX_SEC", "5")
    monkeypatch.setenv("AXIOM_FORENSIC_COOLDOWN_MODE", "linear")
    monkeypatch.setenv("AXIOM_CONTRADICTION_REGISTRY_PATH", "/workspace/data_test")


def _cleanup_state():
    base = os.getenv("AXIOM_CONTRADICTION_REGISTRY_PATH", "/workspace/data_test")
    try:
        reg = os.path.join(base, "contradiction_registry.jsonl")
        if os.path.exists(reg):
            os.remove(reg)
    except Exception:
        pass
    try:
        cd = os.path.join(base, ".forensic_cooldown_state.json")
        if os.path.exists(cd):
            os.remove(cd)
def test_mapping_linear_exponential_tiered(monkeypatch):
    from contradiction_registry import get_cooldown_duration

    # Ensure bounds
    monkeypatch.setenv("AXIOM_FORENSIC_COOLDOWN_MIN_SEC", "10")
    monkeypatch.setenv("AXIOM_FORENSIC_COOLDOWN_MAX_SEC", "100")

    # Linear
    assert get_cooldown_duration(0.0, "linear") == 10
    assert get_cooldown_duration(0.5, "linear") == 10 + int((100 - 10) * 0.5)
    assert get_cooldown_duration(1.0, "linear") == 100

    # Exponential (experimental)
    assert get_cooldown_duration(0.0, "exponential") == 10
    assert get_cooldown_duration(0.5, "exponential") == 10 + int((100 - 10) * (0.5 ** 2))
    assert get_cooldown_duration(1.0, "exponential") == 100

    # Tiered (experimental)
    assert get_cooldown_duration(0.0, "tiered") == 10
    assert get_cooldown_duration(0.3, "tiered") == (10 + 100) // 2
    assert get_cooldown_duration(0.69, "tiered") == (10 + 100) // 2
    assert get_cooldown_duration(0.7, "tiered") == 100


def test_invalid_env_defaults_to_linear(monkeypatch):
    from contradiction_registry import get_cooldown_duration

    monkeypatch.setenv("AXIOM_FORENSIC_COOLDOWN_MIN_SEC", "10")
    monkeypatch.setenv("AXIOM_FORENSIC_COOLDOWN_MAX_SEC", "100")
    # pass invalid mode to function
    assert get_cooldown_duration(0.5, "invalid-mode") == 10 + int((100 - 10) * 0.5)
    except Exception:
        pass
    try:
        os.makedirs(base, exist_ok=True)
    except Exception:
        pass


def test_cooldown_sticks_forensic_mode(monkeypatch, caplog):
    _set_env_defaults(monkeypatch)
    _cleanup_state()

    from contradiction_registry import (
        register_t1_t3_contradiction,
        forensic_cooldown_active,
    )

    # Trigger escalation via severity/repeat (repeat threshold set to 1)
    narrative = {"uuid": "t1-1", "confidence": 0.5}
    raw = {"uuid": "t3-1", "confidence": 0.95}
    with caplog.at_level(logging.INFO):
        register_t1_t3_contradiction(narrative, raw)

    assert forensic_cooldown_active() is True

    # Verify start log emitted
    started_logs = [rec.message for rec in caplog.records if "[RECALL][ForensicCooldown] started" in rec.message]
    assert started_logs, "Expected forensic cooldown start log"

    # Cooldown should still be active before expiry
    assert forensic_cooldown_active() is True


def test_cooldown_expires_allows_narrative(monkeypatch, caplog):
    _set_env_defaults(monkeypatch)
    _cleanup_state()

    from contradiction_registry import (
        register_t1_t3_contradiction,
        forensic_cooldown_active,
    )

    narrative = {"uuid": "t1-2", "confidence": 0.4}
    raw = {"uuid": "t3-2", "confidence": 0.95}
    register_t1_t3_contradiction(narrative, raw)
    assert forensic_cooldown_active() is True

    # Wait until expiry (> configured max 5s)
    time.sleep(6)
    with caplog.at_level(logging.INFO):
        # Calling active check should emit 'expired' when elapsed
        _ = forensic_cooldown_active()
    assert forensic_cooldown_active() is False
    expired_logs = [rec.message for rec in caplog.records if "[RECALL][ForensicCooldown] expired" in rec.message]
    assert expired_logs, "Expected forensic cooldown expired log"


def test_resolution_clears_cooldown(monkeypatch, caplog):
    _set_env_defaults(monkeypatch)
    _cleanup_state()

    from contradiction_registry import (
        register_t1_t3_contradiction,
        forensic_cooldown_active,
        clear_forensic_cooldown,
    )

    narrative = {"uuid": "t1-3", "confidence": 0.4}
    raw = {"uuid": "t3-3", "confidence": 0.99}
    register_t1_t3_contradiction(narrative, raw)
    assert forensic_cooldown_active() is True

    with caplog.at_level(logging.INFO):
        clear_forensic_cooldown()

    assert forensic_cooldown_active() is False
    cleared_logs = [rec.message for rec in caplog.records if "[RECALL][ForensicCooldown] cleared" in rec.message]
    assert cleared_logs, "Expected forensic cooldown cleared log"

