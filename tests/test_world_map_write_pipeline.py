import json
import os
import tempfile
import unittest


from pods.memory.world_map_write import (
    apply_ops_in_memory,
    atomic_write_world_map,
    should_auto_apply_kurt,
    validate_ops,
)


class TestWorldMapWritePipeline(unittest.TestCase):
    def _base_world_map(self):
        return {
            "entities": [
                {"id": "example_person", "wife_name": "Old", "kids": []},
            ],
            "relationships": [],
        }

    def test_validator_rejects_non_allowlisted_path(self):
        obj = self._base_world_map()
        vr = validate_ops(
            world_map_obj=obj,
            entity_id="example_person",
            ops=[{"op": "replace", "path": "/password", "value": "x"}],
            confidence=0.99,
            evidence={},
            require_entity_exists=True,
        )
        self.assertFalse(vr.ok)
        self.assertEqual(vr.error, "path_not_allowed")

    def test_apply_produces_backup_and_atomic_write(self):
        obj = self._base_world_map()
        new_obj, _changed = apply_ops_in_memory(
            world_map_obj=obj,
            entity_id="example_person",
            ops=[{"op": "replace", "path": "/wife_name", "value": "Hev"}],
        )
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "world_map.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(obj, fh)
            tmp_path, backup_path = atomic_write_world_map(
                world_map_path=path, new_obj=new_obj, backup_ts="20250101_000000"
            )
            # tmp_path is replaced; should not exist anymore.
            self.assertFalse(os.path.exists(tmp_path))
            self.assertTrue(os.path.exists(backup_path))
            with open(path, "r", encoding="utf-8") as fh:
                written = json.load(fh)
            ent = [e for e in written.get("entities", []) if e.get("id") == "example_person"][0]
            self.assertEqual(ent.get("wife_name"), "Hev")

    def test_auto_apply_requires_extracted_span_substring(self):
        ops = [{"op": "replace", "path": "/wife_name", "value": "Hev"}]
        ok = should_auto_apply_kurt(
            write_enabled=True,
            auto_apply_enabled=True,
            entity_id="example_person",
            confidence=0.95,
            min_confidence=0.95,
            ops=ops,
            evidence={"source": "user", "raw_text": "ExamplePerson's wife's name is Hev.", "extracted_spans": ["Hev"]},
        )
        self.assertTrue(ok)
        bad = should_auto_apply_kurt(
            write_enabled=True,
            auto_apply_enabled=True,
            entity_id="example_person",
            confidence=0.99,
            min_confidence=0.95,
            ops=ops,
            evidence={"source": "user", "raw_text": "ExamplePerson's wife's name is Hev.", "extracted_spans": ["NotThere"]},
        )
        self.assertFalse(bad)


if __name__ == "__main__":
    unittest.main()

