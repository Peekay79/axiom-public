#!/bin/bash
set -e
python scripts/verify_schema.py --host localhost --port 6333 --collection $(python -c "from memory.memory_collections import memory_collection; print(memory_collection())") --sample 1000