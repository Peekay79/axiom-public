"""
Import bootstrap for the public-safe Axiom tree.

This repo historically imported internal packages as top-level modules, e.g.:
  - import config
  - import memory
  - import retrieval
even though the public tree stores them under `src/axiom/`.

Python automatically imports `sitecustomize` (if present on sys.path) during
startup, so placing this file at repo root makes local runs and tests work
without requiring users to manually set PYTHONPATH.
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
_AXIOM_FLAT = _ROOT / "src" / "axiom"

# Make `src/axiom/*` importable as top-level packages (config, memory, utils, ...)
if _AXIOM_FLAT.is_dir():
    p = str(_AXIOM_FLAT)
    if p not in sys.path:
        sys.path.insert(0, p)

