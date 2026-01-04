# World Map Ingestion Guide

This guide explains how to ingest world map data into the Axiom system for visualization and reasoning.

> Cerberus – Backup & Guardian (Optional)
> - Enable with `ENABLE_CERBERUS=true` to take pre-risk snapshots around ingestion that may touch vector collections.
> - Manual controls: `cerberus-cli snapshot|list|restore`.
> - Keep 3 versions by default (`CERBERUS_RETENTION=3`). NO-OP when disabled; `--force` can override when allowed.

## Overview

This public-safe repo does **not** ship the private `ingest_world_map.py` / `tools/*` ingestion CLIs.

Instead, the recommended local/demo workflow is:

- Keep a private `world_map.json` (do not commit it)
- Run the Memory API, which automatically loads `world_map.json` and exposes world-map endpoints
- Trigger reloads via `POST /world_map/reload`

## Schema Requirements

- **Schema v1**: Uses arrays for `entities` and `relationships` with required `version` field (`1.x.y`)
- **Canonical format**: See `docs/SCHEMA.md` for complete specification
- **Dual-shape support**: Accepts both legacy dict-shaped and canonical array-shaped input
- **Schema validation**: Use `make schema` or `python tools/validate_world_map.py world_map.json`

## Command Line Usage

### Basic Commands

```bash
# Create a private world map file from the example (do NOT commit it)
cp examples/world_map.example.json world_map.json

# Run Memory API (local)
python -m venv .venv && . .venv/bin/activate
pip install -r services/memory/requirements.txt
MEMORY_API_PORT=8002 python -m pods.memory.pod2_memory_api

# Reload world map (if you've edited world_map.json)
curl -fsS -X POST http://localhost:8002/world_map/reload
```

### Available Flags

N/A in the public-safe tree (the ingestion CLI is not included).

### Environment Variables

- `WORLD_MAP_PATH`: Optional override for where the Memory API loads `world_map.json` from.
- `QDRANT_URL` / `QDRANT_HOST` / `QDRANT_PORT`: Qdrant connection for vector-backed features.

## How Ingestion Works

### Entity Processing
1. **Extraction**: Entities parsed from world map (dict or array format)
2. **Trait Analysis**: Automatic trait extraction based on type and properties
3. **Importance Scoring**: Calculated based on type, relationships, and centrality
4. **Memory Storage**: Stored as `entity` type memories with metadata

### Relationship Processing  
1. **Conversion**: Relationships converted to `event` type memories
2. **Expansion**: List-valued source/target edges expanded into multiple 1-1 relationships
3. **Event Creation**: Additional events created from entity properties (goals, capabilities, etc.)

### Vector Sync (Optional)
- **When enabled**: Embeddings generated and stored in Qdrant collections
- **Dependencies**: Requires `sentence-transformers`, `torch`, `qdrant-client`
- **Fallback**: If vector sync fails, ingestion continues with fallback store
- **Collections**: `axiom_memories`, `axiom_beliefs`, `axiom_memory_archives`

## Data Normalization

### Source File Handling
- **Ingestion never rewrites source files** unless `--normalize-output` is explicitly used
- **Reader accepts both shapes**: Legacy dict-shaped and canonical array-shaped
- **Writer always emits arrays**: Normalized output uses canonical array schema

### Manual Normalization
```bash
# Normalize to canonical arrays (recommended)
python tools/normalize_world_map.py world_map.json -o world_map.json
make normalize

# In-place normalization
python tools/normalize_world_map.py world_map.json --in-place
```

## Success Indicators

### Expected Log Output
```
✅ Loaded world map from world_map.json
📊 Found X top-level entries
📝 Ingested entity: [Name] (ID: [uuid], traits: [count], importance: [score])
🔗 Ingested event: [ID] (ID: [uuid], entities: [count])
📊 Statistics: X entities, Y relationships, Z events
```

### Ingestion Manifest
- **File**: `ingestion_manifest.json` 
- **Contains**: Timestamps, statistics, file hashes, configuration used
- **Purpose**: Audit trail and re-ingestion detection

## Troubleshooting

### Common Issues

**Schema validation errors:**
```bash
# Validate shape via the shipped parser (pydantic)
python -c "import json; from services.memory.world_map_models import parse_world_map; parse_world_map(json.load(open('world_map.json'))); print('✅ world_map.json parsed')"
```

**Vector dependencies missing:**
```bash
# Install service requirements (includes qdrant-client and sentence-transformers)
pip install -r services/memory/requirements.txt
```

**Qdrant connection failed:**
```bash
curl -fsS http://localhost:6333/health  # Test connectivity
docker compose -f docker-compose.qdrant.yml up -d axiom_qdrant  # Start Qdrant if needed
```

**Memory manager not available:**
- Expected in testing environments without full dependencies
- Use `--dry-run` to test without dependencies

### Debugging

```bash
# Enable verbose logging
python ingest_world_map.py --dry-run --verbose

# Check world map structure
python tools/validate_world_map.py world_map.json

# Test vector connectivity
curl http://localhost:6333/collections
```

## Integration Notes

- **World-map endpoints** (Memory API):
  - `GET /world_map/entity/<entity_id>`
  - `GET /world_map/relationships?entity_id=<id>&direction=any|out|in`
  - `GET /world_map/profile/<entity_id>`
  - `POST /world_map/reload`
- **Lazy imports**: Vector dependencies loaded only when needed
- **Graceful fallback**: Continues operation if vector sync fails
- **Dual-shape parsing**: Handled by `services/memory/world_map_models.py` (`parse_world_map`)

For schema details, see `docs/SCHEMA.md`. For vector setup, see `docs/VECTOR_SYNC.md`.

