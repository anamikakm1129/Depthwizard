"""
Unit and Integration Tests for Scientific Evaluation Engine
===========================================================
Tests metric computer, spatial error map generator, SceneEvaluator,
and FastAPI /api/v1/evaluate endpoint.
Strictly adheres to .agents/rules/depthwizard-development.md (No Fake AI).
"""

import io
import json
import tempfile
from pathlib import Path
import numpy as np
import rasterio
from starlette.testclient import TestClient

from backend.app.main import app
from backend.app.evaluation.metrics import ElevationMetricComputer
from backend.app.evaluation.error_map import ErrorMapGenerator
from backend.app.evaluation.evaluator import SceneEvaluator

client = TestClient(app)
DATA_DIR = Path("tests/data")

def test_metric_computer_perfect_match():
    """Verify that identical arrays yield zero error and 100% threshold accuracy."""
    grid = np.array([[10.0, 20.0, 30.0], [40.0, 50.0, 60.0]], dtype=np.float32)
    metrics = ElevationMetricComputer.compute(pred=grid, reference=grid)

    assert metrics.mae == 0.0
    assert metrics.rmse == 0.0
    assert metrics.bias == 0.0
    assert metrics.abs_rel == 0.0
    assert metrics.sq_rel == 0.0
    assert metrics.pearson_r == 1.0
    assert metrics.r_squared == 1.0
    assert metrics.delta_1 == 1.0
    assert metrics.delta_2 == 1.0
    assert metrics.delta_3 == 1.0
    assert metrics.valid_points_count == 6
    assert metrics.coverage_ratio == 1.0

def test_metric_computer_known_residuals():
    """Verify exact formula values for known linear offsets."""
    ref = np.array([10.0, 20.0, 30.0, 40.0], dtype=np.float32)
    pred = ref + 2.0  # Constant +2.0m bias

    metrics = ElevationMetricComputer.compute(pred=pred, reference=ref)
    assert np.isclose(metrics.mae, 2.0)
    assert np.isclose(metrics.rmse, 2.0)
    assert np.isclose(metrics.bias, 2.0)
    assert np.isclose(metrics.pearson_r, 1.0)
    # R^2 with constant offset
    ss_tot = np.sum((ref - np.mean(ref)) ** 2)
    ss_res = 4.0 * (2.0 ** 2)
    expected_r2 = 1.0 - (ss_res / ss_tot)
    assert np.isclose(metrics.r_squared, expected_r2)

def test_metric_computer_nodata_masking():
    """Verify that nodata and non-finite values are strictly excluded from calculation."""
    ref = np.array([[10.0, 20.0], [30.0, -9999.0]], dtype=np.float32)
    pred = np.array([[12.0, 22.0], [32.0, 50.0]], dtype=np.float32)

    metrics = ElevationMetricComputer.compute(pred=pred, reference=ref, nodata=-9999.0)
    assert metrics.valid_points_count == 3
    assert metrics.total_points_count == 4
    assert metrics.coverage_ratio == 0.75
    assert np.isclose(metrics.mae, 2.0)

def test_error_map_generator_diverging_palette():
    """Verify residual difference calculation and diverging PNG generation."""
    h, w = 20, 20
    pred = np.linspace(0.0, 100.0, h * w).reshape(h, w).astype(np.float32)
    ref = np.full((h, w), 50.0, dtype=np.float32)

    with tempfile.TemporaryDirectory() as tmpdir:
        out_png = Path(tmpdir) / "error_map.png"
        residuals, written_path = ErrorMapGenerator.generate_error_map(
            pred=pred,
            reference=ref,
            output_filepath=out_png
        )

        assert written_path.exists()
        assert written_path.stat().st_size > 500
        assert residuals.shape == (h, w)
        assert np.isclose(residuals[0, 0], -50.0) # Under-estimation (Blue)
        assert np.isclose(residuals[-1, -1], 50.0) # Over-estimation (Red)

def test_scene_evaluator_resampling():
    """Verify that SceneEvaluator handles dimension mismatches gracefully with warnings."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        pred_path = tmp_path / "pred.tif"
        ref_path = tmp_path / "ref.tif"

        # Create 100x100 pred
        meta = {
            "driver": "GTiff",
            "height": 100,
            "width": 100,
            "count": 1,
            "dtype": "float32"
        }
        with rasterio.open(pred_path, "w", **meta) as dst:
            dst.write(np.full((1, 100, 100), 50.0, dtype=np.float32))

        # Create 50x50 reference
        meta_ref = dict(meta, height=50, width=50)
        with rasterio.open(ref_path, "w", **meta_ref) as dst:
            dst.write(np.full((1, 50, 50), 50.0, dtype=np.float32))

        resp = SceneEvaluator.evaluate_rasters(
            predicted_raster_path=pred_path,
            reference_raster_path=ref_path,
            job_id="test_job",
            is_metric=True,
            depth_type="CALIBRATED_DSM"
        )

        assert resp.metrics.mae == 0.0
        assert any("resampled" in w for w in resp.warnings)

def test_evaluation_api_integration():
    """End-to-end test of /api/v1/evaluate with real imagery."""
    sample_path = DATA_DIR / "sample_geotiff.tif"
    assert sample_path.exists()

    # 1. Process image to get valid job_id and predicted output raster
    with open(sample_path, "rb") as f:
        proc_resp = client.post(
            "/api/v1/process",
            files={"file": ("sample_geotiff.tif", f, "image/tiff")}
        )
    assert proc_resp.status_code == 200
    job_id = proc_resp.json()["job_id"]

    # 2. Evaluate using sample_geotiff.tif as reference
    with open(sample_path, "rb") as f:
        eval_resp = client.post(
            "/api/v1/evaluate",
            data={"job_id": job_id, "is_metric": False},
            files={"reference_file": ("sample_geotiff.tif", f, "image/tiff")}
        )
    assert eval_resp.status_code == 200
    eval_data = eval_resp.json()

    assert eval_data["target_job_id"] == job_id
    assert "metrics" in eval_data
    assert eval_data["metrics"]["valid_points_count"] > 100_000
    assert "error_map_download_url" in eval_data

    # 3. Verify Error Map download
    err_url = eval_data["error_map_download_url"]
    err_resp = client.get(err_url)
    assert err_resp.status_code == 200
    assert err_resp.headers["content-type"] == "image/png"
    assert len(err_resp.content) > 10_000

