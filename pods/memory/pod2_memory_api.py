"""
Compatibility wrapper for `pods.memory.pod2_memory_api`.

The implementation lives at `services/memory/pod2_memory_api.py` in the
public-safe tree. This module keeps the historical import path stable for:
  - README quickstart commands
  - docker-compose commands
  - unit tests
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure flattened `src/axiom/*` packages (config, memory, utils, ...) are importable.
_ROOT = Path(__file__).resolve().parents[2]
_AXIOM_FLAT = _ROOT / "src" / "axiom"
if _AXIOM_FLAT.is_dir():
    p = str(_AXIOM_FLAT)
    if p not in sys.path:
        sys.path.insert(0, p)

# Re-export implementation symbols (tests import `app`, some helpers).
from services.memory.pod2_memory_api import *  # type: ignore  # noqa: F401,F403
from services.memory.pod2_memory_api import app  # type: ignore  # noqa: F401,E402


def main() -> None:
    # Allow port override for local runs (defaults to Flask 5000).
    port = int(os.getenv("MEMORY_API_PORT", os.getenv("PORT", "5000")) or 5000)
    print("ROUTES ON START:", [r.rule for r in app.url_map.iter_rules()])
    app.run(host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()

