# Dockerfile for Vector Adapter service
FROM python:3.10-slim

# Set working directory
WORKDIR /app
COPY services/vector/vector_adapter.py ./vector_adapter.py

# Install system dependencies for key Python packages
RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    cmake \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Optional: faster pip and cleaner logs
ENV PIP_NO_CACHE_DIR=true
ENV PYTHONUNBUFFERED=1

# Copy and install Python dependencies
COPY services/vector/vector_requirements.txt ./requirements.txt
RUN pip install --upgrade pip && \
    pip install -r requirements.txt && \
    pip install aiohttp

# Optional: Verify aiohttp install
RUN python3 -c "import aiohttp; print('✅ aiohttp installed')"

# Copy service source code
COPY . ./

# Expose service port
EXPOSE 5001

# Optional healthcheck (adjust if needed)
# HEALTHCHECK CMD curl --fail http://localhost:5001/health || exit 1

# Start the vector adapter
CMD ["python3", "vector_adapter.py"]
