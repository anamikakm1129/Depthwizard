# DepthWizard SIH 2026: Deployment & Packaging Guide

This guide documents reproducible deployment workflows for DepthWizard across **Windows**, **macOS**, and **Linux** environments, optimized for **pure CPU execution** on low-resource hardware (benchmark target: Intel Core i3-6006U, 2 cores / 4 threads, ~8 GB RAM).

---

## 1. System Requirements

| Specification | Minimum Target | Recommended Production |
|---|---|---|
| **Operating System** | Windows 10/11, macOS 12+ (Intel/Apple Silicon), Linux (Ubuntu 22.04+) | Ubuntu 22.04 LTS / Windows 11 |
| **Processor** | Intel Core i3-6006U (2C/4T @ 2.00 GHz, AVX2) | 4+ physical cores (AVX2 / VNNI or Apple Silicon NE) |
| **System Memory (RAM)** | 8 GB | 16 GB |
| **GPU Requirement** | **None** (Pure CPU execution via ONNX Runtime `CPUExecutionProvider`) | Optional future CUDA/CoreML acceleration |
| **Disk Space** | 2 GB free (includes dependencies, INT8 ONNX weights, and outputs) | 10 GB free |
| **Python Runtime** | Python 3.10 or 3.11 (64-bit) | Python 3.11.9 (64-bit) |

---

## 2. Bare-Metal Local Deployment

### Step 2.1: Clone and Create Virtual Environment

**Windows (PowerShell):**
```powershell
# Navigate to project workspace
cd Depthwizard

# Create virtual environment
python -m venv venv

# Activate virtual environment
.\venv\Scripts\Activate.ps1
```

**macOS / Linux:**
```bash
cd Depthwizard
python3 -m venv venv
source venv/bin/activate
```

---

### Step 2.2: Install Dependencies

All dependencies are strictly curated to avoid unnecessary cloud SDKs, CUDA, or GPU-only packages:

```bash
pip install --upgrade pip
pip install -r backend/requirements.txt
```

> **Note on Geospatial GDAL/RasterIO:**
> On Windows and macOS, official `rasterio` binary wheels from PyPI bundle self-contained GDAL, PROJ, and GEOS libraries. No separate system GDAL installation is required.

---

### Step 2.3: Acquire Real Model Weights & Sample Data

In strict adherence to **Rule Section 2 (No Fake AI)**, DepthWizard never uses simulated or placeholder models. Download the verified INT8 ONNX checkpoint:

```bash
python scripts/download_assets.py
```

This verifies:
- `backend/models/depth_anything_v2_vits_int8.onnx` (26 MB, Apache-2.0)
- `tests/data/sample_geotiff.tif` (Real Copernicus Sentinel-2 GeoTIFF)
- `tests/data/sample_aerial.tif` (Real NAIP Orthophoto GeoTIFF)

---

### Step 2.4: Pre-flight System Validation

Execute the diagnostic tool to audit your environment before launch:

```bash
python scripts/validate_setup.py
```

---

### Step 2.5: Launch the Application

Use the provided platform launcher or unified Python script:

**Windows One-Click Launcher:**
```cmd
run_depthwizard.bat
```

**macOS / Linux Launcher:**
```bash
chmod +x run_depthwizard.sh
./run_depthwizard.sh
```

**Direct Python Launcher:**
```bash
python scripts/run_app.py --host 127.0.0.1 --port 8000
```

Once running, access the services:
- **DepthWizard Web Application (SPA)**: [http://localhost:8000/app](http://localhost:8000/app)
- **Interactive OpenAPI Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Alternative API Docs**: [http://localhost:8000/redoc](http://localhost:8000/redoc)
- **Health Check**: [http://localhost:8000/api/v1/health](http://localhost:8000/api/v1/health)

---

## 3. Configuration & Environment Variables

DepthWizard supports flexible configuration via a `.env` file in the project root or system environment variables prefixed with `DEPTHWIZARD_`:

| Environment Variable | Default Value | Description |
|---|---|---|
| `DEPTHWIZARD_HOST` | `127.0.0.1` | Network interface to bind (`0.0.0.0` for all interfaces) |
| `DEPTHWIZARD_PORT` | `8000` | HTTP service port |
| `DEPTHWIZARD_DEBUG` | `false` | Enable ASGI reload and verbose logging |
| `DEPTHWIZARD_TARGET_DEVICE` | `CPU` | Target compute provider (`CPUExecutionProvider`) |
| `DEPTHWIZARD_ONNX_INTRA_OP_THREADS` | `2` | OpenMP intra-op CPU threads (tuned to physical cores) |
| `DEPTHWIZARD_MODEL_PATH` | `backend/models/depth_anything_v2_vits_int8.onnx` | Relative or absolute path to ONNX model |
| `DEPTHWIZARD_UPLOAD_DIR` | `backend/uploads` | Directory for uploaded source imagery |
| `DEPTHWIZARD_OUTPUT_DIR` | `backend/outputs` | Directory for generated GeoTIFFs, OBJs, and error maps |
| `DEPTHWIZARD_MAX_UPLOAD_SIZE_MB` | `250` | Maximum file upload size threshold in megabytes |
| `DEPTHWIZARD_CORS_ORIGINS` | `["*"]` | Allowed CORS origins (JSON array string) |

To customize, copy the template:
```bash
cp .env.example .env
```

---

## 4. Docker Container Deployment

For containerized deployment on servers, virtual machines, or developer workstations:

### Step 4.1: Build and Run with Docker Compose

Ensure model weights are present in `./backend/models/`:
```bash
python scripts/download_assets.py
```

Start the containerized stack:
```bash
docker compose up -d --build
```

### Step 4.2: Verify Container Health

```bash
docker compose ps
curl http://localhost:8000/api/v1/health
```

### Step 4.3: View Logs and Stop Container

```bash
# View real-time logs
docker compose logs -f

# Stop and clean up
docker compose down
```

---

## 5. Offline & Air-Gapped Deployment

For deployment in restricted or non-internet connected environments:
1. Perform steps 2.1–2.3 on a connected machine to create `venv/` and download `depth_anything_v2_vits_int8.onnx`.
2. Bundle the entire directory including `backend/models/` and pre-built `frontend/dist/`.
3. Transfer bundle to target offline machine.
4. Run `python scripts/validate_setup.py` to confirm zero internet calls are made during inference and evaluation.

---

## 6. Troubleshooting

| Issue | Root Cause | Remediation |
|---|---|---|
| **HTTP 503 on `/process`** | Model checkpoint missing at startup | Run `python scripts/download_assets.py` to acquire official weights. |
| **Port 8000 already in use** | Another service is using port 8000 | Launch on a different port: `python scripts/run_app.py --port 8080`. |
| **Inference latency high (>30s)** | Cache thrashing from excessive threads | Ensure `DEPTHWIZARD_ONNX_INTRA_OP_THREADS=2` matches physical core count. |
| **Frontend build missing** | `frontend/dist` directory absent | Run `cd frontend && npm install && npm run build` (requires Node.js 18+). |
