import pytest
from pathlib import Path
import numpy as np

from backend.app.geospatial.calibration import MetricCalibrator
from backend.app.geospatial.calibration_schemas import (
    CalibrationMode,
    CalibrationMethod,
    CalibrationSourceType,
    GroundControlPoint
)
from backend.app.geospatial.raster_io import RasterIO
from backend.app.geospatial.schemas import RasterExportConfig

DATA_DIR = Path("tests/data")
OUTPUT_DIR = Path("backend/outputs")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def test_calibration_fallback_to_relative():
    depth_map = np.random.uniform(0.0, 1.0, (100, 100)).astype(np.float32)
    res = MetricCalibrator.fallback_to_relative(depth_map, reason="No reference")

    assert res.mode == CalibrationMode.UNCALIBRATED_RELATIVE
    assert res.method == CalibrationMethod.NONE
    assert res.is_metric is False
    assert res.depth_type == "RELATIVE_DEPTH"
    assert res.metrics is None
    assert res.scale_factor is None
    assert np.array_equal(res.calibrated_array, depth_map)

def test_calibration_insufficient_gcps():
    depth_map = np.linspace(0.0, 1.0, 10000, dtype=np.float32).reshape((100, 100))
    
    # 0 GCPs
    res0 = MetricCalibrator.calibrate_with_gcps(depth_map, [])
    assert res0.is_metric is False
    assert "Insufficient GCPs" in res0.rejection_reason

    # 2 GCPs
    res2 = MetricCalibrator.calibrate_with_gcps(
        depth_map,
        [GroundControlPoint(10, 10, 100.0), GroundControlPoint(20, 20, 120.0)]
    )
    assert res2.is_metric is False
    assert "Insufficient GCPs" in res2.rejection_reason

def test_calibration_out_of_bounds_gcps():
    depth_map = np.zeros((50, 50), dtype=np.float32)
    out_gcps = [
        GroundControlPoint(10, 10, 100.0),
        GroundControlPoint(200, 200, 150.0),  # Out of bounds
        GroundControlPoint(500, 500, 200.0)   # Out of bounds
    ]
    res = MetricCalibrator.calibrate_with_gcps(depth_map, out_gcps)
    assert res.is_metric is False
    assert "Only 1 GCPs fall within raster boundaries" in res.rejection_reason

def test_calibration_least_squares_numerical_precision():
    depth_map = np.linspace(0.0, 1.0, 10000, dtype=np.float32).reshape((100, 100))
    true_scale = 32.5
    true_shift = 145.0
    
    gcps = [
        GroundControlPoint(0, 0, float(true_scale * depth_map[0, 0] + true_shift)),
        GroundControlPoint(50, 50, float(true_scale * depth_map[50, 50] + true_shift)),
        GroundControlPoint(99, 99, float(true_scale * depth_map[99, 99] + true_shift)),
        GroundControlPoint(25, 75, float(true_scale * depth_map[75, 25] + true_shift))
    ]
    res = MetricCalibrator.calibrate_with_gcps(depth_map, gcps, max_rmse_threshold=10.0)
    assert res.is_metric is True
    assert res.mode == CalibrationMode.VALIDATED_METRIC
    assert res.depth_type == "CALIBRATED_DSM"
    assert np.isclose(res.scale_factor, true_scale, atol=1e-4)
    assert np.isclose(res.shift_offset, true_shift, atol=1e-4)
    assert res.metrics.rmse < 1e-4
    assert res.metrics.mae < 1e-4
    assert np.isclose(res.metrics.r_squared, 1.0, atol=1e-4)

def test_calibration_rejection_on_excessive_rmse():
    depth_map = np.linspace(0.0, 1.0, 10000, dtype=np.float32).reshape((100, 100))
    # Inconsistent/chaotic reference elevation
    gcps = [
        GroundControlPoint(0, 0, 100.0),
        GroundControlPoint(50, 50, 900.0),
        GroundControlPoint(99, 99, 50.0)
    ]
    res = MetricCalibrator.calibrate_with_gcps(depth_map, gcps, max_rmse_threshold=10.0)
    assert res.is_metric is False
    assert res.mode == CalibrationMode.CANDIDATE_METRIC
    assert res.rejection_reason is not None
    assert "exceeds threshold" in res.rejection_reason

def test_calibration_gamus_ndsm_domain_warning():
    depth_map = np.linspace(0.0, 1.0, 10000, dtype=np.float32).reshape((100, 100))
    ndsm_ref = (15.0 * depth_map + 1.0).astype(np.float32)

    res = MetricCalibrator.calibrate_with_reference_raster(
        depth_map=depth_map,
        reference_array=ndsm_ref,
        source_type=CalibrationSourceType.NDSM_GAMUS,
        source_identifier="gamus_potsdam_tile_01"
    )

    assert res.is_metric is True
    assert res.depth_type == "CALIBRATED_DSM"
    assert any("GAMUS / nDSM" in w for w in res.warnings)

def test_calibrated_dsm_geotiff_export_integration():
    source_path = DATA_DIR / "sample_geotiff.tif"
    source_meta = RasterIO.extract_metadata(source_path)

    depth_map = np.linspace(0.0, 1.0, source_meta.width * source_meta.height, dtype=np.float32).reshape((source_meta.height, source_meta.width))
    gcps = [
        GroundControlPoint(0, 0, 120.0),
        GroundControlPoint(source_meta.width // 2, source_meta.height // 2, 170.0),
        GroundControlPoint(source_meta.width - 1, source_meta.height - 1, 220.0)
    ]
    calib = MetricCalibrator.calibrate_with_gcps(depth_map, gcps)
    assert calib.is_metric is True

    export_path = OUTPUT_DIR / "test_pytest_calibrated.tif"
    config = RasterExportConfig(target_path=export_path)

    res = RasterIO.export_depth_to_geotiff(
        depth_map=calib.calibrated_array,
        source_metadata=source_meta,
        config=config,
        depth_type=calib.depth_type,
        is_calibrated=True
    )
    assert res.validation.is_valid is True
    assert res.validation.crs_matches_source is True
    assert res.validation.transform_matches_source is True
