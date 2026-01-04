FROM python:3.10-slim

# Set working directory to /app (as expected by memory manager and imports)
WORKDIR /app

# Install curl (useful for debugging pod health) and clean up cache
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Upgrade protobuf to support latest Weaviate client versions
RUN pip install --upgrade "protobuf>=4.21.0"

# Install memory pod dependencies (profile-selectable)
# - core: no local embeddings / no HF stack
# - vector: includes sentence-transformers/transformers/tokenizers
ARG AXIOM_MEMORY_PROFILE=vector
COPY services/memory/requirements-core.txt ./requirements-core.txt
COPY services/memory/requirements-vector.txt ./requirements-vector.txt
RUN pip install --no-cache-dir -r "requirements-${AXIOM_MEMORY_PROFILE}.txt"

# Set a default value for VECTOR_POD_URL (can be overridden at runtime)
# This prevents startup failures when env var is unset
ENV VECTOR_POD_URL=http://localhost:8011

# Copy the full repo into the container
COPY . .

# Run the memory API module on container startup
CMD ["python3", "-m", "pods.memory.pod2_memory_api"]
