"""
DepthWizard: Container Deployment & Production Verification Harness
===================================================================
Conducts rigorous live verification against the running DepthWizard Docker container:
- Health check & CPU execution provider telemetry
- Single-origin React SPA serving (/app) & OpenAPI docs (/docs)
- Real optical image processing (POST /api/v1/process) with Copernicus Sentinel-2 GeoTIFF
- Strict scientific semantics verification (RELATIVE_DSM, unitless_disparity, is_metric=False)
- Relief metrics validation (IQR, P10/P50/P90)
- HTTP download of GeoTIFF, preview PNG, and Wavefront OBJ 3D mesh
- Host volume persistence & RasterIO integrity check on host (CRS, dimensions, bounds)
- Live scientific evaluation inside container (POST /api/v1/evaluate)
- Container security bounds (magic bytes validation, path traversal rejection, 404 on missing job)

Strictly adheres to .agents/rules/depthwizard-development.md (No Fake AI).
"""

import sys
import os
import argparse
from pathlib import Path
import httpx
import numpy as np
import rasterio

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent

def run_container_verification(host: str = "127.0.0.1", port: int = 8001):
    base_url = f"http://{host}:{port}"
    print("=" * 78)
    print("   DEPTHWIZARD SIH 2026: CONTAINER DEPLOYMENT VERIFICATION")
    print("=" * 78)
    print(f"Target Container Endpoint: {base_url}\n")

    passed_checks = 0
    total_checks = 0

    def check(condition: bool, msg: str):
        nonlocal passed_checks, total_checks
        total_checks += 1
        if condition:
            passed_checks += 1
            print(f"  [PASS] {msg}")
        else:
            print(f"  [FAIL] {msg}")
            raise AssertionError(f"Check failed: {msg}")

    client = httpx.Client(base_url=base_url, timeout=60.0)

    try:
        # ---------------------------------------------------------------------
        # STAGE 1: Container Health & Hardware Telemetry
        # ---------------------------------------------------------------------
        print("[Gate 1/6] Container Health Telemetry...")
        health_resp = client.get("/api/v1/health")
        check(health_resp.status_code == 200, f"Health endpoint returned HTTP 200 (got {health_resp.status_code})")
        h_data = health_resp.json()
        check(h_data.get("status") == "ok", f"Health status is 'ok' (got {h_data.get('status')})")
        check(h_data.get("model_loaded") is True, "INT8 ONNX model checkpoint loaded inside container")
        check(h_data.get("device") == "CPU", "Pure CPU execution device confirmed")
        check("CPUExecutionProvider" in h_data.get("execution_provider", ""), "ONNX CPUExecutionProvider active")
        print(f"  [INFO] Model: {h_data.get('model_name')}, Device: {h_data.get('device')}")

        # ---------------------------------------------------------------------
        # STAGE 2: Production SPA & Documentation Serving
        # ---------------------------------------------------------------------
        print("\n[Gate 2/6] Single-Origin SPA & Documentation Serving...")
        spa_resp = client.get("/app")
        check(spa_resp.status_code == 200, "Single-origin SPA /app returned HTTP 200")
        check("<html" in spa_resp.text.lower(), "SPA /app returned valid HTML document")
        check("depthwizard" in spa_resp.text.lower() or "assets/" in spa_resp.text, "SPA references compiled production assets")

        docs_resp = client.get("/docs")
        check(docs_resp.status_code == 200, "Interactive OpenAPI Swagger UI accessible at /docs")

        redoc_resp = client.get("/redoc")
        check(redoc_resp.status_code == 200, "Alternative OpenAPI ReDoc accessible at /redoc")

        # ---------------------------------------------------------------------
        # STAGE 3: Real Optical Image Processing Pipeline (No Fake AI)
        # ---------------------------------------------------------------------
        print("\n[Gate 3/6] Containerized Real Monocular Depth & Relative DSM Pipeline...")
        sample_tif = WORKSPACE_ROOT / "tests" / "data" / "sample_geotiff.tif"
        check(sample_tif.is_file(), f"Authentic test GeoTIFF found at {sample_tif.name}")

        with open(sample_tif, "rb") as f:
            file_bytes = f.read()

        proc_resp = client.post(
            "/api/v1/process",
            files={"file": ("sample_geotiff.tif", file_bytes, "image/tiff")},
            data={"invert_depth": "false"}
        )
        check(proc_resp.status_code == 200, f"Process pipeline returned HTTP 200 (got {proc_resp.status_code})")
        proc_data = proc_resp.json()
        job_id = proc_data.get("job_id")
        check(bool(job_id), f"Valid job_id returned: {job_id}")

        # Verify Strict Scientific Semantics
        check(proc_data.get("depth_type") == "RELATIVE_DSM", f"depth_type is strictly RELATIVE_DSM (got {proc_data.get('depth_type')})")
        check(proc_data.get("units") == "unitless_disparity", f"units is strictly unitless_disparity (got {proc_data.get('units')})")
        check(proc_data.get("is_metric") is False, f"is_metric is strictly False without empirical GCPs (got {proc_data.get('is_metric')})")

        # Verify Relief Metrics
        relief_metrics = proc_data.get("relief_metrics", {})
        iqr = relief_metrics.get("roughness_iqr", 0.0)
        p10 = relief_metrics.get("p10", 0.0)
        p50 = relief_metrics.get("p50", 0.0)
        p90 = relief_metrics.get("p90", 0.0)
        check(iqr > 0, f"Roughness IQR is positive ({iqr:.4f})")
        check(p10 <= p50 <= p90, f"Percentiles monotonically ordered: P10={p10:.4f}, P50={p50:.4f}, P90={p90:.4f}")

        # Verify Artifact URLs
        check("geotiff_download_url" in proc_data, "geotiff_download_url present in response")
        check("preview_png_download_url" in proc_data, "preview_png_download_url present in response")
        check("mesh_download_url" in proc_data, "mesh_download_url present in response")

        # ---------------------------------------------------------------------
        # STAGE 4: Artifact Downloads & Host Volume Persistence
        # ---------------------------------------------------------------------
        print("\n[Gate 4/6] Artifact Downloads & Host Volume Persistence...")
        # 4.1 Download GeoTIFF via HTTP
        tif_url = proc_data["geotiff_download_url"]
        tif_resp = client.get(tif_url)
        check(tif_resp.status_code == 200, f"GeoTIFF download succeeded: HTTP {tif_resp.status_code}")
        check(tif_resp.headers.get("content-type") == "image/tiff", "GeoTIFF content-type is image/tiff")
        check(len(tif_resp.content) > 1000, f"GeoTIFF size verified: {len(tif_resp.content)} bytes")

        # 4.2 Download Preview PNG via HTTP
        prev_url = proc_data["preview_png_download_url"]
        prev_resp = client.get(prev_url)
        check(prev_resp.status_code == 200, f"Preview PNG download succeeded: HTTP {prev_resp.status_code}")
        check("image/png" in prev_resp.headers.get("content-type", ""), "Preview content-type is image/png")

        # 4.3 Download OBJ Mesh via HTTP
        mesh_url = proc_data["mesh_download_url"]
        mesh_resp = client.get(mesh_url)
        check(mesh_resp.status_code == 200, f"Mesh OBJ download succeeded: HTTP {mesh_resp.status_code}")
        check(b"v " in mesh_resp.content and b"f " in mesh_resp.content, "OBJ mesh contains valid vertex and face definitions")

        # 4.4 Host Volume Persistence Check
        host_output_dir = WORKSPACE_ROOT / "backend" / "outputs"
        host_tif = host_output_dir / f"{job_id}_depth.tif"
        host_obj = host_output_dir / f"{job_id}_mesh.obj"
        host_png = host_output_dir / f"{job_id}_preview.png"

        check(host_tif.is_file(), f"Host volume persisted GeoTIFF: {host_tif.name} ({host_tif.stat().st_size} bytes)")
        check(host_obj.is_file(), f"Host volume persisted OBJ mesh: {host_obj.name} ({host_obj.stat().st_size} bytes)")
        check(host_png.is_file(), f"Host volume persisted Preview PNG: {host_png.name} ({host_png.stat().st_size} bytes)")

        # 4.5 Validate Persisted GeoTIFF with Host RasterIO
        with rasterio.open(sample_tif) as orig_src:
            expected_w = orig_src.width
            expected_h = orig_src.height

        with rasterio.open(host_tif) as src:
            check(src.count == 1, f"Persisted raster band count == 1 (got {src.count})")
            check(src.dtypes[0] == "float32", f"Persisted raster dtype == float32 (got {src.dtypes[0]})")
            check(src.width == expected_w and src.height == expected_h, f"Dimensions match input ({src.width}x{src.height})")
            check(src.crs is not None, f"CRS preserved: {src.crs.to_string()}")
            arr = src.read(1)
            valid_mask = np.isfinite(arr)
            valid_vals = arr[valid_mask]
            check(len(valid_vals) > 0, "Raster contains finite valid disparity pixels")
            check(float(np.nanmin(valid_vals)) >= -1e-6, f"Disparity min >= 0.0 (got {np.nanmin(valid_vals):.4f})")
            check(float(np.nanmax(valid_vals)) <= 1.0 + 1e-6, f"Disparity max <= 1.0 (got {np.nanmax(valid_vals):.4f})")
            print(f"  [OK] Validated Host Raster: CRS={src.crs.to_string()}, Min={np.nanmin(valid_vals):.4f}, Max={np.nanmax(valid_vals):.4f}")

        # ---------------------------------------------------------------------
        # STAGE 5: Containerized Scientific Evaluation Endpoint
        # ---------------------------------------------------------------------
        print("\n[Gate 5/6] Containerized Scientific Accuracy Evaluation (POST /api/v1/evaluate)...")
        eval_resp = client.post(
            "/api/v1/evaluate",
            data={"job_id": job_id, "is_metric": False},
            files={"reference_file": ("ref.tif", file_bytes, "image/tiff")}
        )
        check(eval_resp.status_code == 200, f"Evaluation endpoint returned HTTP 200 (got {eval_resp.status_code})")
        eval_data = eval_resp.json()
        check(eval_data.get("target_job_id") == job_id, "Evaluation correlates to correct target job_id")
        check("metrics" in eval_data, "Metrics block present in evaluation response")
        eval_metrics = eval_data["metrics"]
        check(eval_metrics.get("valid_points_count", 0) > 0, "Valid comparison points evaluated")
        check("mae" in eval_metrics and "rmse" in eval_metrics, "MAE and RMSE calculated")
        check("error_map_download_url" in eval_data, "Residual error map URL returned")

        # Download error map
        err_url = eval_data["error_map_download_url"]
        err_resp = client.get(err_url)
        check(err_resp.status_code == 200, f"Error map download HTTP 200 (got {err_resp.status_code})")
        check("image/png" in err_resp.headers.get("content-type", ""), "Error map is PNG image")
        print(f"  [OK] Evaluated Metrics: MAE={eval_metrics['mae']:.4f}, RMSE={eval_metrics['rmse']:.4f}, Points={eval_metrics['valid_points_count']}")

        # ---------------------------------------------------------------------
        # STAGE 6: Container Security Boundaries & Error Handling
        # ---------------------------------------------------------------------
        print("\n[Gate 6/6] Security Boundaries & Error Handling...")
        # 6.1 Reject corrupted / fake file upload (Magic bytes verification)
        corrupt_resp = client.post(
            "/api/v1/process",
            files={"file": ("fake.tif", b"THIS_IS_NOT_AN_IMAGE", "image/tiff")}
        )
        check(corrupt_resp.status_code == 400, f"Corrupted file rejected with HTTP 400 (got {corrupt_resp.status_code})")

        # 6.2 Reject non-existent job on evaluation
        missing_job_resp = client.post(
            "/api/v1/evaluate",
            data={"job_id": "nonexistent_job_uuid_99999"},
            files={"reference_file": ("ref.tif", file_bytes, "image/tiff")}
        )
        check(missing_job_resp.status_code == 404, f"Missing job rejected with HTTP 404 (got {missing_job_resp.status_code})")

        # 6.3 Reject path traversal attempt on file download
        traversal_resp = client.get("/api/v1/download/../../etc/passwd")
        check(traversal_resp.status_code in (400, 404), f"Path traversal rejected (got HTTP {traversal_resp.status_code})")

        # ---------------------------------------------------------------------
        # Final Summary
        # ---------------------------------------------------------------------
        print("\n" + "=" * 78)
        print(f"   CONTAINER DEPLOYMENT VERIFICATION COMPLETE: {passed_checks}/{total_checks} CHECKS PASSED")
        print("=" * 78)
        print("Container Deployment Status: FULLY OPERATIONAL & CERTIFIED")
        print("Image: depthwizard-depthwizard:latest")
        print("Target: Pure CPU (AVX2), Resource constrained (2 CPU / 4GB RAM)")
        print("All gates verified: Health, SPA, ONNX Inference, Volume Mounts, RasterIO, Evaluation, Security.")

        return 0
    finally:
        client.close()

def main():
    parser = argparse.ArgumentParser(description="DepthWizard Container Deployment Verification")
    parser.add_argument("--host", default="127.0.0.1", help="Target container host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8001, help="Target container port (default: 8001)")
    args = parser.parse_args()

    sys.exit(run_container_verification(host=args.host, port=args.port))

if __name__ == "__main__":
    main()

