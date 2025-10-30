# Multi-stage build for slim production image
FROM python:3.11-slim as builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
WORKDIR /app
COPY requirements.txt pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir --user -e .

# Production stage
FROM python:3.11-slim

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Copy Python packages from builder
COPY --from=builder /root/.local /root/.local

# Set up working directory
WORKDIR /app

# Copy source code (required for editable install to work)
COPY src ./src

# Copy application code (config, data, scripts, main.py remain at root)
# Note: docs/ is excluded via .dockerignore as it's not needed in containers
COPY config ./config
COPY data ./data
COPY scripts ./scripts
COPY tests ./tests
COPY main.py ./
COPY pyproject.toml ./

# Make sure scripts are executable
RUN chmod +x scripts/**/*.py || true

# Set environment variables
ENV PATH=/root/.local/bin:$PATH
ENV PYTHONUNBUFFERED=1
ENV TZ=UTC

# Default command (can be overridden in docker-compose)
CMD ["python", "main.py"]

