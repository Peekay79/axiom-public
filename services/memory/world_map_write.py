"""
World map write helpers (stdlib-only, deterministic).

This module is intentionally side-effect free so it can be unit tested without
importing the full Memory API server (which has substantial boot logic).

Ops format (restricted, not full JSONPatch):
  - op: "add" | "replace"
  - path: "/field_name" (top-level only)
  - value: JSON-serialisable scalar/list/dict

List semantics (for allowed list paths only):
  - replace: sets the entire list
  - add + scalar/dict: append (with bounded length) / upsert for certain lists
"""

from __future__ import annotations

import json
import os
import shutil
import time
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    error: str = ""
    detail: Optional[dict] = None


def _is_jsonable(value: Any) -> bool:
    try:
        json.dumps(value, ensure_ascii=False)
        return True
    except Exception:
        return False


def _now_ts() -> str:
    # Stable-ish timestamp used in filenames/logs (seconds precision).
    return time.strftime("%Y%m%d_%H%M%S", time.gmtime())


def _top_level_key(path: str) -> Optional[str]:
    p = str(path or "")
    if not p.startswith("/"):
        return None
    # Restrict to top-level only: "/foo" (no nested segments).
    segs = [s for s in p.split("/") if s != ""]
    if len(segs) != 1:
        return None
    key = segs[0].strip()
    if not key:
        return None
    # Conservative key charset
    for ch in key:
        if not (ch.isalnum() or ch == "_"):
            return None
    return key


def get_entity_from_world_map(obj: dict, entity_id: str) -> Optional[dict]:
    """Return a COPY of entity dict (never returns a live reference)."""
    if not isinstance(obj, dict):
        return None
    ents = obj.get("entities")
    eid = str(entity_id or "")
    if not eid:
        return None
    if isinstance(ents, list):
        for ent in ents:
            if isinstance(ent, dict) and str(ent.get("id")) == eid:
                return dict(ent)
        return None
    if isinstance(ents, dict):
        v = ents.get(eid)
        if isinstance(v, dict):
            out = dict(v)
            out.setdefault("id", eid)
            return out
    return None


def _allowed_paths_for_entity(entity_id: str) -> Dict[str, str]:
    """Return mapping path->type_tag for validation."""
    # General conservative allowlist (any entity): safe metadata only.
    base: Dict[str, str] = {
        "/display_name": "str",
        "/name": "str",
        "/alias": "str",
        "/notes": "str",
        "/tags": "list_str",
    }

    eid = str(entity_id or "").strip().lower()
    if eid != "example_person":
        return base

    # ExamplePerson hard facts allowlist (plus base).
    example_person = {
        "/wife_name": "str",
        "/birth_date": "str",
        "/birth_place": "str",
        "/location": "str",
        "/nationality": "str",
        "/job_title": "str",
        "/works_at": "str",
        "/worked_at": "list_str_or_add_str",
        "/career_history": "list_dict_or_add_dict",
        "/family": "list_str_or_add_str",
        "/kids": "list_kids_or_add_kid",
    }
    out = dict(base)
    out.update(example_person)
    return out


def validate_ops(
    *,
    world_map_obj: dict,
    entity_id: str,
    ops: Any,
    confidence: Any,
    evidence: Any,
    require_entity_exists: bool = True,
    for_auto_apply_kurt: bool = False,
    max_string_len: int = 200,
    max_list_len: int = 20,
) -> ValidationResult:
    """Validate proposal payload shape + deterministic safety rules."""
    eid = str(entity_id or "").strip()
    if not eid:
        return ValidationResult(False, "missing_entity_id")

    if require_entity_exists:
        if get_entity_from_world_map(world_map_obj or {}, eid) is None:
            return ValidationResult(False, "entity_not_found", {"entity_id": eid})

    try:
        conf = float(confidence)
    except Exception:
        return ValidationResult(False, "invalid_confidence")
    if not (0.0 <= conf <= 1.0):
        return ValidationResult(False, "invalid_confidence_range", {"confidence": confidence})

    if not isinstance(ops, list) or not ops:
        return ValidationResult(False, "invalid_ops")

    allow = _allowed_paths_for_entity(eid)

    # When gating auto-apply, require example_person hard facts only.
    if for_auto_apply_kurt:
        if eid.lower() != "example_person":
            return ValidationResult(False, "auto_apply_entity_not_allowed")
        # Hard facts: only these paths qualify.
        hard_fact_paths = {
            "/wife_name",
            "/birth_date",
            "/birth_place",
            "/location",
            "/nationality",
            "/job_title",
            "/works_at",
            "/worked_at",
            "/career_history",
            "/family",
            "/kids",
        }
        if any(str((op or {}).get("path")) not in hard_fact_paths for op in ops if isinstance(op, dict)):
            return ValidationResult(False, "auto_apply_path_not_allowed")

    for i, op in enumerate(list(ops)):
        if not isinstance(op, dict):
            return ValidationResult(False, "op_not_object", {"index": i})
        kind = str(op.get("op") or "").strip().lower()
        if kind not in {"add", "replace"}:
            return ValidationResult(False, "op_not_allowed", {"index": i, "op": kind})
        path = str(op.get("path") or "").strip()
        if path not in allow:
            return ValidationResult(False, "path_not_allowed", {"index": i, "path": path})
        key = _top_level_key(path)
        if key is None:
            return ValidationResult(False, "path_invalid", {"index": i, "path": path})
        value = op.get("value", None)
        if not _is_jsonable(value):
            return ValidationResult(False, "value_not_jsonable", {"index": i, "path": path})

        tag = allow[path]
        if tag in {"str"}:
            if not isinstance(value, str) or not value.strip():
                return ValidationResult(False, "value_type_invalid", {"index": i, "path": path, "want": "str"})
            if len(value) > max_string_len:
                return ValidationResult(False, "value_too_long", {"index": i, "path": path, "max": max_string_len})

        elif tag in {"list_str"}:
            if not isinstance(value, list) or any(not isinstance(x, str) for x in value):
                return ValidationResult(False, "value_type_invalid", {"index": i, "path": path, "want": "list[str]"})
            if len(value) > max_list_len:
                return ValidationResult(False, "list_too_long", {"index": i, "path": path, "max": max_list_len})
            if any(len(x) > max_string_len for x in value):
                return ValidationResult(False, "value_too_long", {"index": i, "path": path, "max": max_string_len})

        elif tag in {"list_str_or_add_str"}:
            if kind == "replace":
                if not isinstance(value, list) or any(not isinstance(x, str) for x in value):
                    return ValidationResult(False, "value_type_invalid", {"index": i, "path": path, "want": "list[str]"})
                if len(value) > max_list_len:
                    return ValidationResult(False, "list_too_long", {"index": i, "path": path, "max": max_list_len})
                if any(len(x) > max_string_len for x in value):
                    return ValidationResult(False, "value_too_long", {"index": i, "path": path, "max": max_string_len})
            else:
                if not isinstance(value, str) or not value.strip():
                    return ValidationResult(False, "value_type_invalid", {"index": i, "path": path, "want": "str"})
                if len(value) > max_string_len:
                    return ValidationResult(False, "value_too_long", {"index": i, "path": path, "max": max_string_len})

        elif tag in {"list_dict_or_add_dict"}:
            if kind == "replace":
                if not isinstance(value, list) or any(not isinstance(x, dict) for x in value):
                    return ValidationResult(False, "value_type_invalid", {"index": i, "path": path, "want": "list[dict]"})
                if len(value) > max_list_len:
                    return ValidationResult(False, "list_too_long", {"index": i, "path": path, "max": max_list_len})
                # Bound each entry size (prevents huge structures)
                for ent in value:
                    try:
                        if len(json.dumps(ent, ensure_ascii=False)) > 2000:
                            return ValidationResult(False, "value_too_long", {"index": i, "path": path, "max": 2000})
                    except Exception:
                        return ValidationResult(False, "value_not_jsonable", {"index": i, "path": path})
            else:
                if not isinstance(value, dict) or not value:
                    return ValidationResult(False, "value_type_invalid", {"index": i, "path": path, "want": "dict"})
                try:
                    if len(json.dumps(value, ensure_ascii=False)) > 2000:
                        return ValidationResult(False, "value_too_long", {"index": i, "path": path, "max": 2000})
                except Exception:
                    return ValidationResult(False, "value_not_jsonable", {"index": i, "path": path})

        elif tag in {"list_kids_or_add_kid"}:
            if kind == "replace":
                if not isinstance(value, list) or any(not isinstance(x, dict) for x in value):
                    return ValidationResult(False, "value_type_invalid", {"index": i, "path": path, "want": "list[kid]"})
                if len(value) > max_list_len:
                    return ValidationResult(False, "list_too_long", {"index": i, "path": path, "max": max_list_len})
                for kid in value:
                    if not isinstance(kid.get("name"), str) or not kid.get("name", "").strip():
                        return ValidationResult(False, "kid_invalid", {"index": i, "path": path})
                    if "age" in kid and not isinstance(kid.get("age"), int):
                        return ValidationResult(False, "kid_invalid", {"index": i, "path": path})
                    if isinstance(kid.get("name"), str) and len(kid.get("name")) > 80:
                        return ValidationResult(False, "value_too_long", {"index": i, "path": path, "max": 80})
            else:
                if not isinstance(value, dict):
                    return ValidationResult(False, "value_type_invalid", {"index": i, "path": path, "want": "kid"})
                if not isinstance(value.get("name"), str) or not value.get("name", "").strip():
                    return ValidationResult(False, "kid_invalid", {"index": i, "path": path})
                if "age" in value and not isinstance(value.get("age"), int):
                    return ValidationResult(False, "kid_invalid", {"index": i, "path": path})
                if isinstance(value.get("name"), str) and len(value.get("name")) > 80:
                    return ValidationResult(False, "value_too_long", {"index": i, "path": path, "max": 80})

        else:
            return ValidationResult(False, "internal_unknown_path_tag", {"index": i, "path": path})

    # Evidence is only strictly required for auto-apply gating (enforced elsewhere).
    if evidence is not None and not isinstance(evidence, dict):
        return ValidationResult(False, "invalid_evidence")

    return ValidationResult(True)


def _upsert_kid(kids: List[dict], kid: dict) -> List[dict]:
    name = str(kid.get("name") or "").strip()
    if not name:
        return kids
    out: List[dict] = []
    replaced = False
    for k in kids:
        if isinstance(k, dict) and str(k.get("name") or "").strip() == name:
            merged = dict(k)
            merged.update({kk: vv for kk, vv in kid.items() if vv is not None})
            out.append(merged)
            replaced = True
        else:
            out.append(k if isinstance(k, dict) else {"value": k})
    if not replaced:
        out.append(dict(kid))
    return out


def apply_ops_in_memory(
    *,
    world_map_obj: dict,
    entity_id: str,
    ops: List[dict],
    max_list_len: int = 20,
) -> Tuple[dict, List[str]]:
    """Apply ops to a world_map object and return (new_obj, changed_fields)."""
    obj = dict(world_map_obj or {})
    ents = obj.get("entities")
    eid = str(entity_id or "")
    if not eid:
        raise ValueError("missing_entity_id")

    # Find live entity reference in this copied object.
    ent_ref: Optional[dict] = None
    if isinstance(ents, list):
        for idx, ent in enumerate(list(ents)):
            if isinstance(ent, dict) and str(ent.get("id")) == eid:
                ent_ref = ent
                break
    elif isinstance(ents, dict):
        v = ents.get(eid)
        if isinstance(v, dict):
            ent_ref = v
            ent_ref.setdefault("id", eid)
    if ent_ref is None:
        raise KeyError("entity_not_found")

    changed: List[str] = []

    for op in ops:
        kind = str(op.get("op") or "").strip().lower()
        path = str(op.get("path") or "").strip()
        key = _top_level_key(path)
        if key is None:
            raise ValueError(f"invalid_path:{path}")
        value = op.get("value")

        if kind == "replace":
            ent_ref[key] = value
            changed.append(key)
            continue

        if kind != "add":
            raise ValueError(f"invalid_op:{kind}")

        # add semantics: list append / upsert for special list fields; else set-if-missing.
        if key in {"worked_at", "family"}:
            cur = ent_ref.get(key)
            if not isinstance(cur, list):
                cur = []
            if isinstance(value, list):
                for v in value:
                    cur.append(v)
            else:
                cur.append(value)
            ent_ref[key] = list(cur)[:max_list_len]
            changed.append(key)
            continue

        if key == "kids":
            cur = ent_ref.get("kids")
            if not isinstance(cur, list):
                cur = []
            if isinstance(value, list):
                out = list(cur)
                for v in value:
                    if isinstance(v, dict):
                        out = _upsert_kid(out, v)
                ent_ref["kids"] = out[:max_list_len]
            elif isinstance(value, dict):
                ent_ref["kids"] = _upsert_kid(list(cur), value)[:max_list_len]
            else:
                # ignore invalid; validator should prevent
                ent_ref["kids"] = list(cur)[:max_list_len]
            changed.append(key)
            continue

        if key == "career_history":
            cur = ent_ref.get("career_history")
            if not isinstance(cur, list):
                cur = []
            if isinstance(value, list):
                for v in value:
                    cur.append(v)
            else:
                cur.append(value)
            ent_ref["career_history"] = list(cur)[:max_list_len]
            changed.append(key)
            continue

        if key == "worked_at":
            cur = ent_ref.get("worked_at")
            if not isinstance(cur, list):
                cur = []
            if isinstance(value, list):
                for v in value:
                    cur.append(v)
            else:
                cur.append(value)
            ent_ref["worked_at"] = list(cur)[:max_list_len]
            changed.append(key)
            continue

        # Default add: set if missing/empty.
        if key not in ent_ref or ent_ref.get(key) in (None, "", [], {}):
            ent_ref[key] = value
            changed.append(key)

    return obj, sorted(set(changed))


def atomic_write_world_map(
    *,
    world_map_path: str,
    new_obj: dict,
    backup_ts: Optional[str] = None,
) -> Tuple[str, str]:
    """Write `new_obj` to `world_map_path` atomically; return (tmp_path, backup_path)."""
    path = str(world_map_path or "")
    if not path:
        raise ValueError("missing_world_map_path")

    ts = backup_ts or _now_ts()
    tmp_path = f"{path}.tmp"
    backup_path = f"{path}.bak.{ts}"

    parent = os.path.dirname(path) or "."
    os.makedirs(parent, exist_ok=True)

    # Backup existing file if present.
    if os.path.exists(path):
        shutil.copy2(path, backup_path)

    with open(tmp_path, "w", encoding="utf-8") as fh:
        json.dump(new_obj, fh, ensure_ascii=False, indent=2, sort_keys=True)
        fh.write("\n")

    # Atomic replace on POSIX
    os.replace(tmp_path, path)
    return tmp_path, backup_path


def evidence_has_direct_spans(evidence: Any) -> bool:
    """Return True iff evidence proves direct user lift (substring constraint)."""
    if not isinstance(evidence, dict):
        return False
    if str(evidence.get("source") or "").strip().lower() != "user":
        return False
    raw_text = evidence.get("raw_text")
    if not isinstance(raw_text, str) or not raw_text:
        return False
    spans: List[str] = []
    if isinstance(evidence.get("extracted_span"), str) and evidence.get("extracted_span"):
        spans = [evidence.get("extracted_span")]
    elif isinstance(evidence.get("extracted_spans"), list):
        spans = [s for s in evidence.get("extracted_spans") if isinstance(s, str) and s]
    if not spans:
        return False
    return all((s in raw_text) for s in spans)


def should_auto_apply_kurt(
    *,
    write_enabled: bool,
    auto_apply_enabled: bool,
    entity_id: str,
    confidence: float,
    min_confidence: float,
    ops: List[dict],
    evidence: Any,
) -> bool:
    if not write_enabled or not auto_apply_enabled:
        return False
    if str(entity_id or "").strip().lower() != "example_person":
        return False
    try:
        if float(confidence) < float(min_confidence):
            return False
    except Exception:
        return False
    # All op paths must be example_person hard facts allowlist.
    hard_fact_paths = {
        "/wife_name",
        "/birth_date",
        "/birth_place",
        "/location",
        "/nationality",
        "/job_title",
        "/works_at",
        "/worked_at",
        "/career_history",
        "/family",
        "/kids",
    }
    for op in list(ops or []):
        if not isinstance(op, dict):
            return False
        if str(op.get("path") or "") not in hard_fact_paths:
            return False
        if str(op.get("op") or "").strip().lower() not in {"add", "replace"}:
            return False
    return evidence_has_direct_spans(evidence)

