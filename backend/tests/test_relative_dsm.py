import pytest
from pathlib import Path
import numpy as np
import rasterio

from backend.app.geospatial.schemas import GeoMetadata, RasterExportConfig
from backend.app.geospatial.raster_io import RasterIO
from backend.app.geospatial.validation import RasterValidator
from backend.app.geospatial.relative_dsm import (
    RelativeSurfaceConvention,
    RelativeReliefMetrics,
    RelativeRasterConfig,
    RelativeDSMProduct,
    RelativeDSMGenerator
)
from backend.app.inference.pipeline import DepthPipeline
from backend.app.config import settings

DATA_DIR = Path("tests/data")
OUTPUT_DIR = Path("backend/outputs")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def test_relative_dsm_generation_from_array():
    """Verifies standard relative DSM creation, shape matching, and relief statistics."""
    source_path = DATA_DIR / "sample_geotiff.tif"
    metadata = RasterIO.extract_metadata(source_path)

    # Create synthetic gradient depth array matching exact spatial dimensions
    y, x = np.mgrid[0:metadata.height, 0:metadata.width]
    depth_array = ((x + y) / (metadata.width + metadata.height)).astype(np.float32)

    product = RelativeDSMGenerator.generate(depth_array, metadata)

    assert isinstance(product, RelativeDSMProduct)
    assert product.depth_type == "RELATIVE_DSM"
    assert product.is_metric is False
    assert product.convention == RelativeSurfaceConvention.SURFACE_RELIEF_DISPARITY
    assert product.array.shape == (metadata.height, metadata.width)

    # Relief metrics verification
    metrics = product.metrics
    assert isinstance(metrics, RelativeReliefMetrics)
    assert 0.0 <= metrics.min_value <= metrics.max_value <= 1.0
    assert metrics.relief_range > 0.0
    assert metrics.roughness_iqr > 0.0
    assert metrics.valid_pixel_count == metadata.width * metadata.height
    assert metrics.p10 <= metrics.p50 <= metrics.p90


def test_relative_dsm_dimension_mismatch_fails_hard():
    """Ensures dimension mismatch between depth array and geospatial metadata raises ValueError."""
    source_path = DATA_DIR / "sample_geotiff.tif"
    metadata = RasterIO.extract_metadata(source_path)

    mismatched_array = np.zeros((metadata.height + 10, metadata.width), dtype=np.float32)

    with pytest.raises(ValueError, match="Dimension mismatch"):
        RelativeDSMGenerator.generate(mismatched_array, metadata)


def test_relative_dsm_nan_or_inf_fails_hard():
    """Ensures NaN or Inf values in input depth are strictly rejected."""
    source_path = DATA_DIR / "sample_geotiff.tif"
    metadata = RasterIO.extract_metadata(source_path)

    arr_with_nan = np.zeros((metadata.height, metadata.width), dtype=np.float32)
    arr_with_nan[10, 10] = np.nan

    with pytest.raises(ValueError, match="contains NaN or Inf"):
        RelativeDSMGenerator.generate(arr_with_nan, metadata)


def test_relative_dsm_conventions_and_inversion():
    """Verifies surface relief disparity vs camera distance depth conventions."""
    metadata = GeoMetadata(width=10, height=10, count=1, dtype="float32", driver="GTiff", has_georeference=False)
    arr = np.linspace(0.0, 1.0, 100, dtype=np.float32).reshape((10, 10))

    # Default convention
    p1 = RelativeDSMGenerator.generate(arr, metadata)
    assert p1.convention == RelativeSurfaceConvention.SURFACE_RELIEF_DISPARITY
    assert np.isclose(p1.array[0, 0], 0.0)
    assert np.isclose(p1.array[9, 9], 1.0)

    # Inverted convention
    cfg_inverted = RelativeRasterConfig(invert_convention=True)
    p2 = RelativeDSMGenerator.generate(arr, metadata, config=cfg_inverted)
    assert p2.convention == RelativeSurfaceConvention.CAMERA_DISTANCE_DEPTH
    assert np.isclose(p2.array[0, 0], 1.0)
    assert np.isclose(p2.array[9, 9], 0.0)


def test_relative_dsm_export_preserves_crs_and_metadata():
    """Verifies GeoTIFF export preserves EPSG:32618, dimensions, and writes unitless metadata tags."""
    source_path = DATA_DIR / "sample_geotiff.tif"
    metadata = RasterIO.extract_metadata(source_path)

    arr = np.linspace(0.0, 1.0, metadata.width * metadata.height, dtype=np.float32).reshape((metadata.height, metadata.width))
    product = RelativeDSMGenerator.generate(arr, metadata)

    target_path = OUTPUT_DIR / "test_rdsm_export.tif"
    export_result = RelativeDSMGenerator.export(product, target_path)

    assert export_result.file_path.exists()
    assert export_result.validation.is_valid is True
    assert export_result.validation.crs_matches_source is True
    assert export_result.validation.transform_matches_source is True

    # Re-open and verify with rasterio directly
    with rasterio.open(target_path) as src:
        assert src.crs.to_epsg() == 32618
        assert (src.height, src.width) == (metadata.height, metadata.width)
        tags = src.tags()
        assert tags.get("DEPTH_TYPE") == "RELATIVE_DSM"
        assert tags.get("IS_CALIBRATED") == "False"
        assert tags.get("UNITS") == "unitless_disparity"


def test_relative_dsm_strict_rejection_of_metric_claims():
    """Scientific Integrity: Ensures uncalibrated exports cannot masquerade as absolute DSM or elevation."""
    source_path = DATA_DIR / "sample_geotiff.tif"
    metadata = RasterIO.extract_metadata(source_path)
    arr = np.zeros((metadata.height, metadata.width), dtype=np.float32)

    # RelativeDSMProduct cannot be metric
    product = RelativeDSMGenerator.generate(arr, metadata)
    assert product.is_metric is False

    # Attempting to export with uncalibrated metric labels in RasterIO must fail
    cfg = RasterExportConfig(target_path=OUTPUT_DIR / "forbidden_rdsm.tif")
    for forbidden_label in ["ABSOLUTE_DSM", "DSM", "DTM", "ndsm", "elevation_meters", "agl"]:
        with pytest.raises(ValueError, match="Scientific Integrity Violation"):
            RasterIO.export_depth_to_geotiff(
                depth_map=arr,
                source_metadata=metadata,
                config=cfg,
                depth_type=forbidden_label,
                is_calibrated=False
            )


def test_relative_dsm_end_to_end_with_real_inference():
    """
    End-to-End Test:
    RGB GeoTIFF -> Real ONNX Model CPU Inference -> Relative DSM Product -> Validated GeoTIFF Raster.
    Strictly verifies zero mock/fake AI.
    """
    sample_geotiff = DATA_DIR / "sample_geotiff.tif"
    assert sample_geotiff.exists()
    assert settings.MODEL_PATH.exists()

    pipeline = DepthPipeline(
        model_path=settings.MODEL_PATH,
        target_size=settings.MODEL_INPUT_SIZE,
        intra_op_threads=settings.ONNX_INTRA_OP_THREADS
    )

    target_export = OUTPUT_DIR / "test_rdsm_real_inference.tif"
    product = RelativeDSMGenerator.process_raster(
        input_source=sample_geotiff,
        pipeline=pipeline,
        export_path=target_export
    )

    assert product.depth_type == "RELATIVE_DSM"
    assert product.is_metric is False
    assert product.array.shape == (718, 791)
    assert product.metrics.valid_pixel_count == 718 * 791
    assert product.metrics.std_value > 0.0  # Real model output has rich variance, not flat constant

    # Verify exported GeoTIFF
    assert target_export.exists()
    assert product.export_result is not None
    assert product.export_result.validation.is_valid is True
    assert product.export_result.validation.crs_matches_source is True

    with rasterio.open(target_export) as src:
        assert src.crs.to_epsg() == 32618
        assert src.tags()["DEPTH_TYPE"] == "RELATIVE_DSM"
        assert src.tags()["UNITS"] == "unitless_disparity"

