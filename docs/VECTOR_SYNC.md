# Vector Sync Setup Guide

## Overview

Vector synchronization enables semantic search capabilities by storing embeddings in Qdrant. It's optional and disabled by default, with graceful fallback to a simple memory store. As of 2025, the default vector path uses a unified client that talks directly to Qdrant, with an optional Vector Adapter for legacy compatibility.

> Cerberus – Backup & Guardian (Optional)
> - Set `ENABLE_CERBERUS=true` to enable protective snapshots around risky vector ops.
> - Automatic pre-risk snapshots: `--create-collections`, `qdrant_ingest.py` runs, and filesystem changes under `/qdrant/storage/collections` (if monitored).
> - Manual: `./cerberus-cli snapshot | list | restore <id>`; API: `POST /backup/snapshot`, `GET /backup/list`, `POST /backup/restore/:id`.
> - Retention: keep 3 by default (`CERBERUS_RETENTION=3`). Archives live in `/backups/` (or fallback).
> - Safety: when disabled, all hooks are NO-OP. Use `--force` to override pre-snapshot when allowed.

## Configuration

### Environment Variables

| Variable | Purpose | Default | Example |
|----------|---------|---------|---------|
| `AX_VECTOR_SYNC` | Enable vector sync | `false` | `true` |
| `AX_QDRANT_URL` | Qdrant base URL | `http://localhost:6333` | `http://remote-host:6333` |
| `QDRANT_HOST` | Qdrant hostname | `localhost` | `your-qdrant-host` |
| `QDRANT_PORT` | Qdrant port | `6333` | `6333` |
| `EMBEDDING_MODEL` | Embeddings model | `all-MiniLM-L6-v2` | `all-MiniLM-L6-v2` |
| `QDRANT_MEMORY_COLLECTION` | Memory collection name | `axiom_memories` | `axiom_memories` |
| `ENABLE_CERBERUS` | Enable Cerberus backups/guard | `false` | `true` |
| `CERBERUS_RETENTION` | Backups to keep | `3` | `5` |
| `CERBERUS_BACKUP_DIR` | Override backup dir | auto | `/data/backups` |
| `VECTOR_PATH` | Vector path (`qdrant` or `adapter`) | `qdrant` | `adapter` |
| `VECTOR_POD_URL` | Adapter base URL (if using adapter) | — | `http://vector:5001` |
| `AXIOM_CANARIES` | Startup canaries enabled | `true` | `false` |
| `AXIOM_COMPOSITE_SCORING` | Composite reranking | `false` | `true` |

### Enabling Vector Sync

```bash
# Method 1: Environment variables
export AX_VECTOR_SYNC=true
export AX_QDRANT_URL=http://localhost:6333
# NOTE: the private `ingest_world_map.py` CLI is not shipped in this public-safe tree.
# For local demos, run the Memory API + Qdrant and use the Memory API endpoints instead.

# Method 2: Command line flag
# (not available in public-safe tree)

# Method 3: Docker environment
docker compose -f docker-compose.qdrant.yml up -d  # Qdrant + Memory
```

### Remote Qdrant Setup

```bash
# Point to remote Qdrant instance
export AX_QDRANT_URL=http://your-qdrant-host:6333
export AX_VECTOR_SYNC=true

# With API key (if using Qdrant Cloud)
export AX_QDRANT_API_KEY=your-api-key

# Verify connectivity
curl $AX_QDRANT_URL/health
```

## Qdrant Collections

### Default Collections
- `axiom_memories` - Main memory storage with embeddings
- `axiom_beliefs` - Belief system entries  
- `axiom_memory_archives` - Archived memory entries

### Vector Configuration
- **Embedding Model**: `all-MiniLM-L6-v2` (384 dimensions)
- **Distance Metric**: Cosine similarity
- **Vector Size**: 384
- **Lazy Loading**: Models loaded only when vector sync enabled

## Health Checks & Diagnostics

### Basic Connectivity
```bash
# Test Qdrant health
curl $AX_QDRANT_URL/health | jq

# List collections
curl $AX_QDRANT_URL/collections | jq '.result.collections[].name'

# Check collection details
curl $AX_QDRANT_URL/collections/axiom_memories | jq
```

### Collection Information
```bash
# Get vector configuration
curl $AX_QDRANT_URL/collections/axiom_memories | jq '.result.config.params'

# Count points in collection
curl $AX_QDRANT_URL/collections/axiom_memories | jq '.result.points_count'

# Sample collection data
curl $AX_QDRANT_URL/collections/axiom_memories/points | jq '.result.points[:3]'
```

### Memory Pod Integration
```bash
# Test memory pod vector backend
curl http://localhost:5000/health
# Optional canary status
curl http://localhost:5000/canary/status || true

# Check memory statistics with vector info
curl http://localhost:5000/api/memory-stats | jq
```

## Dependencies & Installation

### Required Dependencies
```bash
# Install service requirements (public-safe tree)
pip install -r services/memory/requirements.txt
```

### Optional Dependencies
```bash
# This public-safe tree does not ship a `pyproject.toml` with extras.
# Install per-service requirements from `services/*/requirements.txt`.
```

## Lazy Loading & Fallback

### Lazy Import Strategy
- **Heavy dependencies** (`torch`, `transformers`, `sentence-transformers`) imported only when needed
- **Graceful fallback** if imports fail or Qdrant unavailable
- **Null embedder** provides deterministic vectors when vector sync disabled

### Fallback Behavior
```python
# Vector sync disabled or failed
- Memory operations continue with fallback store
- Ingestion succeeds without vector storage
- Search works with basic text matching
- No error interruption of core functionality
```

## Troubleshooting

### Common Issues

**Qdrant connection refused:**
```bash
# Check if Qdrant is running
docker compose -f docker-compose.qdrant.yml ps
curl $AX_QDRANT_URL/health

# Start Qdrant if needed
docker compose -f docker-compose.qdrant.yml up -d axiom_qdrant
```

**Vector dependencies missing:**
```bash
# Install vector extras
pip install -e .[vector]

# Check installation
python -c "import sentence_transformers; print('OK')"
python -c "import torch; print('OK')"
```

**Collections not found:**
```bash
# List available collections
curl $AX_QDRANT_URL/collections | jq

# Collections are created automatically on first use
# Run ingestion to create collections
python ingest_world_map.py --dry-run --vector-sync
```

**Performance issues:**
```bash
# Check vector dimensions match model
curl $AX_QDRANT_URL/collections/axiom_memories | jq '.result.config.params.vectors'

# Verify embedding model
echo $EMBEDDING_MODEL  # Should be all-MiniLM-L6-v2
```

### Debugging

```bash
# Enable verbose logging
export LOG_LEVEL=DEBUG
python ingest_world_map.py --vector-sync --dry-run --verbose

# Test embedding generation
python -c "
from sentence_transformers import SentenceTransformer
model = SentenceTransformer('all-MiniLM-L6-v2')
vec = model.encode('test')
print(f'Vector dim: {len(vec)}')
"

# Test Qdrant client
python -c "
from qdrant_client import QdrantClient
client = QdrantClient(url='$AX_QDRANT_URL')
print(client.get_collections())
"
```

## Integration with Memory System

### Memory Manager Integration
- **Fallback orchestration**: `pods.memory.memory_manager.MemoryManager`
- **Vector backend**: `pods.memory.qdrant_backend.QdrantMemoryBackend` 
- **Automatic routing**: Vector vs fallback based on `AX_VECTOR_SYNC`

### Lazy Initialization
- **Model loading**: Sentence transformer loaded on first vector operation
- **Client creation**: Qdrant client created when first needed
- **Collection setup**: Collections created automatically if missing

## Docker Integration

### Docker Compose Services
```yaml
# Qdrant service
qdrant:
  image: qdrant/qdrant:latest
  ports: ["6333:6333"]
  volumes: ["./.data/qdrant:/qdrant/storage"]

# Memory service with vector sync
axiom_memory:
  environment:
    USE_QDRANT_BACKEND: "1"
    QDRANT_HOST: axiom_qdrant
    QDRANT_PORT: "6333"
```

### Service Health Checks
```bash
# Check all services
docker compose -f docker-compose.qdrant.yml ps

# Check Qdrant logs
docker compose -f docker-compose.qdrant.yml logs axiom_qdrant

# Check memory service logs  
docker compose -f docker-compose.qdrant.yml logs axiom_memory
```

For ingestion workflow, see `docs/INGEST_WORLD_MAP.md`. For schema details, see `docs/SCHEMA.md`.

