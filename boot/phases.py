from __future__ import annotations

import os
import time
from typing import Callable, Dict


def _env_int(name: str, default: int) -> int:
    try:
        return int(str(os.getenv(name, str(default))).strip())
    except Exception:
        return int(default)


def _env_bool(name: str, default: bool = False) -> bool:
    return str(os.getenv(name, str(default))).strip().lower() in {"1", "true", "yes", "y", "on"}


def run_boot(
    pod_name: str,
    phases: Dict[str, Callable[[], bool]],
    deps: Callable[[], Dict[str, bool]],
) -> dict:
    """
    Lightweight boot orchestrator used by tests and local demos.

    Behavior (env-controlled):
    - BOOT_TOTAL_TIMEOUT_SEC: total time to wait for deps+phases (default 120)
    - BOOT_PHASE_TIMEOUT_SEC: per-phase time budget (default 60)
    - BOOT_RETRY_BACKOFF_SEC: sleep between retries (default 2)
    - BOOT_REQUIRE: comma-separated deps that must be true for "normal"
    - BOOT_DEGRADED_MIN_REQUIRE: comma-separated deps required for "degraded" mode
    - BOOT_ALLOW_DEGRADED_ON_TIMEOUT: if true, allow "degraded" when min deps pass
    """
    from pods.cockpit.cockpit_reporter import write_signal  # local import (keeps import graph light)
    from pods.cockpit.cockpit_reporter import report_degraded

    total_timeout = max(1, _env_int("BOOT_TOTAL_TIMEOUT_SEC", 120))
    phase_timeout = max(1, _env_int("BOOT_PHASE_TIMEOUT_SEC", 60))
    backoff = max(0, _env_int("BOOT_RETRY_BACKOFF_SEC", 2))

    require = [x.strip() for x in (os.getenv("BOOT_REQUIRE", "") or "").split(",") if x.strip()]
    degraded_min = [
        x.strip()
        for x in (os.getenv("BOOT_DEGRADED_MIN_REQUIRE", "") or "").split(",")
        if x.strip()
    ]
    allow_degraded = _env_bool("BOOT_ALLOW_DEGRADED_ON_TIMEOUT", False)

    start = time.monotonic()
    last_deps: Dict[str, bool] = {}

    def _deps_ok(names: list[str]) -> bool:
        if not names:
            return True
        for n in names:
            if not bool(last_deps.get(n, False)):
                return False
        return True

    # Wait for deps to satisfy "normal" requirements (or timeout)
    while True:
        last_deps = deps() or {}
        if _deps_ok(require):
            break
        if (time.monotonic() - start) >= total_timeout:
            break
        if backoff:
            time.sleep(backoff)

    # Run phases (best-effort, time-bounded per phase)
    phases_ok = True
    for phase_name, phase_fn in (phases or {}).items():
        p_start = time.monotonic()
        ok = False
        while True:
            try:
                ok = bool(phase_fn())
            except Exception:
                ok = False
            if ok:
                break
            if (time.monotonic() - p_start) >= phase_timeout:
                break
            if backoff:
                time.sleep(backoff)
        if not ok:
            phases_ok = False
            break

    # Decide mode
    if _deps_ok(require) and phases_ok:
        mode = "normal"
        ready = True
    else:
        # Try degraded if allowed and min deps are present
        last_deps = deps() or last_deps
        if allow_degraded and _deps_ok(degraded_min):
            mode = "degraded"
            ready = True
            report_degraded(True, depth=1)
        else:
            mode = "safe"
            ready = False
            report_degraded(False, depth=None)

    # Emit cockpit signals (schema used in tests)
    payload = {"mode": mode, "ready": ready, "deps": last_deps}
    if ready:
        write_signal(pod_name, "boot_complete", payload)
    else:
        write_signal(pod_name, "boot_incomplete", payload)

    return {"pod": pod_name, "ready": ready, "mode": mode, "deps": last_deps}

