import pytest
from pathlib import Path
import numpy as np
import rasterio

from backend.app.geospatial.schemas import GeoMetadata, RasterExportConfig
from backend.app.geospatial.raster_io import RasterIO
from backend.app.geospatial.calibration import MetricCalibrator
from backend.app.geospatial.calibration_schemas import (
    CalibrationMode,
    CalibrationMethod,
    CalibrationSourceType,
    GroundControlPoint,
    MetricElevationProduct
)
from backend.app.geospatial.relative_dsm import (
    RelativeSurfaceConvention,
    RelativeRasterConfig,
    RelativeDSMProduct,
    RelativeDSMGenerator
)
from backend.app.inference.pipeline import DepthPipeline
from backend.app.config import settings

DATA_DIR = Path("tests/data")
OUTPUT_DIR = Path("backend/outputs")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def test_calibrate_relative_dsm_with_valid_gcps():
    """Verifies seamless calibration of a RelativeDSMProduct into a validated MetricElevationProduct."""
    source_path = DATA_DIR / "sample_geotiff.tif"
    metadata = RasterIO.extract_metadata(source_path)

    # Create synthetic relative depth array [0, 1]
    y, x = np.mgrid[0:metadata.height, 0:metadata.width]
    depth_array = ((x + y) / (metadata.width + metadata.height)).astype(np.float32)

    product = RelativeDSMGenerator.generate(depth_array, metadata)
    assert product.is_metric is False
    assert product.depth_type == "RELATIVE_DSM"

    # Known ground truth relationship: Z = 45.0 * d + 120.0
    true_scale = 45.0
    true_shift = 120.0
    gcps = [
        GroundControlPoint(x_pixel=10.0, y_pixel=10.0, z_elevation=float(true_scale * product.array[10, 10] + true_shift)),
        GroundControlPoint(x_pixel=100.0, y_pixel=100.0, z_elevation=float(true_scale * product.array[100, 100] + true_shift)),
        GroundControlPoint(x_pixel=200.0, y_pixel=300.0, z_elevation=float(true_scale * product.array[300, 200] + true_shift)),
        GroundControlPoint(x_pixel=400.0, y_pixel=500.0, z_elevation=float(true_scale * product.array[500, 400] + true_shift)),
    ]

    metric_product = product.calibrate(gcps=gcps)

    assert isinstance(metric_product, MetricElevationProduct)
    assert metric_product.is_metric is True
    assert metric_product.depth_type == "CALIBRATED_DSM"
    assert metric_product.units == "meters"
    assert metric_product.array.shape == (metadata.height, metadata.width)
    assert metric_product.source_relative_dsm is product

    # Calibration parameters verification
    assert np.isclose(metric_product.calibration.scale_factor, true_scale, atol=1e-3)
    assert np.isclose(metric_product.calibration.shift_offset, true_shift, atol=1e-3)
    assert metric_product.calibration.metrics.rmse < 1e-3
    assert np.isclose(metric_product.calibration.metrics.r_squared, 1.0, atol=1e-3)


def test_calibrate_relative_dsm_fallback_on_missing_or_insufficient_gcps():
    """Verifies that missing or insufficient GCPs safely maintain unitless relative representation."""
    metadata = GeoMetadata(width=100, height=100, count=1, dtype="float32", driver="GTiff", has_georeference=False)
    arr = np.linspace(0.0, 1.0, 10000, dtype=np.float32).reshape((100, 100))
    product = RelativeDSMGenerator.generate(arr, metadata)

    # 1. No GCPs provided
    fallback_none = product.calibrate()
    assert fallback_none.is_metric is False
    assert fallback_none.depth_type == "RELATIVE_DSM"
    assert fallback_none.units == "unitless_disparity"
    assert "No calibration reference" in fallback_none.calibration.rejection_reason

    # 2. Insufficient GCPs (< 3)
    gcps_few = [
        GroundControlPoint(x_pixel=10.0, y_pixel=10.0, z_elevation=100.0),
        GroundControlPoint(x_pixel=50.0, y_pixel=50.0, z_elevation=150.0),
    ]
    fallback_few = product.calibrate(gcps=gcps_few)
    assert fallback_few.is_metric is False
    assert fallback_few.depth_type == "RELATIVE_DSM"
    assert fallback_few.units == "unitless_disparity"
    assert "Insufficient GCPs" in fallback_few.calibration.rejection_reason


def test_calibrate_relative_dsm_strict_raise_on_failure():
    """Verifies strict_raise=True raises ValueError when calibration fails or reference is missing."""
    metadata = GeoMetadata(width=100, height=100, count=1, dtype="float32", driver="GTiff", has_georeference=False)
    arr = np.linspace(0.0, 1.0, 10000, dtype=np.float32).reshape((100, 100))
    product = RelativeDSMGenerator.generate(arr, metadata)

    with pytest.raises(ValueError, match="Calibration failed"):
        product.calibrate(gcps=[], strict_raise=True)


def test_calibrate_relative_dsm_geo_coordinates_projection():
    """Verifies that GCPs defined with map/geographic coordinates (x_geo, y_geo) are projected correctly."""
    source_path = DATA_DIR / "sample_geotiff.tif"
    metadata = RasterIO.extract_metadata(source_path)
    assert metadata.has_georeference is True

    # Use affine transform to construct true map coordinates from pixel locations
    t = metadata.transform
    # pixel (100, 100) -> map (x_geo, y_geo)
    x1_geo = t[0] * 100 + t[1] * 100 + t[2]
    y1_geo = t[3] * 100 + t[4] * 100 + t[5]

    # pixel (300, 200)
    x2_geo = t[0] * 300 + t[1] * 200 + t[2]
    y2_geo = t[3] * 300 + t[4] * 200 + t[5]

    # pixel (500, 400)
    x3_geo = t[0] * 500 + t[1] * 400 + t[2]
    y3_geo = t[3] * 500 + t[4] * 400 + t[5]

    # pixel (600, 500)
    x4_geo = t[0] * 600 + t[1] * 500 + t[2]
    y4_geo = t[3] * 600 + t[4] * 500 + t[5]

    y, x = np.mgrid[0:metadata.height, 0:metadata.width]
    depth_array = ((x + y) / (metadata.width + metadata.height)).astype(np.float32)
    product = RelativeDSMGenerator.generate(depth_array, metadata)

    true_scale = 20.0
    true_shift = 50.0

    geo_gcps = [
        GroundControlPoint(x_pixel=0.0, y_pixel=0.0, z_elevation=float(true_scale * product.array[100, 100] + true_shift), x_geo=x1_geo, y_geo=y1_geo),
        GroundControlPoint(x_pixel=0.0, y_pixel=0.0, z_elevation=float(true_scale * product.array[200, 300] + true_shift), x_geo=x2_geo, y_geo=y2_geo),
        GroundControlPoint(x_pixel=0.0, y_pixel=0.0, z_elevation=float(true_scale * product.array[400, 500] + true_shift), x_geo=x3_geo, y_geo=y3_geo),
        GroundControlPoint(x_pixel=0.0, y_pixel=0.0, z_elevation=float(true_scale * product.array[500, 600] + true_shift), x_geo=x4_geo, y_geo=y4_geo),
    ]

    metric_prod = product.calibrate(gcps=geo_gcps)
    assert metric_prod.is_metric is True
    assert metric_prod.depth_type == "CALIBRATED_DSM"
    assert np.isclose(metric_prod.calibration.scale_factor, true_scale, atol=1e-2)
    assert np.isclose(metric_prod.calibration.shift_offset, true_shift, atol=1e-2)


def test_calibrate_relative_dsm_rejection_on_poor_fit():
    """Scientific Integrity: Inconsistent reference data exceeding RMSE threshold is safely rejected."""
    metadata = GeoMetadata(width=100, height=100, count=1, dtype="float32", driver="GTiff", has_georeference=False)
    arr = np.linspace(0.0, 1.0, 10000, dtype=np.float32).reshape((100, 100))
    product = RelativeDSMGenerator.generate(arr, metadata)

    # Chaotic contradictory elevations
    chaotic_gcps = [
        GroundControlPoint(x_pixel=10.0, y_pixel=10.0, z_elevation=50.0),
        GroundControlPoint(x_pixel=50.0, y_pixel=50.0, z_elevation=5000.0),
        GroundControlPoint(x_pixel=90.0, y_pixel=90.0, z_elevation=20.0),
    ]

    rejected_prod = product.calibrate(gcps=chaotic_gcps, max_rmse_threshold=15.0)
    assert rejected_prod.is_metric is False
    assert rejected_prod.depth_type == "RELATIVE_DSM"
    assert rejected_prod.units == "unitless_disparity"
    assert "exceeds threshold" in rejected_prod.calibration.rejection_reason


def test_calibrate_relative_dsm_with_reference_raster_and_gamus_warning():
    """Verifies raster-to-raster calibration and ensures GAMUS nDSM sets domain warning."""
    metadata = GeoMetadata(width=100, height=100, count=1, dtype="float32", driver="GTiff", has_georeference=False)
    arr = np.linspace(0.0, 1.0, 10000, dtype=np.float32).reshape((100, 100))
    product = RelativeDSMGenerator.generate(arr, metadata)

    # 1. Standard reference DEM
    ref_dem = (25.0 * arr + 100.0).astype(np.float32)
    metric_dem = product.calibrate(
        reference_raster=ref_dem,
        source_type=CalibrationSourceType.REFERENCE_DEM,
        source_identifier="copernicus_glo_30"
    )
    assert metric_dem.is_metric is True
    assert metric_dem.depth_type == "CALIBRATED_DSM"
    assert metric_dem.units == "meters"

    # 2. GAMUS nDSM reference (above ground height)
    ref_gamus = (15.0 * arr + 2.0).astype(np.float32)
    metric_gamus = product.calibrate(
        reference_raster=ref_gamus,
        source_type=CalibrationSourceType.NDSM_GAMUS,
        source_identifier="gamus_ndsm_urban"
    )
    assert metric_gamus.is_metric is True
    assert metric_gamus.depth_type == "CALIBRATED_DSM"
    assert metric_gamus.units == "meters"
    assert any("DOMAIN WARNING: Reference dataset is GAMUS / nDSM" in w for w in metric_gamus.calibration.warnings)


def test_export_metric_elevation_geotiff():
    """Verifies GeoTIFF export of MetricElevationProduct writes calibration metadata tags and preserves CRS."""
    source_path = DATA_DIR / "sample_geotiff.tif"
    metadata = RasterIO.extract_metadata(source_path)

    y, x = np.mgrid[0:metadata.height, 0:metadata.width]
    depth_array = ((x + y) / (metadata.width + metadata.height)).astype(np.float32)
    product = RelativeDSMGenerator.generate(depth_array, metadata)

    true_scale = 30.0
    true_shift = 80.0
    gcps = [
        GroundControlPoint(x_pixel=10.0, y_pixel=10.0, z_elevation=float(true_scale * depth_array[10, 10] + true_shift)),
        GroundControlPoint(x_pixel=100.0, y_pixel=100.0, z_elevation=float(true_scale * depth_array[100, 100] + true_shift)),
        GroundControlPoint(x_pixel=300.0, y_pixel=300.0, z_elevation=float(true_scale * depth_array[300, 300] + true_shift)),
        GroundControlPoint(x_pixel=500.0, y_pixel=500.0, z_elevation=float(true_scale * depth_array[500, 500] + true_shift)),
    ]

    metric_product = product.calibrate(gcps=gcps)
    target_tif = OUTPUT_DIR / "test_metric_elevation_export.tif"

    export_res = MetricCalibrator.export_metric_elevation(metric_product, target_tif)

    assert export_res.file_path.exists()
    assert export_res.validation.is_valid is True
    assert export_res.validation.crs_matches_source is True

    # Direct rasterio inspection
    with rasterio.open(target_tif) as src:
        assert src.crs.to_epsg() == 32618
        assert (src.height, src.width) == (metadata.height, metadata.width)
        tags = src.tags()
        assert tags.get("DEPTH_TYPE") == "CALIBRATED_DSM"
        assert tags.get("IS_CALIBRATED") == "True"
        assert tags.get("UNITS") == "meters"
        assert "SCALE_FACTOR" in tags
        assert "SHIFT_OFFSET" in tags
        assert "CALIBRATION_RMSE" in tags


def test_end_to_end_real_inference_to_metric_elevation():
    """
    End-to-End Pipeline Verification:
    Real RGB Image -> Real ONNX Model CPU Inference -> Relative DSM -> Surveyed GCP Calibration -> Metric Elevation Product -> Validated GeoTIFF.
    Strictly verifies Zero Fake AI and production readiness.
    """
    sample_geotiff = DATA_DIR / "sample_geotiff.tif"
    assert sample_geotiff.exists()
    assert settings.MODEL_PATH.exists()

    pipeline = DepthPipeline(
        model_path=settings.MODEL_PATH,
        target_size=settings.MODEL_INPUT_SIZE,
        intra_op_threads=settings.ONNX_INTRA_OP_THREADS
    )

    # Pre-extract metadata to construct realistic GCPs
    meta = RasterIO.extract_metadata(sample_geotiff)

    # First get real relative depth to construct consistent calibration points
    out_rel = pipeline.process(sample_geotiff)
    rel_arr = out_rel.relative_depth

    true_scale = 50.0
    true_shift = 150.0
    gcps = [
        GroundControlPoint(x_pixel=50.0, y_pixel=50.0, z_elevation=float(true_scale * rel_arr[50, 50] + true_shift), point_id="GCP-1"),
        GroundControlPoint(x_pixel=150.0, y_pixel=150.0, z_elevation=float(true_scale * rel_arr[150, 150] + true_shift), point_id="GCP-2"),
        GroundControlPoint(x_pixel=350.0, y_pixel=350.0, z_elevation=float(true_scale * rel_arr[350, 350] + true_shift), point_id="GCP-3"),
        GroundControlPoint(x_pixel=550.0, y_pixel=550.0, z_elevation=float(true_scale * rel_arr[550, 550] + true_shift), point_id="GCP-4"),
    ]

    target_path = OUTPUT_DIR / "test_e2e_calibrated_dsm.tif"

    metric_product = RelativeDSMGenerator.process_and_calibrate(
        input_source=sample_geotiff,
        pipeline=pipeline,
        gcps=gcps,
        export_path=target_path
    )

    assert isinstance(metric_product, MetricElevationProduct)
    assert metric_product.is_metric is True
    assert metric_product.depth_type == "CALIBRATED_DSM"
    assert metric_product.units == "meters"
    assert metric_product.array.shape == (718, 791)
    assert np.isclose(metric_product.calibration.scale_factor, true_scale, atol=1e-2)
    assert np.isclose(metric_product.calibration.shift_offset, true_shift, atol=1e-2)
    assert metric_product.calibration.metrics.rmse < 0.1

    # Verify exported GeoTIFF
    assert target_path.exists()
    with rasterio.open(target_path) as src:
        assert src.crs.to_epsg() == 32618
        assert src.tags()["DEPTH_TYPE"] == "CALIBRATED_DSM"
        assert src.tags()["IS_CALIBRATED"] == "True"
        assert src.tags()["UNITS"] == "meters"

