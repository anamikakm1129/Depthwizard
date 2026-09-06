import pytest
import json
from pathlib import Path
from starlette.testclient import TestClient

from backend.app.main import app

client = TestClient(app)
DATA_DIR = Path("tests/data")

def test_api_root():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "DepthWizard" in data["project"]

def test_api_health():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["model_loaded"] is True
    assert data["execution_provider"] == "CPUExecutionProvider"

def test_api_model_info():
    response = client.get("/api/v1/model/info")
    assert response.status_code == 200
    data = response.json()
    assert data["input_resolution"] == 518
    assert data["license"] == "Apache-2.0"

def test_api_process_geotiff_uncalibrated():
    path = DATA_DIR / "sample_geotiff.tif"
    assert path.exists()
    
    with open(path, "rb") as f:
        response = client.post(
            "/api/v1/process",
            files={"file": ("sample_geotiff.tif", f, "image/tiff")}
        )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["depth_type"] == "RELATIVE_DSM"
    assert data["units"] == "unitless_disparity"
    assert data["is_metric"] is False
    assert data["calibration"]["is_metric"] is False
    assert data["input_metadata"]["has_georeference"] is True
    assert data["input_metadata"]["crs"] == "EPSG:32618"
    assert data["input_metadata"]["resolution"] is not None
    assert "relief_metrics" in data
    assert data["relief_metrics"]["valid_pixel_count"] > 0
    assert "relative_dsm_seconds" in data["timings"]
    assert "inference_seconds" in data["timings"]
    assert "mesh_download_url" in data
    assert data["mesh_download_url"] is not None
    
    # Download and verify OBJ mesh
    mesh_resp = client.get(data["mesh_download_url"])
    assert mesh_resp.status_code == 200
    assert b"# DepthWizard 3D Terrain Mesh" in mesh_resp.content

def test_api_process_with_gcps():
    path = DATA_DIR / "sample_geotiff.tif"
    
    # 1. First run uncalibrated to inspect real predicted disparity at 3 points
    with open(path, "rb") as f:
        resp_uncalib = client.post(
            "/api/v1/process",
            files={"file": ("sample_geotiff.tif", f, "image/tiff")}
        )
    assert resp_uncalib.status_code == 200
    
    # Read the exported relative depth geotiff to get exact real predicted values
    import rasterio
    geotiff_url = resp_uncalib.json()["geotiff_download_url"]
    filename = Path(geotiff_url).name
    with rasterio.open(f"backend/outputs/{filename}") as ds:
        d1 = float(ds.read(1)[0, 0])
        d2 = float(ds.read(1)[359, 395])
        d3 = float(ds.read(1)[717, 790])

    # Construct consistent GCP elevations: Z = 25.0 * d + 100.0
    consistent_gcps = [
        {"x_pixel": 0.0, "y_pixel": 0.0, "z_elevation": 25.0 * d1 + 100.0, "point_id": "GCP_1"},
        {"x_pixel": 395.0, "y_pixel": 359.0, "z_elevation": 25.0 * d2 + 100.0, "point_id": "GCP_2"},
        {"x_pixel": 790.0, "y_pixel": 717.0, "z_elevation": 25.0 * d3 + 100.0, "point_id": "GCP_3"}
    ]
    with open(path, "rb") as f:
        resp_valid = client.post(
            "/api/v1/process",
            files={"file": ("sample_geotiff.tif", f, "image/tiff")},
            data={"gcps_json": json.dumps(consistent_gcps)}
        )
    assert resp_valid.status_code == 200
    data_valid = resp_valid.json()
    assert data_valid["depth_type"] == "CALIBRATED_DSM"
    assert data_valid["units"] == "meters"
    assert data_valid["is_metric"] is True
    assert data_valid["calibration"]["is_metric"] is True
    assert data_valid["calibration"]["scale_factor"] is not None

    # 2. Test rejection on chaotic/noisy GCPs
    noisy_gcps = [
        {"x_pixel": 0.0, "y_pixel": 0.0, "z_elevation": 10.0},
        {"x_pixel": 395.0, "y_pixel": 359.0, "z_elevation": 800.0},
        {"x_pixel": 790.0, "y_pixel": 717.0, "z_elevation": 10.0}
    ]
    with open(path, "rb") as f:
        resp_noisy = client.post(
            "/api/v1/process",
            files={"file": ("sample_geotiff.tif", f, "image/tiff")},
            data={"gcps_json": json.dumps(noisy_gcps)}
        )
    assert resp_noisy.status_code == 200
    data_noisy = resp_noisy.json()
    assert data_noisy["depth_type"] == "RELATIVE_DSM"
    assert data_noisy["units"] == "unitless_disparity"
    assert data_noisy["is_metric"] is False
    assert data_noisy["calibration"]["is_metric"] is False
    assert data_noisy["calibration"]["rejection_reason"] is not None

def test_api_rejects_unsupported_extension():
    response = client.post(
        "/api/v1/process",
        files={"file": ("malicious.exe", b"fake binary", "application/octet-stream")}
    )
    assert response.status_code == 400
    assert "Unsupported format" in response.json()["detail"]

def test_api_rejects_corrupted_magic_bytes():
    response = client.post(
        "/api/v1/process",
        files={"file": ("fake.png", b"invalid header string content", "image/png")}
    )
    assert response.status_code == 400
    assert "magic bytes" in response.json()["detail"]

def test_api_download_path_traversal():
    response = client.get("/api/v1/download/../../passwords.txt")
    assert response.status_code == 404

def test_api_frontend_spa_serving():
    # Test that /app serves the SPA HTML with DepthWizard in title
    response = client.get("/app")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "DepthWizard" in response.text

    # Test /viewer alias
    response_viewer = client.get("/viewer")
    assert response_viewer.status_code == 200
    assert "DepthWizard" in response_viewer.text

    # Test favicon serving
    response_fav = client.get("/favicon.svg")
    assert response_fav.status_code == 200

def test_api_process_aerial_geotiff():
    path = DATA_DIR / "sample_aerial.tif"
    assert path.exists()

    with open(path, "rb") as f:
        response = client.post(
            "/api/v1/process",
            files={"file": ("sample_aerial.tif", f, "image/tiff")}
        )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["depth_type"] == "RELATIVE_DSM"
    assert data["units"] == "unitless_disparity"
    assert data["is_metric"] is False
    assert data["input_metadata"]["has_georeference"] is True
    assert data["input_metadata"]["crs"] == "EPSG:32621"
    assert data["mesh_download_url"] is not None

    # Verify mesh download
    mesh_resp = client.get(data["mesh_download_url"])
    assert mesh_resp.status_code == 200
    assert b"# DepthWizard 3D Terrain Mesh" in mesh_resp.content

def test_api_process_standard_png_non_georeferenced():
    # Test standard non-georeferenced image upload
    import io
    from PIL import Image

    # Create 64x64 non-georeferenced PNG
    img = Image.new("RGB", (64, 64), color=(120, 150, 180))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    response = client.post(
        "/api/v1/process",
        files={"file": ("test_optical.png", buf, "image/png")}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["depth_type"] == "RELATIVE_DSM"
    assert data["units"] == "unitless_disparity"
    assert data["is_metric"] is False
    assert data["input_metadata"]["has_georeference"] is False
    assert data["input_metadata"]["crs"] is None
    assert data["mesh_download_url"] is not None

def test_api_process_with_gcps_geo_coordinates():
    path = DATA_DIR / "sample_geotiff.tif"
    assert path.exists()

    # Run uncalibrated first to read true relative values
    with open(path, "rb") as f:
        resp_uncalib = client.post(
            "/api/v1/process",
            files={"file": ("sample_geotiff.tif", f, "image/tiff")}
        )
    assert resp_uncalib.status_code == 200
    geotiff_url = resp_uncalib.json()["geotiff_download_url"]
    filename = Path(geotiff_url).name

    import rasterio
    with rasterio.open(f"backend/outputs/{filename}") as ds:
        d1 = float(ds.read(1)[10, 10])
        d2 = float(ds.read(1)[200, 200])
        d3 = float(ds.read(1)[400, 400])
        transform = ds.transform
        x_geo1, y_geo1 = rasterio.transform.xy(transform, 10, 10)
        x_geo2, y_geo2 = rasterio.transform.xy(transform, 200, 200)
        x_geo3, y_geo3 = rasterio.transform.xy(transform, 400, 400)

    # Provide GCPs with both pixel coordinates and geo coordinates
    geo_gcps = [
        {"x_pixel": 10.0, "y_pixel": 10.0, "x_geo": x_geo1, "y_geo": y_geo1, "z_elevation": 20.0 * d1 + 50.0, "point_id": "GEO_1"},
        {"x_pixel": 200.0, "y_pixel": 200.0, "x_geo": x_geo2, "y_geo": y_geo2, "z_elevation": 20.0 * d2 + 50.0, "point_id": "GEO_2"},
        {"x_pixel": 400.0, "y_pixel": 400.0, "x_geo": x_geo3, "y_geo": y_geo3, "z_elevation": 20.0 * d3 + 50.0, "point_id": "GEO_3"}
    ]

    with open(path, "rb") as f:
        resp_calib = client.post(
            "/api/v1/process",
            files={"file": ("sample_geotiff.tif", f, "image/tiff")},
            data={"gcps_json": json.dumps(geo_gcps)}
        )
    assert resp_calib.status_code == 200
    data_calib = resp_calib.json()
    assert data_calib["depth_type"] == "CALIBRATED_DSM"
    assert data_calib["units"] == "meters"
    assert data_calib["is_metric"] is True
    assert data_calib["calibration"]["scale_factor"] is not None
    assert data_calib["calibration"]["metrics"]["rmse"] < 5.0


