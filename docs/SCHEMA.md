# World Map Schema v1 Guide

## Overview

Stevebot uses a standardized world map format for representing entities, relationships, and system components. The canonical format ensures consistent data structure and enables reliable parsing and validation.

## Canonical Format Specification

### Required Top-Level Structure
```json
{
  "version": "1.0.0",
  "entities": [...],
  "relationships": [...]
}
```

### Version Field
- **Format**: `1.x.y` (semantic versioning)  
- **Current**: `1.0.0`
- **Purpose**: Schema evolution and migration support
- **Validation**: Must match pattern `^1\.[0-9]+\.[0-9]+$`

### Entities Array
- **Format**: Array of objects
- **Required fields**: `id` (string), `type` (string)
- **Additional properties**: Allowed (flexible schema)

```json
{
  "entities": [
    {
      "id": "axiom",
      "type": "agent", 
      "full_name": "Axiom AI Assistant",
      "goals": ["understand", "help", "learn"]
    },
    {
      "id": "example_person",
      "type": "human",
      "job_title": "Developer"
    }
  ]
}
```

### Relationships Array  
- **Format**: Array of objects
- **Required fields**: `id` (string), `type` (string), `source` (string), `target` (string)
- **Additional properties**: Allowed

```json
{
  "relationships": [
    {
      "id": "mentorship",
      "type": "mentored_by",
      "source": "axiom", 
      "target": "example_person",
      "description": "ExamplePerson mentors Axiom in development"
    }
  ]
}
```

## JSON Schema Validation

### Schema File
- **Location**: `docs/world_map.schema.json`
- **Standard**: JSON Schema Draft 2020-12  
- **Schema URL**: `https://peekay.ai/schemas/world_map.schema.json`

### Validation Commands
```bash
# Validate using Makefile
make schema

# Direct validation
python tools/validate_world_map.py world_map.json

# Pre-commit hook validation
pre-commit run check-jsonschema --files world_map.json
```

### Validation Output
```bash
# Success
✅ Schema valid

# Errors
❌ ["entities", 0]: 'id' is a required property
❌ ["relationships", 2]: 'source' is a required property
```

## Legacy Format Support (Deprecated)

### Dict-Shaped Format
Older world maps used object/dictionary shapes:

```json
{
  "axiom": {"type": "agent", "goals": [...]},
  "example_person": {"type": "human", "job_title": "Developer"},
  "relationships": {
    "mentorship": {"type": "mentored_by", "source": "axiom", "target": "example_person"}
  }
}
```

### Migration Support
- **Reader compatibility**: Accepts both dict and array formats
- **Deprecation warning**: Logged when dict format detected
- **Writer behavior**: Always outputs canonical array format

### Normalization Process
```bash
# Convert to canonical arrays (recommended)
python tools/normalize_world_map.py world_map.json -o world_map.json

# In-place normalization
python tools/normalize_world_map.py world_map.json --in-place

# Makefile shortcut
make normalize
```

## Dual-Shape Parser

### Implementation
- **Location**: `pods.memory.world_map_models.parse_world_map()`
- **Input**: Raw JSON (dict or array format)
- **Output**: Typed `WorldMap` object + normalized dict + warnings

### Pydantic Models
```python
class Entity(BaseModel):
    id: str = Field(..., min_length=1)
    type: str = Field(..., min_length=1)
    # Additional fields allowed via extra="allow"

class Relationship(BaseModel): 
    id: str = Field(..., min_length=1)
    type: str = Field(..., min_length=1)
    source: str = Field(..., min_length=1)
    target: str = Field(..., min_length=1)

class WorldMap(BaseModel):
    version: str = "1.0.0"
    entities: List[Entity] = Field(default_factory=list)
    relationships: List[Relationship] = Field(default_factory=list)
```

## Validation Integration

### Pre-commit Hooks
The repository includes automatic schema validation:

```yaml
# .pre-commit-config.yaml
- repo: https://github.com/python-jsonschema/check-jsonschema
  hooks:
    - id: check-jsonschema
      files: ^world_map\.json$
      args: [--schemafile, docs/world_map.schema.json]
```

### CI Pipeline
```yaml
# .github/workflows/ci.yml
- run: make schema  # Validates world_map.json in CI
```

### Development Workflow
```bash
# Before committing changes
make schema           # Validate schema
make normalize       # Convert to canonical format if needed
pre-commit run --all-files  # Run all checks
```

## Schema Evolution

### Future Versions
- **Version 1.x.y**: Backward compatible changes within v1
- **Version 2.0.0**: Breaking changes (future)
- **Migration tools**: Will be provided for major version upgrades

### Extensibility
- **Additional properties**: Allowed in all objects
- **Custom fields**: Can be added without breaking validation
- **Type flexibility**: Entity and relationship types are open strings

## Common Patterns

### Entity Types
```json
{
  "type": "agent",      // AI agents
  "type": "human",      // Human entities  
  "type": "company",    // Organizations
  "type": "system",     // System components
  "type": "platform"   // Communication platforms
}
```

### Relationship Types
```json
{
  "type": "mentored_by",   // Mentorship relationships
  "type": "works_at",      // Employment relationships
  "type": "creates",       // Creation relationships
  "type": "family_of",     // Family relationships
  "type": "uses"           // Usage relationships
}
```

### Relationship Expansion
List-valued sources/targets are automatically expanded:

```json
// Input (multi-target)
{
  "id": "family_rel",
  "source": "example_person", 
  "target": ["sarah", "kids"],
  "type": "family_of"
}

// Output (expanded)
[
  {
    "id": "family_rel__1",
    "source": "example_person",
    "target": "sarah", 
    "type": "family_of"
  },
  {
    "id": "family_rel__2", 
    "source": "example_person",
    "target": "kids",
    "type": "family_of"
  }
]
```

## Troubleshooting

### Common Schema Errors
```bash
# Missing required fields
❌ 'id' is a required property
# Fix: Add "id" field to entity/relationship

# Invalid version format  
❌ "2.0" does not match "^1\.[0-9]+\.[0-9]+$"
# Fix: Use "1.0.0" format

# Wrong data types
❌ [] is not of type 'object'
# Fix: Ensure entities/relationships are arrays of objects
```

### Validation Debugging
```bash
# Check current format
python -c "
import json
with open('world_map.json') as f:
    data = json.load(f)
print('Entities type:', type(data.get('entities')))
print('Relationships type:', type(data.get('relationships')))
"

# Test normalization
python tools/normalize_world_map.py world_map.json --dry-run
```

For ingestion details, see `docs/INGEST_WORLD_MAP.md`. For vector setup, see `docs/VECTOR_SYNC.md`.

