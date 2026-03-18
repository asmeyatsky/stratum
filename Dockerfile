# =============================================================================
# Stratum — Multi-stage Docker build for on-premises deployment
#
# Stage 1 (builder): Install Python dependencies in an isolated environment
# Stage 2 (runtime): Slim production image with only runtime packages
#
# Build:   docker build -t stratum:latest .
# Run:     docker run -p 8000:8000 --env-file .env stratum:latest
# =============================================================================

# ---------------------------------------------------------------------------
# Stage 1: Builder — install dependencies
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS builder

WORKDIR /build

# Install build dependencies for compiled packages (WeasyPrint, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    libcairo2 \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency specification first for Docker layer caching
COPY pyproject.toml ./

# Install Python dependencies into a virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir . && \
    pip install --no-cache-dir uvicorn[standard]

# Copy application source code
COPY domain/ ./domain/
COPY application/ ./application/
COPY infrastructure/ ./infrastructure/
COPY presentation/ ./presentation/

# Install the application package itself
RUN pip install --no-cache-dir .

# ---------------------------------------------------------------------------
# Stage 2: Runtime — slim production image
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

LABEL maintainer="Stratum <engineering@stratum.dev>"
LABEL description="Stratum Code Intelligence Platform — on-premises deployment"

WORKDIR /app

# Install only runtime system libraries (WeasyPrint rendering dependencies)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libcairo2 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy the virtual environment from the builder stage
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application source
COPY domain/ ./domain/
COPY application/ ./application/
COPY infrastructure/ ./infrastructure/
COPY presentation/ ./presentation/

# Create non-root user for security
RUN groupadd --gid 1000 stratum && \
    useradd --uid 1000 --gid stratum --shell /bin/bash --create-home stratum && \
    chown -R stratum:stratum /app

USER stratum

# Configuration via environment variables (defaults for development)
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    STRATUM_HOST=0.0.0.0 \
    STRATUM_PORT=8000 \
    STRATUM_WORKERS=4 \
    STRATUM_LOG_LEVEL=info

EXPOSE 8000

# Health check — hit the /health endpoint every 30 seconds
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

# Run with uvicorn
CMD ["uvicorn", \
     "presentation.api.app:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "4", \
     "--log-level", "info", \
     "--access-log"]
