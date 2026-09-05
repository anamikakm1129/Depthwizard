# DepthWizard SIH 2026: Pure CPU Container Image
# ===============================================
FROM python:3.11-slim-bookworm

LABEL maintainer="DepthWizard Team"
LABEL description="Single-View Optical Remote Sensing to Elevation & 3D Terrain"

# Set environment flags
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEPTHWIZARD_HOST=0.0.0.0 \
    DEPTHWIZARD_PORT=8000 \
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

# Copy application backend, production frontend dist, and scripts
COPY backend/ /app/backend/
COPY frontend/dist/ /app/frontend/dist/
COPY scripts/ /app/scripts/
COPY .env.example /app/.env.example

# Create storage directories
RUN mkdir -p /app/backend/models /app/backend/uploads /app/backend/outputs

# Expose HTTP service port
EXPOSE 8000

# Health check against DepthWizard health API
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

# Launch using unified runner
CMD ["python", "scripts/run_app.py", "--host", "0.0.0.0", "--port", "8000", "--skip-validation"]
