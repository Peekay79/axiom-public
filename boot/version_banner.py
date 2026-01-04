from __future__ import annotations

import os
import platform
import sys
from datetime import datetime


def collect_banner() -> dict:
    """
    Collect a small, safe "version banner" for cockpit visibility.

    Intentionally avoids:
    - hostnames/IPs
    - env var dumps
    - any secrets
    """
    return {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "git_sha": (os.getenv("GIT_SHA") or "").strip() or None,
    }

