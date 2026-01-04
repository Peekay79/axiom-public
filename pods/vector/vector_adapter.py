"""
Compatibility wrapper for `pods.vector.vector_adapter`.

Implementation lives under `services/vector/vector_adapter.py` in the public tree.
This wrapper keeps historical import paths stable for tests and scripts.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure flattened `src/axiom/*` packages (config, memory, utils, ...) are importable.
_ROOT = Path(__file__).resolve().parents[2]
_AXIOM_FLAT = _ROOT / "src" / "axiom"
if _AXIOM_FLAT.is_dir():
    p = str(_AXIOM_FLAT)
    if p not in sys.path:
        sys.path.insert(0, p)

# Re-export adapter implementation
from services.vector.vector_adapter import *  # type: ignore  # noqa: F401,F403

