"""Compatibility package for legacy imports (cockpit)."""

from __future__ import annotations

from pathlib import Path
from pkgutil import extend_path

__path__ = extend_path(__path__, __name__)  # type: ignore[name-defined]
_ROOT = Path(__file__).resolve().parents[2]
_SERVICES = _ROOT / "services" / "cockpit"
if _SERVICES.is_dir():
    sp = str(_SERVICES)
    if sp not in __path__:
        __path__.append(sp)  # type: ignore[attr-defined]

