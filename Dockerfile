# DepthWizard SIH 2026: Multi-Stage Container Image
# ===============================================

# ------------------------------------------------------------------------------
# Stage 1: Build production React + Three.js frontend SPA
# ------------------------------------------------------------------------------
FROM node:20-slim AS frontend-builder

WORKDIR /app/frontend

# Install dependencies using package-lock.json layer caching
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

# Copy full frontend source and configuration
COPY frontend/ ./

# Build production bundle into /app/frontend/dist
RUN npm run build

# ------------------------------------------------------------------------------
# Stage 2: Production Python runtime image (Pure CPU + AVX2)
# ------------------------------------------------------------------------------
FROM python:3.11-slim-bookworm

LABEL maintainer="DepthWizard Team"
LABEL description="Single-View Optical Remote Sensing to Elevation & 3D Terrain"

# Set environment flags
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEPTHWIZARD_HOST=0.0.0.0 \
    DEPTHWIZARD_TARGET_DEVICE=CPU \
    DEPTHWIZARD_ONNX_INTRA_OP_THREADS=2

# Install minimal system libraries for OpenCV headless and OpenMP CPU runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python backend dependencies first for layer caching
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /app/backend/requirements.txt

# Copy application backend, compiled production frontend dist from Stage 1, and scripts
COPY backend/ /app/backend/
COPY --from=frontend-builder /app/frontend/dist /app/frontend/dist
COPY scripts/ /app/scripts/
COPY .env.example /app/.env.example

# Create storage directories
RUN mkdir -p /app/backend/models /app/backend/uploads /app/backend/outputs

# Expose HTTP service port (default documentation)
EXPOSE 8000

# Health check against DepthWizard health API (dynamically uses PORT or default 8000)
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/api/v1/health || exit 1

# Launch using unified runner, respecting dynamic Railway PORT and auto-acquiring assets if needed
CMD ["python", "scripts/run_app.py", "--host", "0.0.0.0", "--skip-validation", "--download-assets"]
