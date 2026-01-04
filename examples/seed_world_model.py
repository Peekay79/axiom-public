#!/usr/bin/env python3
"""
Example data only — replace with your own private configuration.

This helper shows how you might seed a minimal world-map file locally for demos.
It intentionally uses fictional entities and contains no PII.
"""

from __future__ import annotations

import json
from pathlib import Path


def main() -> None:
    examples_dir = Path(__file__).resolve().parent
    world_map_path = examples_dir / "world_map.example.json"
    data = json.loads(world_map_path.read_text(encoding="utf-8"))

    print(f"Loaded example world map with {len(data.get('entities', []))} entities.")
    print("Tip: copy this file to a private `world_map.json` (do not commit) and customize it.")


if __name__ == "__main__":
    main()

