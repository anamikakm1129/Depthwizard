import pytest
from pathlib import Path
import numpy as np
import rasterio

from backend.app.geospatial.schemas import GeoMetadata, RasterExportConfig
from backend.app.geospatial.raster_io import RasterIO
from backend.app.geospatial.validation import RasterValidator

DATA_DIR = Path("tests/data")
OUTPUT_DIR = Path("backend/outputs")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def test_extract_metadata_geotiff():
    geotiff_path = DATA_DIR / "sample_geotiff.tif"
    meta = RasterIO.extract_metadata(geotiff_path)
    
    assert meta.has_georeference is True
    assert meta.width == 791
    assert meta.height == 718
    assert meta.crs_epsg == 32618
    assert meta.transform is not None
    assert len(meta.transform) == 6
    assert meta.bounds is not None
    assert meta.resolution is not None

def test_extract_metadata_non_georeferenced():
    # Construct a dummy non-georeferenced GeoMetadata
    dummy_meta = GeoMetadata(
        width=200,
        height=150,
        count=3,
        dtype='uint8',
        driver='PIL',
        has_georeference=False
    )
    assert dummy_meta.has_georeference is False
    assert dummy_meta.crs_string is None
    assert dummy_meta.transform is None

def test_geotiff_export_preserves_crs_and_transform():
    source_path = DATA_DIR / "sample_geotiff.tif"
    source_meta = RasterIO.extract_metadata(source_path)
    
    # Create test relative depth map of exact spatial size
    depth_map = np.linspace(0.0, 1.0, source_meta.width * source_meta.height, dtype=np.float32)
    depth_map = depth_map.reshape((source_meta.height, source_meta.width))

    target_path = OUTPUT_DIR / "test_pytest_export.tif"
    config = RasterExportConfig(target_path=target_path, compress="lzw")

    result = RasterIO.export_depth_to_geotiff(
        depth_map=depth_map,
        source_metadata=source_meta,
        config=config,
        depth_type="RELATIVE_DEPTH",
        is_calibrated=False
    )

    assert result.file_path.exists()
    assert result.validation.is_valid is True
    assert result.validation.dimensions_match_source is True
    assert result.validation.crs_matches_source is True
    assert result.validation.transform_matches_source is True
    assert result.validation.bounds_match_source is True

    # Re-open with rasterio directly
    with rasterio.open(target_path) as dst:
        assert dst.crs.to_epsg() == 32618
        assert dst.width == 791
        assert dst.height == 718
        assert dst.tags()["DEPTH_TYPE"] == "RELATIVE_DEPTH"
        assert dst.tags()["IS_CALIBRATED"] == "False"
        data = dst.read(1)
        assert data.shape == (718, 791)
        assert not np.isnan(data).any()

def test_export_rejects_uncalibrated_metric_labels():
    source_path = DATA_DIR / "sample_geotiff.tif"
    source_meta = RasterIO.extract_metadata(source_path)
    depth_map = np.zeros((source_meta.height, source_meta.width), dtype=np.float32)
    target_path = OUTPUT_DIR / "illegal_test.tif"
    config = RasterExportConfig(target_path=target_path)

    # Test each banned metric label
    banned_labels = ["ABSOLUTE_DSM", "elevation_meters", "metric_elevation", "ndsm", "terrain_elevation"]
    for label in banned_labels:
        with pytest.raises(ValueError, match="Scientific Integrity Violation"):
            RasterIO.export_depth_to_geotiff(
                depth_map=depth_map,
                source_metadata=source_meta,
                config=config,
                depth_type=label,
                is_calibrated=False
            )

def test_non_georeferenced_export_does_not_fabricate_crs():
    meta = GeoMetadata(
        width=100,
        height=100,
        count=3,
        dtype="uint8",
        driver="PIL",
        has_georeference=False
    )
    depth_map = np.full((100, 100), 0.5, dtype=np.float32)
    # add variation so validator doesn't flag zero std
    depth_map[0, 0] = 0.0
    depth_map[99, 99] = 1.0

    target_path = OUTPUT_DIR / "test_non_geo.tif"
    config = RasterExportConfig(target_path=target_path)

    result = RasterIO.export_depth_to_geotiff(
        depth_map=depth_map,
        source_metadata=meta,
        config=config,
        depth_type="RELATIVE_DEPTH",
        is_calibrated=False
    )

    assert result.validation.is_valid is True
    assert result.validation.crs_matches_source is True
    with rasterio.open(target_path) as dst:
        assert dst.crs is None  # Must NOT invent fake CRS!

def test_validator_catches_tampered_raster():
    source_path = DATA_DIR / "sample_geotiff.tif"
    source_meta = RasterIO.extract_metadata(source_path)
    
    # Tamper with expected dimensions in metadata
    tampered_meta = GeoMetadata(
        width=source_meta.width + 10,
        height=source_meta.height,
        count=1,
        dtype="float32",
        driver="GTiff",
        has_georeference=True,
        crs_string=source_meta.crs_string,
        transform=source_meta.transform,
        bounds=source_meta.bounds,
        resolution=source_meta.resolution,
        nodata=-9999.0
    )
    
    existing_file = OUTPUT_DIR / "test_pytest_export.tif"
    if existing_file.exists():
        report = RasterValidator.validate(existing_file, tampered_meta, is_calibrated=False)
        assert report.is_valid is False
        assert report.dimensions_match_source is False
