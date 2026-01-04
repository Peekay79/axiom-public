import json
import pathlib

from pods.memory.world_map_models import parse_world_map


def load(fp="world_map.json"):
    return json.loads(pathlib.Path(fp).read_text())


def test_dual_shape_ok():
    raw = load("world_map.json")
    typed, norm, warns = parse_world_map(raw)
    assert isinstance(typed.entities, list)
    assert isinstance(typed.relationships, list)


def test_unique_ids_and_no_dangling():
    raw = load("world_map.json")
    typed, norm, _ = parse_world_map(raw)
    e_ids = {e.id for e in typed.entities}
    assert len(e_ids) == len(typed.entities)
    r_ids = {r.id for r in typed.relationships}
    assert len(r_ids) == len(typed.relationships)
    for r in typed.relationships:
        assert r.source in e_ids
        assert r.target in e_ids


def test_round_trip_normalize(tmp_path):
    src = tmp_path / "wm.json"
    src.write_text(json.dumps(load("world_map.json")))
    typed, norm, _ = parse_world_map(json.loads(src.read_text()))
    out = tmp_path / "out.json"
    out.write_text(json.dumps(norm, indent=2))
    norm2 = json.loads(out.read_text())
    assert isinstance(norm2["entities"], list)
    assert isinstance(norm2["relationships"], list)
