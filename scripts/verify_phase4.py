import sys
from pathlib import Path
import numpy as np

# Ensure project root in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.geospatial.calibration import MetricCalibrator
from backend.app.geospatial.calibration_schemas import (
    CalibrationMode,
    CalibrationMethod,
    CalibrationSourceType,
    GroundControlPoint
)
from backend.app.geospatial.raster_io import RasterIO
from backend.app.geospatial.schemas import RasterExportConfig

def verify_phase4():
    print("==========================================================")
    print("   DEPTHWIZARD PHASE 4 CALIBRATION & REASONING HARNESS    ")
    print("==========================================================")

    # 1. Uncalibrated Safe Fallback
    print("\n[CHECK 1] Uncalibrated Relative Mode (Safe Fallback)...")
    raw_depth = np.linspace(0.0, 1.0, 10000, dtype=np.float32).reshape((100, 100))
    res1 = MetricCalibrator.fallback_to_relative(raw_depth)
    assert res1.mode == CalibrationMode.UNCALIBRATED_RELATIVE
    assert res1.is_metric is False
    assert res1.depth_type == "RELATIVE_DEPTH"
    assert res1.metrics is None
    print(f" - Mode: {res1.mode.value}, is_metric: {res1.is_metric}, depth_type: {res1.depth_type}")
    print(f" - Fallback Reason: {res1.rejection_reason}")
    print(" -> Uncalibrated fallback check PASSED.")

    # 2. Insufficient GCP Rejection
    print("\n[CHECK 2] Insufficient GCP Handling (< 3 points)...")
    sparse_gcps = [GroundControlPoint(10.0, 10.0, 150.0, "GCP1")]
    res2 = MetricCalibrator.calibrate_with_gcps(raw_depth, sparse_gcps)
    assert res2.is_metric is False
    assert res2.mode == CalibrationMode.UNCALIBRATED_RELATIVE
    assert "Insufficient GCPs" in res2.rejection_reason
    print(f" - Successfully caught insufficient GCPs: {res2.rejection_reason}")
    print(" -> Insufficient GCP rejection check PASSED.")

    # 3. Mathematical Calibration Precision (3 Valid Points)
    print("\n[CHECK 3] Mathematical Scale & Shift Solver Precision...")
    # Known relation: Z = 45.0 * d + 210.0
    known_scale = 45.0
    known_shift = 210.0
    test_gcps = [
        GroundControlPoint(0.0, 0.0, float(known_scale * raw_depth[0, 0] + known_shift), "P1"),
        GroundControlPoint(50.0, 50.0, float(known_scale * raw_depth[50, 50] + known_shift), "P2"),
        GroundControlPoint(99.0, 99.0, float(known_scale * raw_depth[99, 99] + known_shift), "P3")
    ]
    res3 = MetricCalibrator.calibrate_with_gcps(raw_depth, test_gcps, max_rmse_threshold=15.0)
    assert res3.is_metric is True
    assert res3.mode == CalibrationMode.VALIDATED_METRIC
    assert res3.depth_type == "CALIBRATED_DSM"
    assert np.isclose(res3.scale_factor, known_scale, atol=1e-3)
    assert np.isclose(res3.shift_offset, known_shift, atol=1e-3)
    assert res3.metrics.rmse < 1e-3
    assert np.isclose(res3.metrics.r_squared, 1.0, atol=1e-4)
    print(f" - Solved Scale: {res3.scale_factor:.4f} (True: {known_scale})")
    print(f" - Solved Shift: {res3.shift_offset:.4f} (True: {known_shift})")
    print(f" - Validation: RMSE={res3.metrics.rmse:.6f}m, MAE={res3.metrics.mae:.6f}m, R2={res3.metrics.r_squared:.4f}")
    print(" -> Mathematical solver precision check PASSED.")

    # 4. Gating Check: Rejection of Noisy/Uncorrelated Elevation Data
    print("\n[CHECK 4] Quality Gating: Rejection of Low-Correlation Reference Data...")
    noisy_gcps = [
        GroundControlPoint(0.0, 0.0, 100.0, "N1"),
        GroundControlPoint(50.0, 50.0, 800.0, "N2"),  # Huge non-physical jump
        GroundControlPoint(99.0, 99.0, 50.0, "N3")
    ]
    res4 = MetricCalibrator.calibrate_with_gcps(raw_depth, noisy_gcps, max_rmse_threshold=15.0)
    assert res4.is_metric is False
    assert res4.mode == CalibrationMode.CANDIDATE_METRIC
    assert res4.rejection_reason is not None
    print(f" - Quality gate successfully rejected noisy reference: {res4.rejection_reason}")
    print(f" - Residual RMSE: {res4.metrics.rmse:.2f}m (Threshold: 15.0m)")
    print(" -> Metric quality gating check PASSED.")

    # 5. GAMUS / nDSM Domain Semantic Warnings
    print("\n[CHECK 5] GAMUS / nDSM Domain Semantic Warnings...")
    # Simulate an nDSM reference
    ndsm_ref = 30.0 * raw_depth + 2.0
    res5 = MetricCalibrator.calibrate_with_reference_raster(
        depth_map=raw_depth,
        reference_array=ndsm_ref,
        source_type=CalibrationSourceType.NDSM_GAMUS,
        source_identifier="simulated_gamus_tile",
        max_rmse_threshold=15.0
    )
    assert res5.is_metric is True
    assert res5.depth_type == "APPROX_METRIC_HEIGHT"  # NOT absolute DSM!
    assert any("DOMAIN WARNING: Reference dataset is GAMUS / nDSM" in w for w in res5.warnings)
    print(f" - Output Depth Type: {res5.depth_type} (Strictly nDSM above-ground height)")
    print(f" - Documented Warning: {res5.warnings[0]}")
    print(" -> GAMUS / nDSM domain semantic check PASSED.")

    # 6. Export of Validated Calibrated GeoTIFF
    print("\n[CHECK 6] GeoTIFF Export of Validated Calibrated DSM...")
    data_dir = PROJECT_ROOT / "tests" / "data"
    output_dir = PROJECT_ROOT / "backend" / "outputs"
    source_meta = RasterIO.extract_metadata(data_dir / "sample_geotiff.tif")
    
    # Scale array to spatial dimensions of sample GeoTIFF
    geo_depth = np.linspace(0.0, 1.0, source_meta.width * source_meta.height, dtype=np.float32).reshape((source_meta.height, source_meta.width))
    calib_res = MetricCalibrator.calibrate_with_gcps(
        geo_depth,
        [
            GroundControlPoint(0, 0, 100.0),
            GroundControlPoint(source_meta.width // 2, source_meta.height // 2, 150.0),
            GroundControlPoint(source_meta.width - 1, source_meta.height - 1, 200.0)
        ]
    )
    assert calib_res.is_metric is True

    export_path = output_dir / "exported_calibrated_dsm.tif"
    cfg = RasterExportConfig(target_path=export_path)
    export_out = RasterIO.export_depth_to_geotiff(
        depth_map=calib_res.calibrated_array,
        source_metadata=source_meta,
        config=cfg,
        depth_type=calib_res.depth_type,
        is_calibrated=True
    )
    assert export_out.validation.is_valid is True
    assert export_out.validation.crs_matches_source is True
    print(f" - Calibrated GeoTIFF written to: {export_out.file_path}")
    print(f" - Preserved CRS: {export_out.validation.crs_matches_source}")
    print(f" - GeoTIFF Units: meters ({calib_res.depth_type})")
    print(" -> Calibrated GeoTIFF export check PASSED.")

    print("\n==========================================================")
    print("   ALL PHASE 4 VERIFICATIONS COMPLETED WITH SUCCESS       ")
    print("==========================================================")

if __name__ == "__main__":
    verify_phase4()
