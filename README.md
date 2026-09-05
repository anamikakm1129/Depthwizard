# DepthWizard: Single-View Optical Remote-Sensing Elevation & 3D Terrain

[![License: Apache-2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python: 3.11](https://img.shields.io/badge/Python-3.11-green.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com/)
[![ONNX Runtime](https://img.shields.io/badge/ONNX_Runtime-CPU_INT8-informational.svg)](https://onnxruntime.ai/)
[![Three.js](https://img.shields.io/badge/Three.js-r170-black.svg)](https://threejs.org/)

> **Smart India Hackathon (SIH 2026)**  
> Production-grade pipeline converting single-view optical satellite and aerial imagery into georeferenced elevation representations and interactive 3D terrain visualizations. Strictly compliant with the **Zero Fake AI** standard (Rule §2) — real model checkpoints, deterministic scientific calibration, and publication-grade evaluation against ground-truth DEMs.

---

## Key Capabilities

- **Real Monocular Disparity Engine**: Runs quantized Vision Transformer (`depth_anything_v2_vits_int8.onnx`, 26.0 MB) via pure CPU ONNX Runtime with intra-op thread tuning (2 physical threads). No mock predictions or simulated fallbacks.
- **Geospatial Rigor**: Ingests GeoTIFFs (Sentinel-2, NAIP, UAV orthophotos); strictly preserves Coordinate Reference Systems (e.g., `EPSG:32618`), affine geotransforms, spatial bounding boxes, and nodata masks.
- **Surveyed GCP Metric Calibration**: Solves affine scale-and-shift via linear least squares using $\ge 3$ ground control points. Gated by strict RMSE ($\le 15.0\,\text{m}$) and $R^2$ ($\ge 0.20$) thresholds to produce validated `CALIBRATED_DSM` products without hallucinating elevation.
- **Ground-Truth Evaluation Engine (`POST /api/v1/evaluate`)**: Computes dense pixel-level residuals against authentic reference DEMs, generating statistical metrics (MAE, RMSE, Pearson $r$, $R^2$) and exportable diverging coolwarm residual error heatmaps.
- **Hardware-Accelerated 3D Terrain Viewer**: Interactive Three.js WebGL viewport rendering real displaced 3D terrain meshes textured with source optical imagery, featuring orbit controls, vertical exaggeration slider, and wireframe toggles.
- **CAD/GIS Asset Export**: Exports georeferenced GeoTIFF rasters, colorized PNGs, and Wavefront 3D OBJ meshes with companion MTL material files.
- **Single-Origin Deployment**: Serves the compiled React + Vite + Tailwind CSS frontend SPA directly from FastAPI at `/app`, backed by comprehensive Swagger documentation at `/docs`.

---

## Quick Start

For comprehensive bare-metal setup, environment variables, Docker instructions, and air-gapped configuration, see **[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)**.

### 1. One-Click Launchers

#### Windows
```cmd
run_depthwizard.bat
```

#### Linux / macOS
```bash
chmod +x run_depthwizard.sh
./run_depthwizard.sh
```

### 2. Python CLI
```bash
# 1. Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: .\venv\Scripts\activate

# 2. Install dependencies
pip install -r backend/requirements.txt

# 3. Download verified model weights and sample imagery
python scripts/download_assets.py

# 4. Run pre-flight validation
python scripts/validate_setup.py

# 5. Launch application
python scripts/run_app.py
```

### 3. Docker Containerization
```bash
docker-compose up --build
```

Access DepthWizard at:
- **Interactive Web App**: [http://127.0.0.1:8000/app](http://127.0.0.1:8000/app)
- **API Documentation (Swagger UI)**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **System Telemetry & Health Check**: [http://127.0.0.1:8000/api/v1/health](http://127.0.0.1:8000/api/v1/health)

---

## Repository Structure

```
Depthwizard/
├── .agents/rules/              # Development rules & Zero Fake AI directives
├── backend/
│   ├── app/
│   │   ├── api/                # FastAPI routes (process, evaluate, health) & schemas
│   │   ├── config.py           # Pydantic v2 environment settings
│   │   ├── evaluation/         # Pixel residual computer & error heatmap generator
│   │   ├── geospatial/         # RasterIO geotransform, CRS, and GCP calibrator
│   │   ├── inference/          # ONNX Runtime INT8 preprocessing, engine & postprocessing
│   │   ├── mesh/               # Wavefront OBJ 3D terrain generator
│   │   └── main.py             # FastAPI entrypoint and static SPA mount
│   ├── models/                 # Model checkpoints (depth_anything_v2_vits_int8.onnx)
│   ├── outputs/                # Generated GeoTIFFs, PNGs, and OBJ meshes
│   ├── uploads/                # Temporary uploaded images
│   ├── requirements.txt        # Minimal pinned backend dependencies
│   └── tests/                  # Pytest automated test suites (50 unit & integration tests)
├── docs/
│   └── DEPLOYMENT.md           # Comprehensive cross-platform deployment guide
├── frontend/                   # React + TypeScript + Vite + Three.js web application
│   ├── dist/                   # Production compiled SPA bundle
│   ├── src/                    # UI components (3D Terrain, 2D Comparison, Evaluation)
│   └── package.json            # Frontend dependencies
├── scripts/
│   ├── download_assets.py      # Automated model & sample image acquisition
│   ├── run_app.py              # Cross-platform CLI application launcher
│   ├── validate_setup.py       # Pre-flight environment diagnostics
│   └── verify_final_integration.py # 56-check master audit harness
├── tests/data/                 # Verified sample satellite & aerial GeoTIFF rasters
├── Dockerfile                  # CPU-optimized Python 3.11 slim container
├── docker-compose.yml          # Container configuration with CPU/memory limits
├── run_depthwizard.bat         # One-click Windows batch launcher
├── run_depthwizard.sh          # One-click Linux/macOS shell launcher
├── .env.example                # Environment variable configuration template
└── README.md                   # This document
```

---

## Verification & Testing

DepthWizard includes a comprehensive verification suite:

```bash
# 1. Run all 50 unit and integration tests
pytest -v

# 2. Run system pre-flight diagnostic check
python scripts/validate_setup.py

# 3. Run the 56-check Master Final Integration Audit
python scripts/verify_final_integration.py
```

---

## Deployment Guide Reference

Detailed production deployment specifications, including resource tuning for entry-level hardware (Intel Core i3-6006U / 8 GB RAM), CORS configuration, air-gapped setup, and container resource limits, are fully documented in **[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)**.

---

## License

This project is licensed under the Apache License 2.0. Model weights derive from Depth Anything V2 (Apache-2.0).

