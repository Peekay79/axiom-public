"""Compatibility package for legacy imports (vector)."""

from __future__ import annotations

import sys
from pathlib import Path
from pkgutil import extend_path

__path__ = extend_path(__path__, __name__)  # type: ignore[name-defined]
_ROOT = Path(__file__).resolve().parents[2]
_SERVICES = _ROOT / "services" / "vector"
if _SERVICES.is_dir():
    sp = str(_SERVICES)
    if sp not in __path__:
        __path__.append(sp)  # type: ignore[attr-defined]

_AXIOM_FLAT = _ROOT / "src" / "axiom"
if _AXIOM_FLAT.is_dir():
    ap = str(_AXIOM_FLAT)
    if ap not in sys.path:
        sys.path.insert(0, ap)

