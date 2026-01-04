#!/usr/bin/env python3
from __future__ import annotations

import os
from typing import Any, Dict, Tuple


def _truthy(name: str, default: bool = False) -> bool:
    v = str(os.getenv(name, str(default))).strip().lower()
    return v in {"1", "true", "yes", "y", "on"}


def _emit(signal: str, data: Dict[str, Any]) -> None:
    try:
        from pods.cockpit.cockpit_reporter import write_signal  # type: ignore

        write_signal("bluegreen", signal, data)
    except Exception:
        pass


def record_recall_eval(source_alias: str, shadow_alias: str, k: int, delta_recall: float) -> None:
    _emit("recall_eval", {
        "source": source_alias,
        "shadow": shadow_alias,
        "k": int(k),
        "delta_recall": float(delta_recall),
    })


def maybe_cutover(client: Any, alias: str, shadow: str, min_delta: float) -> Tuple[bool, str | None, str | None]:
    """
    If BLUEGREEN_ENABLED and delta >= min_delta, switch alias to shadow via client's update_aliases.
    Returns (switched, prev, new). Fail-closed: on error, returns (False, None, None).
    """
    if not _truthy("BLUEGREEN_ENABLED", True):
        return False, None, None
    try:
        from qdrant_client.http import models as qm  # type: ignore
        # Read current alias target (best-effort)
        prev = None
        try:
            aliases = client.list_aliases()
            d = getattr(aliases, "aliases", None) or getattr(aliases, "result", None) or {}
            if isinstance(d, list):
                for a in d:
                    name = getattr(a, "alias_name", None) or getattr(a, "alias", None) or getattr(a, "name", None)
                    target = getattr(a, "collection_name", None) or getattr(a, "collection", None)
                    if str(name) == alias:
                        prev = str(target)
                        break
        except Exception:
            prev = None
        ops = [qm.CreateAliasOperation(create_alias=qm.CreateAlias(collection_name=shadow, alias_name=alias))]
        client.update_aliases(changes=ops)
        _emit("switch", {"alias": alias, "from": prev, "to": shadow})
        return True, prev, shadow
    except Exception as e:
        _emit("switch_error", {"alias": alias, "shadow": shadow, "error": str(e)})
        return False, None, None


__all__ = ["record_recall_eval", "maybe_cutover"]

