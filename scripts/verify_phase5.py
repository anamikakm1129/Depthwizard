import sys
import json
from pathlib import Path
from starlette.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.main import app

def verify_phase5():
    print("==========================================================")
    print("   DEPTHWIZARD PHASE 5 FASTAPI BACKEND API VERIFICATION  ")
    print("==========================================================")

    client = TestClient(app)
    data_dir = PROJECT_ROOT / "tests" / "data"

    # 1. Health Endpoint Check
    print("\n[CHECK 1] Testing GET /api/v1/health...")
    resp1 = client.get("/api/v1/health")
    assert resp1.status_code == 200, f"Expected 200, got {resp1.status_code}"
    h_data = resp1.json()
    print(f" - Health: {h_data}")
    assert h_data["status"] == "ok"
    assert h_data["model_loaded"] is True
    assert h_data["execution_provider"] == "CPUExecutionProvider"
    print(" -> Health check PASSED.")

    # 2. Model Info Endpoint Check
    print("\n[CHECK 2] Testing GET /api/v1/model/info...")
    resp2 = client.get("/api/v1/model/info")
    assert resp2.status_code == 200
    info_data = resp2.json()
    print(f" - Model Info: {info_data['model_name']} ({info_data['license']})")
    assert info_data["input_resolution"] == 518
    assert info_data["license"] == "Apache-2.0"
    print(" -> Model info check PASSED.")

    # 3. Real Georeferenced GeoTIFF Processing (Uncalibrated Fallback)
    print("\n[CHECK 3] Testing POST /api/v1/process with Real GeoTIFF (Uncalibrated)...")
    geotiff_path = data_dir / "sample_geotiff.tif"
    assert geotiff_path.exists()

    with open(geotiff_path, "rb") as f:
        resp3 = client.post(
            "/api/v1/process",
            files={"file": ("sample_geotiff.tif", f, "image/tiff")}
        )

    assert resp3.status_code == 200, f"Process failed: {resp3.text}"
    p_data = resp3.json()
    print(f" - Job ID: {p_data['job_id']}")
    print(f" - Status: {p_data['status']}")
    print(f" - Output Depth Type: {p_data['depth_type']} (Strictly unitless disparity)")
    print(f" - Input Spatial CRS: {p_data['input_metadata']['crs']}")
    print(f" - Dimensions: {p_data['input_metadata']['original_width']} x {p_data['input_metadata']['original_height']}")
    print(f" - Timing Breakdown:")
    for k, v in p_data["timings"].items():
        print(f"   * {k}: {v:.4f} s")
    print(f" - GeoTIFF Download URL: {p_data['geotiff_download_url']}")
    print(f" - Preview PNG Download URL: {p_data['preview_png_download_url']}")

    assert p_data["depth_type"] == "RELATIVE_DEPTH"
    assert p_data["calibration"]["is_metric"] is False
    assert p_data["input_metadata"]["has_georeference"] is True
    assert p_data["input_metadata"]["crs"] == "EPSG:32618"
    print(" -> Real GeoTIFF processing check PASSED.")

    # 4. Download Exported GeoTIFF
    print("\n[CHECK 4] Testing GET /api/v1/download/{filename}...")
    download_url = p_data["geotiff_download_url"]
    resp4 = client.get(download_url)
    assert resp4.status_code == 200
    assert resp4.headers["content-type"] == "image/tiff"
    assert len(resp4.content) > 100000  # At least 100 KB
    print(f" - Successfully retrieved exported GeoTIFF ({len(resp4.content) / 1024:.1f} KB)")
    print(" -> File download check PASSED.")

    # 5. Real Processing with GCP Calibration
    print("\n[CHECK 5] Testing POST /api/v1/process with Surveyed GCP Calibration...")
    import rasterio
    geotiff_url = p_data["geotiff_download_url"]
    filename = Path(geotiff_url).name
    with rasterio.open(f"backend/outputs/{filename}") as ds:
        d1 = float(ds.read(1)[0, 0])
        d2 = float(ds.read(1)[359, 395])
        d3 = float(ds.read(1)[717, 790])

    test_gcps = [
        {"x_pixel": 0.0, "y_pixel": 0.0, "z_elevation": 20.0 * d1 + 100.0, "point_id": "GCP1"},
        {"x_pixel": 395.0, "y_pixel": 359.0, "z_elevation": 20.0 * d2 + 100.0, "point_id": "GCP2"},
        {"x_pixel": 790.0, "y_pixel": 717.0, "z_elevation": 20.0 * d3 + 100.0, "point_id": "GCP3"}
    ]
    with open(geotiff_path, "rb") as f:
        resp5 = client.post(
            "/api/v1/process",
            files={"file": ("sample_geotiff.tif", f, "image/tiff")},
            data={"gcps_json": json.dumps(test_gcps)}
        )
    assert resp5.status_code == 200
    p5_data = resp5.json()
    print(f" - Calibrated Depth Type: {p5_data['depth_type']}")
    print(f" - Is Metric: {p5_data['calibration']['is_metric']}")
    print(f" - Solved Scale: {p5_data['calibration']['scale_factor']:.4f}")
    print(f" - Solved Shift: {p5_data['calibration']['shift_offset']:.4f}")
    print(f" - Validation RMSE: {p5_data['calibration']['metrics']['rmse']:.4f} m")
    assert p5_data["depth_type"] == "CALIBRATED_DSM"
    assert p5_data["calibration"]["is_metric"] is True
    print(" -> Surveyed GCP calibration check PASSED.")

    # 6. Rejection of Unsupported File Format
    print("\n[CHECK 6] Testing Rejection of Unsupported Extension (.txt)...")
    resp6 = client.post(
        "/api/v1/process",
        files={"file": ("test.txt", b"dummy content", "text/plain")}
    )
    assert resp6.status_code == 400
    print(f" - Rejected as expected: {resp6.json()['detail']}")
    print(" -> Unsupported format rejection check PASSED.")

    # 7. Rejection of Corrupted File (Magic Bytes Mismatch)
    print("\n[CHECK 7] Testing Rejection of Corrupted File (Magic Bytes Mismatch)...")
    resp7 = client.post(
        "/api/v1/process",
        files={"file": ("fake_image.png", b"This is not a real PNG file header", "image/png")}
    )
    assert resp7.status_code == 400
    print(f" - Rejected as expected: {resp7.json()['detail']}")
    print(" -> Corrupted magic bytes check PASSED.")

    # 8. Path Traversal Prevention on Download Endpoint
    print("\n[CHECK 8] Testing Path Traversal Defense...")
    resp8 = client.get("/api/v1/download/../../passwords.txt")
    assert resp8.status_code == 404
    print(" -> Path traversal defense check PASSED.")

    print("\n==========================================================")
    print("   ALL PHASE 5 VERIFICATIONS COMPLETED WITH SUCCESS       ")
    print("==========================================================")

if __name__ == "__main__":
    verify_phase5()
