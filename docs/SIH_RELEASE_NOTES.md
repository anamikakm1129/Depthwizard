# DepthWizard: Smart India Hackathon (SIH 2026) Release Notes & Architecture Guide

**Version**: 1.0.0-rc1  
**Target Hardware Profile**: Low-Resource Entry-Level Workstation (Benchmark: Intel Core i3-6006U @ 2.00 GHz, 2 Cores / 4 Threads, 8 GB RAM, Pure CPU)  
**License**: Apache License 2.0  
**Repository**: Single-View Optical Remote-Sensing Elevation Estimation & Interactive 3D Terrain  

---

## 1. Executive Summary

DepthWizard addresses the SIH 2026 problem statement: **reconstructing 3D digital surface models (DSMs) and elevation data from single-view optical satellite and aerial imagery**. Traditional elevation extraction requires multi-angle stereo pairs (stereophotogrammetry) or airborne LiDAR, which are prohibitively costly, bandwidth-heavy, and unavailable for monocular archives.

DepthWizard solves this with a mathematically principled, pure-CPU architecture that executes in restricted, low-resource computing environments. In strict accordance with **Rule Section 2 (No Fake AI)**, DepthWizard never synthesizes elevations, invents scale factors, or masks relative disparities behind fake metric claims.

---

## 2. Scientific Architecture & Data Flow

```
[Optical Satellite/Aerial Image (GeoTIFF / PNG / JPEG)]
                 │
                 ▼
[Input Validation: Magic Bytes & 250 MB Size Limit]
                 │
                 ▼
[RasterIO Geospatial Extraction: CRS, Transform, Bounds, Nodata]
                 │
                 ▼
[Preprocessor: 518x518 Bicubic Resize + ImageNet Normalization]
                 │
                 ▼
[DepthInferenceEngine: ONNX Runtime CPUExecutionProvider (INT8)]
                 │
                 ▼
[Postprocessor: Bilinear Upsample to Native Res + [0, 1] Disparity]
                 │
                 ▼
[OutputValidator: NaN / Inf / Trivial Variance Gating]
                 │
                 ▼
     [Relative DSM Product (unitless_disparity, is_metric=False)]
                 │
        ┌────────┴─────────────────────────────────────────┐
        │ No GCPs                                          │ Surveyed GCPs (≥3)
        ▼                                                  ▼
[Export Relative DSM]                             [MetricCalibrator: OLS Fit]
  - Tag: RELATIVE_DSM                               - Linear: Z = s·d + t
  - Units: unitless_disparity                       - Gate: RMSE ≤ 15m, R² ≥ 0.20
  - is_metric: False                                       │
  - Relief IQR, P10/P50/P90                                │ Passes Gating
                                                           ▼
                                                  [Export Calibrated DSM]
                                                    - Tag: CALIBRATED_DSM
                                                    - Units: meters
                                                    - is_metric: True
                                                    - GDAL Provenance Tags
                 │                                         │
                 └────────────────────┬────────────────────┘
                                      │
                                      ▼
             [TerrainMeshGenerator: Wavefront OBJ + Viridis Texture]
                                      │
                                      ▼
             [Three.js WebGL Viewport & Single-Origin SPA (/app)]
                                      │
                                      ▼
             [Scientific Evaluation Engine (POST /api/v1/evaluate)]
```

---

## 3. Real Model & Checkpoint Provenance

- **Model Architecture**: Vision Transformer (ViT-Small) monocular depth estimation backbone quantized to INT8 precision.
- **Model Checkpoint**: `backend/models/depth_anything_v2_vits_int8.onnx`
- **File Size**: `26.00 MB` (highly portable and air-gap friendly).
- **License**: Apache-2.0.
- **Inference Runtime**: ONNX Runtime with `CPUExecutionProvider`.
- **Threading Strategy**: OpenMP intra-op parallelism pinned to `DEPTHWIZARD_ONNX_INTRA_OP_THREADS=2` to eliminate cache thrashing on dual-core physical CPUs.
- **GPU Requirement**: **Zero**. Operates completely on pure CPU.

---

## 4. Scientific Semantics: Relative Disparity vs. Metric Elevation

DepthWizard maintains an unyielding scientific boundary between uncalibrated optical disparity and validated metric elevations:

### A. Relative Surface Model (`RELATIVE_DSM`)
- **Units**: `unitless_disparity`
- **Range**: Strictly normalized in $[0.0, 1.0]$.
- **`is_metric`**: Strictly `False`.
- **Scientific Rationale**: Monocular depth models inherently predict relative inverse depth (disparity up to an unknown affine ambiguity: $d = a \cdot z^{-1} + b$). Georeferencing headers (coordinates and CRS) define **where** a pixel is on Earth, but do **not** calibrate its vertical elevation. Uncalibrated rasters are labeled solely as `RELATIVE_DSM`.

### B. Metric Elevation Model (`CALIBRATED_DSM`)
- **Units**: `meters`
- **`is_metric`**: Strictly `True`.
- **Calibration Engine**: Empirical ordinary least squares (OLS) against $\ge 3$ surveyed Ground Control Points (GCPs):
  $$\min_{s, t} \sum_{i=1}^N \left(s \cdot d_i + t - Z_i\right)^2$$
- **Quality Gating Thresholds**:
  - $\text{RMSE} \le 15.0\,\text{meters}$
  - $R^2 \ge 0.20$
  - $\text{std}(d) \ge 10^{-5}$ (variance check)
- **Rejection Behavior**: If gating fails or $<3$ GCPs exist within bounds, the system safely falls back to `RELATIVE_DSM` with explicit provenance warnings.

---

## 5. Hardware Requirements & Benchmarking

| Component | Minimum Specification | Recommended Specification |
|---|---|---|
| **CPU** | Intel Core i3-6006U (2C/4T @ 2.00 GHz, AVX2) | 4+ Physical Cores (x86_64 AVX2 or Apple Silicon) |
| **RAM** | 8 GB | 16 GB |
| **Disk** | 2 GB free | 5 GB free |
| **GPU** | **None** (Pure CPU) | None required |
| **OS** | Windows 10/11, Ubuntu 22.04+, macOS 12+ | Windows 11 / Ubuntu 22.04 LTS |

**Observed Pure CPU Performance (Intel i3 profile)**:
- 518x518 INT8 ONNX inference: ~1.2 – 2.5 seconds
- End-to-end pipeline (Inference + GeoTIFF export + 3D Mesh generation): ~3.5 – 6.0 seconds

---

## 6. Supported Data Formats

### Input Imagery
- **GeoTIFF** (`.tif`, `.tiff`): Copernicus Sentinel-2, Landsat 8/9, NAIP Orthophotos, UAV Orthomosaics. Geospatial metadata (CRS, geotransform, bounds) is automatically preserved.
- **Standard Imagery** (`.png`, `.jpg`, `.jpeg`): Optical photography, drone captures without embedded geospatial headers. Treated on a local pixel coordinate grid.

### Output Artifacts
- **Elevation Raster**: 32-bit floating point GeoTIFF (`.tif`) with LZW compression and GDAL calibration provenance tags (`SCALE_FACTOR`, `SHIFT_OFFSET`, `CALIBRATION_RMSE`, `CALIBRATION_R2`).
- **Visual Preview**: 8-bit RGB colorized raster preview (`.png`) using the perceptually uniform Viridis or Turbo colormap.
- **3D Terrain Model**: Wavefront 3D OBJ mesh (`.obj`) with companion material file (`.mtl`) and draped optical texture.
- **Residual Error Map**: Diverging coolwarm colormapped error raster (`.png`) generated by the scientific evaluation engine.

---

## 7. Known Scientific Limitations

1. **Monocular Scale Ambiguity**: In the absence of external surveyed GCPs or reference elevation data, absolute metric height cannot be deduced purely from single-view optical pixels.
2. **Terrain Shadowing**: Extreme relief, mountain ridgelines, and deep cast shadows cause local contrast loss that may attenuate predicted surface roughness.
3. **GAMUS / nDSM Domain Boundary**: When calibrated against Normalized Digital Surface Models (nDSM), the output reflects above-ground object heights (AGL meters) rather than orthometric elevation above mean sea level. DepthWizard explicitly tags this domain warning.

---

## 8. Validation & Evaluation Methodology

The scientific accuracy evaluation route (`POST /api/v1/evaluate`) performs dense pixel residual analysis ($e_i = z_{pred, i} - z_{ref, i}$):

- **Mean Absolute Error (MAE)**: $\text{MAE} = \frac{1}{N}\sum |e_i|$
- **Root Mean Square Error (RMSE)**: $\text{RMSE} = \sqrt{\frac{1}{N}\sum e_i^2}$
- **Mean Bias**: $\text{Bias} = \frac{1}{N}\sum e_i$
- **Pearson Correlation ($r$)**: Evaluates spatial gradient and slope alignment.
- **Coefficient of Determination ($R^2$)**: Quantifies explained variance.
- **Threshold Accuracies ($\delta_1, \delta_2, \delta_3$)**: Percentage of pixels satisfying $\max(\frac{z_{pred}}{z_{ref}}, \frac{z_{ref}}{z_{pred}}) < 1.25^k$.
- **Spatial Residual Error Map**: Exportable PNG with diverging blue-white-red colorbar encoding local under- and over-estimation.

---

## 9. Verification & Audit Scorecard

| Verification Harness | Scope | Checks Passed |
|---|---|---|
| [`frontend/test_frontend_contracts.mjs`](file:///c:/Users/Mahesh/Documents/Downloads/Depthwizard/frontend/test_frontend_contracts.mjs) | Frontend API contracts, error sanitization, GCP serialization | **4 / 4** (100%) |
| [`scripts/verify_final_integration.py`](file:///c:/Users/Mahesh/Documents/Downloads/Depthwizard/scripts/verify_final_integration.py) | Master pipeline: ONNX, Sentinel-2, NAIP, GCPs, Evaluation, SPA | **56 / 56** (100%) |
| [`scripts/verify_phase9.py`](file:///c:/Users/Mahesh/Documents/Downloads/Depthwizard/scripts/verify_phase9.py) | Packaging, configuration, degraded mode, launchers, Dockerfile | **43 / 43** (100%) |
| [`scripts/verify_container_deployment.py`](file:///c:/Users/Mahesh/Documents/Downloads/Depthwizard/scripts/verify_container_deployment.py) | Live Docker containerization, volume persistence, host RasterIO | **49 / 49** (100%) |
| `backend/tests/` (Pytest) | Unit test suites across inference, geospatial, and API | **66 / 66** (100%) |
| **Total Verified Automated Checks** | **Comprehensive System Surface** | **218 / 218 (100%)** |

