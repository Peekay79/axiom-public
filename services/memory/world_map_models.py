from __future__ import annotations

from typing import Any, Dict, List, Tuple, Union

from pydantic import BaseModel, ConfigDict, Field


class Entity(BaseModel):
    model_config = ConfigDict(extra="allow", str_strip_whitespace=True)
    id: str = Field(..., min_length=1)
    type: str = Field(..., min_length=1)


class Relationship(BaseModel):
    model_config = ConfigDict(extra="allow", str_strip_whitespace=True)
    id: str = Field(..., min_length=1)
    type: str = Field(..., min_length=1)
    source: str = Field(..., min_length=1)
    target: str = Field(..., min_length=1)


class WorldMap(BaseModel):
    model_config = ConfigDict(extra="allow")
    version: str = "1.0.0"
    entities: List[Entity] = Field(default_factory=list)
    relationships: List[Relationship] = Field(default_factory=list)


def _coerce_dual_shape(
    section: Union[Dict[str, Any], List[Dict[str, Any]], None], kind: str
) -> List[Dict[str, Any]]:
    if section is None:
        return []
    if isinstance(section, list):
        out = []
        for i, it in enumerate(section):
            if not isinstance(it, dict):
                it = {"type": str(it)}
            if "id" not in it:
                it = dict(it)
                it["id"] = f"{'e' if kind=='entity' else 'rel'}_{i}"
            out.append(it)
        return out
    if isinstance(section, dict):
        out = []
        for k, v in section.items():
            v = dict(v) if isinstance(v, dict) else {"type": str(v)}
            v.setdefault("id", k)
            out.append(v)
        return out
    return []


def parse_world_map(raw: Dict[str, Any]) -> Tuple[WorldMap, Dict[str, Any], List[str]]:
    warnings: List[str] = []
    ents_raw = raw.get("entities")
    rels_raw = raw.get("relationships")
    if isinstance(ents_raw, dict):
        warnings.append(
            "DEPRECATION: entities provided as dict; array shape is canonical."
        )
    if isinstance(rels_raw, dict):
        warnings.append(
            "DEPRECATION: relationships provided as dict; array shape is canonical."
        )
    ents = _coerce_dual_shape(ents_raw, "entity")
    rels = _coerce_dual_shape(rels_raw, "relationship")
    wm_norm = {
        "version": raw.get("version", "1.0.0"),
        "entities": ents,
        "relationships": rels,
        **{
            k: v
            for k, v in raw.items()
            if k not in {"version", "entities", "relationships"}
        },
    }
    typed = WorldMap.model_validate(wm_norm)
    return typed, wm_norm, warnings
