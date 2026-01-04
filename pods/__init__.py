"""
Compatibility shim.

The original repository used the `pods.*` namespace. The public layout places service
implementations under `services.*`, but many modules/tests still import `pods.*`.

This shim aliases `pods.memory`, `pods.vector`, and `pods.cockpit` to the matching
`services.*` packages to keep imports stable without duplicating source files.
"""

from __future__ import annotations

import importlib
import sys

_ALIASES = ("memory", "vector", "cockpit")

for _name in _ALIASES:
    try:
        sys.modules[f"pods.{_name}"] = importlib.import_module(f"services.{_name}")
    except Exception:
        # If a service package is missing, leave it unaliased.
        pass

