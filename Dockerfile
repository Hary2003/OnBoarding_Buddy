# syntax=docker/dockerfile:1
# ==============================================================================
# Production Dockerfile for OnBoarding Buddy
# Multi-stage optimized, secure, non-root runtime environment
# ==============================================================================

FROM python:3.12-slim

# Prevent Python from writing bytecode and enable real-time log flushing
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    PORT=8000 \
    ENVIRONMENT=production \
    DEBUG=false

# Install required system packages:
# - git: essential for GitPython repository indexing and diff analysis
# - curl: used for container healthchecks
# - ca-certificates: secure HTTPS repository cloning
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Create dedicated non-root application user for defense-in-depth security
RUN useradd -m -u 10001 -s /bin/bash appuser

# Set working directory and ensure appuser ownership
WORKDIR /app
RUN chown -R appuser:appuser /app

# Copy dependency specifications first for Docker layer caching
COPY --chown=appuser:appuser requirements.txt /app/requirements.txt

# Install dependencies into system Python
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application source code with non-root ownership
COPY --chown=appuser:appuser . /app/

# Switch to unprivileged runtime user
USER appuser

# Expose default HTTP service port
EXPOSE 8000

# Container liveness & readiness healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

# Start FastAPI application via app.py
CMD ["python", "app.py"]
