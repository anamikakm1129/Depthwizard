from pathlib import Path
from typing import Union, Optional, Tuple, Dict, Any
import numpy as np
import rasterio
from rasterio.transform import Affine
from PIL import Image

from backend.app.geospatial.schemas import GeoMetadata, RasterExportConfig, ExportResult
from backend.app.geospatial.validation import RasterValidator

# Strictly disallowed labels for uncalibrated relative outputs per Rule §5
BANNED_UNITLESS_LABELS = {
    "absolute_dsm",
    "absolute_elevation",
    "dsm",
    "dtm",
    "terrain_elevation",
    "ndsm",
    "agl",
    "metric_elevation",
    "meters"
}

class RasterIO:
    """
    Handles reading raster geospatial metadata and exporting real model
    depth arrays to GeoTIFF with strict CRS and transform preservation.
    """
    @staticmethod
    def extract_metadata(source_path: Union[str, Path]) -> GeoMetadata:
        """
        Extracts spatial metadata from a source image or raster.
        Does NOT invent missing CRS or coordinates.
        """
        path = Path(source_path)
        if not path.exists():
            raise FileNotFoundError(f"Source raster not found: {path}")

        try:
            with rasterio.open(path) as src:
                has_georef = (src.crs is not None and src.transform is not None and not src.transform.is_identity)
                
                crs_wkt = src.crs.to_wkt() if src.crs else None
                crs_epsg = src.crs.to_epsg() if src.crs else None
                crs_str = str(src.crs) if src.crs else None
                
                # Transform tuple: (a, b, c, d, e, f)
                t = src.transform
                transform_tuple = (t.a, t.b, t.c, t.d, t.e, t.f) if t else None
                
                bounds_tuple = (src.bounds.left, src.bounds.bottom, src.bounds.right, src.bounds.top) if has_georef else None
                resolution_tuple = (src.res[0], src.res[1]) if has_georef else None

                return GeoMetadata(
                    width=src.width,
                    height=src.height,
                    count=src.count,
                    dtype=str(src.dtypes[0]),
                    driver=src.driver,
                    has_georeference=has_georef,
                    crs_wkt=crs_wkt,
                    crs_epsg=crs_epsg,
                    crs_string=crs_str,
                    transform=transform_tuple,
                    bounds=bounds_tuple,
                    resolution=resolution_tuple,
                    nodata=src.nodata
                )
        except Exception:
            # Non-rasterio supported or plain image
            with Image.open(path) as img:
                w, h = img.size
                return GeoMetadata(
                    width=w,
                    height=h,
                    count=len(img.getbands()),
                    dtype="uint8",
                    driver="PIL",
                    has_georeference=False
                )

    @classmethod
    def export_depth_to_geotiff(
        cls,
        depth_map: np.ndarray,
        source_metadata: GeoMetadata,
        config: RasterExportConfig,
        depth_type: str = "RELATIVE_DEPTH",
        is_calibrated: bool = False
    ) -> ExportResult:
        """
        Exports a 2D float32 depth map to GeoTIFF.
        - Preserves input CRS, affine transform, dimensions, and resolution.
        - Strictly forbids labeling relative output as absolute DSM or metric elevation.
        - Re-validates the written GeoTIFF after creation.
        """
        # Rule §5 Enforcement: Relative output must never masquerade as metric elevation
        clean_type = depth_type.lower().strip()
        is_explicitly_relative = (
            clean_type in ("relative_depth", "relative_dsm", "rdsm")
            or clean_type.startswith("relative_")
        )
        if not is_calibrated and not is_explicitly_relative and any(banned in clean_type for banned in BANNED_UNITLESS_LABELS):
            raise ValueError(
                f"Scientific Integrity Violation: Output label '{depth_type}' implies metric elevation, "
                "but calibration has not been performed. Output must be tagged as RELATIVE_DEPTH or RELATIVE_DSM."
            )

        target_path = Path(config.target_path)
        target_path.parent.mkdir(parents=True, exist_ok=True)

        h, w = depth_map.shape
        if (w, h) != (source_metadata.width, source_metadata.height):
            raise ValueError(
                f"Spatial dimension mismatch: depth map is {w}x{h} (WxH), "
                f"source metadata is {source_metadata.width}x{source_metadata.height}."
            )

        # Prepare rasterio profile
        profile = {
            "driver": config.driver,
            "height": h,
            "width": w,
            "count": 1,
            "dtype": config.dtype,
            "nodata": config.nodata
        }

        # Apply compression if supported by driver
        if config.compress:
            profile["compress"] = config.compress

        # Apply spatial reference if source was georeferenced
        if source_metadata.has_georeference:
            assert source_metadata.crs_string is not None, "Missing CRS string for georeferenced source"
            assert source_metadata.transform is not None, "Missing transform for georeferenced source"
            
            profile["crs"] = rasterio.crs.CRS.from_string(source_metadata.crs_string)
            t = source_metadata.transform
            profile["transform"] = Affine(t[0], t[1], t[2], t[3], t[4], t[5])
        else:
            # Plain raster without spatial reference
            profile["crs"] = None
            profile["transform"] = Affine.identity()

        data_to_write = depth_map.astype(np.float32)

        # Write raster with metadata tags
        with rasterio.open(target_path, "w", **profile) as dst:
            dst.write(data_to_write, 1)
            dst.update_tags(
                DEPTH_TYPE=depth_type,
                IS_CALIBRATED=str(is_calibrated),
                SOFTWARE="DepthWizard SIH 2026",
                UNITS="unitless_disparity" if not is_calibrated else "meters"
            )

        # Post-export validation
        validation_report = RasterValidator.validate(target_path, source_metadata, is_calibrated)
        if not validation_report.is_valid:
            raise RuntimeError(f"Export validation failed: {validation_report.message}")

        return ExportResult(
            file_path=target_path,
            file_size_bytes=target_path.stat().st_size,
            depth_type=depth_type,
            geo_metadata=source_metadata,
            validation=validation_report
        )
