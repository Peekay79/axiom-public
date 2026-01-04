# World Map Ingestion Guide

This guide explains how to ingest world map data into the Axiom system for visualization and reasoning.

> Cerberus – Backup & Guardian (Optional)
> - Enable with `ENABLE_CERBERUS=true` to take pre-risk snapshots around ingestion that may touch vector collections.
> - Manual controls: `cerberus-cli snapshot|list|restore`.
> - Keep 3 versions by default (`CERBERUS_RETENTION=3`). NO-OP when disabled; `--force` can override when allowed.

## Overview

The `ingest_world_map.py` script ingests structured world map data into the Stevebot memory system, converting entities and relationships into memory entries with optional vector synchronization to Qdrant.

## Schema Requirements

- **Schema v1**: Uses arrays for `entities` and `relationships` with required `version` field (`1.x.y`)
- **Canonical format**: See `docs/SCHEMA.md` for complete specification
- **Dual-shape support**: Accepts both legacy dict-shaped and canonical array-shaped input
- **Schema validation**: Use `make schema` or `python tools/validate_world_map.py world_map.json`

## Command Line Usage

### Basic Commands

```bash
# Preview changes (recommended first step)
python ingest_world_map.py --dry-run --verbose
make ingest-dry

# Basic ingestion (fallback store only)
python ingest_world_map.py --force --verbose

# With vector sync to Qdrant
AX_VECTOR_SYNC=true python ingest_world_map.py --force --verbose --vector-sync

# Normalize source file during ingestion (explicit only)
python ingest_world_map.py --force --normalize-output
```

### Available Flags

- `--dry-run`: Preview what would be ingested without making changes
- `--force`: Skip safety confirmation and proceed with ingestion  
- `--vector-sync`: Enable vector database synchronization to Qdrant
- `--normalize-output`: Write normalized array-based schema to source file (explicit only)
- `--verbose`: Enable detailed logging output
- `--world-map-path PATH`: Use custom world map file (default: `world_map.json`)

### Environment Variables

- `AX_VECTOR_SYNC=true`: Enable vector sync (alternative to `--vector-sync`)
- `AX_QDRANT_URL`: Qdrant base URL (default: `http://localhost:6333`)
- `EMBEDDING_MODEL`: Model for embeddings (default: `all-MiniLM-L6-v2`)

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
make schema  # Check for validation errors
make normalize  # Convert to canonical format if needed
```

**Vector dependencies missing:**
```bash
pip install -e .[vector]  # Install vector extras
# Or disable vector sync: AX_VECTOR_SYNC=false
```

**Qdrant connection failed:**
```bash
curl $AX_QDRANT_URL/health  # Test connectivity
docker-compose up -d qdrant  # Start Qdrant if needed
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

- **Memory manager**: Uses `pods.memory.MemoryManager` for storage
- **Lazy imports**: Vector dependencies loaded only when needed
- **Graceful fallback**: Continues operation if vector sync fails
- **Dual-shape parsing**: Handled by `pods.memory.world_map_models.parse_world_map`

For schema details, see `docs/SCHEMA.md`. For vector setup, see `docs/VECTOR_SYNC.md`.

