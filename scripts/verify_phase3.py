import sys
from pathlib import Path
import numpy as np
import rasterio

# Ensure project root in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.inference.pipeline import DepthPipeline
from backend.app.geospatial.raster_io import RasterIO
from backend.app.geospatial.schemas import RasterExportConfig

def verify_phase3():
    print("==========================================================")
    print("   DEPTHWIZARD PHASE 3 GEOSPATIAL & EXPORT VERIFICATION   ")
    print("==========================================================")

    model_path = PROJECT_ROOT / "backend" / "models" / "depth_anything_v2_vits_int8.onnx"
    data_dir = PROJECT_ROOT / "tests" / "data"
    output_dir = PROJECT_ROOT / "backend" / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)

    pipeline = DepthPipeline(model_path=model_path, target_size=518, intra_op_threads=2)

    # TEST CASE 1: Georeferenced GeoTIFF
    print("\n[TEST CASE 1] Georeferenced GeoTIFF -> Relative Depth GeoTIFF Export")
    geotiff_input = data_dir / "sample_geotiff.tif"
    source_meta = RasterIO.extract_metadata(geotiff_input)
    print(f"Source: {geotiff_input.name} ({source_meta.width}x{source_meta.height})")
    print(f" - Has Georeference: {source_meta.has_georeference}")
    print(f" - CRS: {source_meta.crs_string}")
    print(f" - Transform: {source_meta.transform[:6]}")
    assert source_meta.has_georeference is True

    # Run real model inference
    pipe_out = pipeline.process(geotiff_input)
    assert pipe_out.depth_type == "RELATIVE_DEPTH"

    # Export to GeoTIFF
    export_path = output_dir / "exported_sample_geotiff_depth.tif"
    cfg = RasterExportConfig(target_path=export_path, compress="lzw")
    
    export_res = RasterIO.export_depth_to_geotiff(
        depth_map=pipe_out.relative_depth,
        source_metadata=source_meta,
        config=cfg,
        depth_type="RELATIVE_DEPTH",
        is_calibrated=False
    )

    print(f"Exported to: {export_res.file_path} ({export_res.file_size_bytes / 1024:.1f} KB)")
    val = export_res.validation
    print(f"Validation Report:")
    print(f" - Is Valid: {val.is_valid}")
    print(f" - Dimensions Match Source: {val.dimensions_match_source}")
    print(f" - CRS Matches Source: {val.crs_matches_source}")
    print(f" - Transform Matches Source: {val.transform_matches_source}")
    print(f" - Bounds Match Source: {val.bounds_match_source}")
    print(f" - Nodata Set: {val.nodata_properly_set}")
    print(f" - Value Range: [{val.min_value:.4f}, {val.max_value:.4f}]")
    assert val.is_valid, f"Validation failed: {val.message}"
    print(" -> Test Case 1 PASSED.")

    # TEST CASE 2: Non-georeferenced Image
    print("\n[TEST CASE 2] Non-Georeferenced Image -> Relative Raster Export (No Fabricated CRS)")
    # Create an explicit non-georeferenced optical image crop from the aerial sample
    aerial_input = data_dir / "sample_aerial.tif"
    aerial_meta = RasterIO.extract_metadata(aerial_input)
    # Force non-georeferenced metadata to test plain optical image handling
    aerial_meta.has_georeference = False
    aerial_meta.crs_string = None
    aerial_meta.crs_wkt = None
    aerial_meta.crs_epsg = None
    aerial_meta.transform = None
    aerial_meta.bounds = None

    # Run real inference
    aerial_pipe_out = pipeline.process(aerial_input)

    aerial_export_path = output_dir / "exported_plain_aerial_depth.tif"
    aerial_cfg = RasterExportConfig(target_path=aerial_export_path, compress="lzw")
    
    aerial_res = RasterIO.export_depth_to_geotiff(
        depth_map=aerial_pipe_out.relative_depth,
        source_metadata=aerial_meta,
        config=aerial_cfg,
        depth_type="RELATIVE_DEPTH",
        is_calibrated=False
    )

    print(f"Exported to: {aerial_res.file_path} ({aerial_res.file_size_bytes / 1024:.1f} KB)")
    a_val = aerial_res.validation
    print(f"Validation Report:")
    print(f" - Is Valid: {a_val.is_valid}")
    print(f" - CRS Matches Source (None/Unset): {a_val.crs_matches_source}")
    print(f" - Dimensions Match Source: {a_val.dimensions_match_source}")
    with rasterio.open(aerial_export_path) as dst:
        assert dst.crs is None, "CRITICAL ERROR: CRS was fabricated for non-georeferenced image!"
        print(" - Verified: No CRS or coordinates were fabricated.")
    assert a_val.is_valid, f"Validation failed: {a_val.message}"
    print(" -> Test Case 2 PASSED.")

    # TEST CASE 3: Scientific Integrity Guard (Rule §5 Enforcement)
    print("\n[TEST CASE 3] Scientific Integrity Guard: Reject Uncalibrated 'ABSOLUTE_DSM' Labels")
    try:
        RasterIO.export_depth_to_geotiff(
            depth_map=pipe_out.relative_depth,
            source_metadata=source_meta,
            config=RasterExportConfig(target_path=output_dir / "illegal.tif"),
            depth_type="ABSOLUTE_DSM",
            is_calibrated=False
        )
        raise AssertionError("Scientific Integrity Check Failed: Allowed uncalibrated output to be labeled as ABSOLUTE_DSM!")
    except ValueError as e:
        print(f" - Successfully caught and blocked uncalibrated label: {e}")
        print(" -> Test Case 3 PASSED.")

    print("\n==========================================================")
    print("   ALL PHASE 3 VERIFICATIONS COMPLETED WITH SUCCESS       ")
    print("==========================================================")

if __name__ == "__main__":
    verify_phase3()
