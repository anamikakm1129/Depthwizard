from pathlib import Path
from typing import Optional
import numpy as np
import rasterio

from backend.app.geospatial.schemas import GeoMetadata, RasterValidationReport

class RasterValidator:
    """
    Performs comprehensive geospatial and radiometric validation of exported rasters
    against the original source metadata.
    """
    @classmethod
    def validate(
        cls,
        exported_path: Path,
        source_metadata: GeoMetadata,
        is_calibrated: bool = False
    ) -> RasterValidationReport:
        if not exported_path.exists():
            return RasterValidationReport(
                is_valid=False,
                file_exists=False,
                can_open=False,
                dimensions_match_source=False,
                crs_matches_source=False,
                transform_matches_source=False,
                bounds_match_source=False,
                resolution_matches_source=False,
                nodata_properly_set=False,
                has_valid_data_range=False,
                has_nans=False,
                has_infs=False,
                min_value=float("nan"),
                max_value=float("nan"),
                message=f"Export file does not exist: {exported_path}"
            )

        try:
            with rasterio.open(exported_path) as dst:
                can_open = True
                
                # 1. Dimensions
                dims_match = (dst.width == source_metadata.width and dst.height == source_metadata.height)
                
                # 2. CRS
                if source_metadata.has_georeference:
                    src_crs = rasterio.crs.CRS.from_string(source_metadata.crs_string)
                    crs_match = (dst.crs == src_crs or (dst.crs.to_epsg() == src_crs.to_epsg() and src_crs.to_epsg() is not None))
                else:
                    crs_match = (dst.crs is None)

                # 3. Transform
                if source_metadata.has_georeference:
                    st = source_metadata.transform
                    dt = dst.transform
                    t_match = bool(
                        np.isclose(dt.a, st[0], atol=1e-4) and
                        np.isclose(dt.b, st[1], atol=1e-4) and
                        np.isclose(dt.c, st[2], atol=1e-4) and
                        np.isclose(dt.d, st[3], atol=1e-4) and
                        np.isclose(dt.e, st[4], atol=1e-4) and
                        np.isclose(dt.f, st[5], atol=1e-4)
                    )
                else:
                    t_match = True

                # 4. Bounds & Resolution
                if source_metadata.has_georeference:
                    sb = source_metadata.bounds
                    db = (dst.bounds.left, dst.bounds.bottom, dst.bounds.right, dst.bounds.top)
                    bounds_match = bool(all(np.isclose(d, s, atol=1e-2) for d, s in zip(db, sb)))
                    res_match = bool(
                        np.isclose(dst.res[0], source_metadata.resolution[0], atol=1e-4) and
                        np.isclose(dst.res[1], source_metadata.resolution[1], atol=1e-4)
                    )
                else:
                    bounds_match = True
                    res_match = True

                # 5. Nodata
                nodata_set = (dst.nodata is not None)

                # 6. Read and validate raster array
                data = dst.read(1)
                
                # Mask nodata if present
                if dst.nodata is not None:
                    valid_mask = (data != dst.nodata)
                    valid_data = data[valid_mask]
                else:
                    valid_data = data

                has_nans = bool(np.isnan(data).any())
                has_infs = bool(np.isinf(data).any())
                
                if valid_data.size > 0 and not has_nans:
                    min_val = float(valid_data.min())
                    max_val = float(valid_data.max())
                    std_val = float(valid_data.std())
                    
                    if not is_calibrated:
                        range_valid = (min_val >= -1e-5 and max_val <= 1.0 + 1e-5 and std_val > 1e-4)
                    else:
                        range_valid = (std_val > 1e-4)
                else:
                    min_val = float("nan")
                    max_val = float("nan")
                    range_valid = False

                # 7. Metadata Tags
                tags = dst.tags()
                depth_type_tag = tags.get("DEPTH_TYPE", "")
                if not is_calibrated and depth_type_tag != "RELATIVE_DEPTH":
                    tag_valid = False
                else:
                    tag_valid = True

                errors = []
                if not dims_match:
                    errors.append(f"Dimension mismatch: got ({dst.width}x{dst.height}), expected ({source_metadata.width}x{source_metadata.height})")
                if not crs_match:
                    errors.append(f"CRS mismatch: got {dst.crs}, expected {source_metadata.crs_string}")
                if not t_match:
                    errors.append("Affine geotransform does not match source")
                if not bounds_match:
                    errors.append("Bounding box does not match source")
                if not nodata_set:
                    errors.append("Nodata value not defined in GeoTIFF")
                if has_nans:
                    errors.append("Raster contains NaN values")
                if has_infs:
                    errors.append("Raster contains Inf values")
                if not range_valid:
                    errors.append(f"Invalid radiometric range or trivial variance: min={min_val}, max={max_val}")
                if not tag_valid:
                    errors.append(f"Invalid DEPTH_TYPE tag: '{depth_type_tag}'")

                is_valid = (
                    dims_match and
                    crs_match and
                    t_match and
                    bounds_match and
                    res_match and
                    nodata_set and
                    not has_nans and
                    not has_infs and
                    range_valid and
                    tag_valid
                )

                message = "; ".join(errors) if errors else "GeoTIFF is valid, spatially aligned, and verified."

                return RasterValidationReport(
                    is_valid=is_valid,
                    file_exists=True,
                    can_open=True,
                    dimensions_match_source=dims_match,
                    crs_matches_source=crs_match,
                    transform_matches_source=t_match,
                    bounds_match_source=bounds_match,
                    resolution_matches_source=res_match,
                    nodata_properly_set=nodata_set,
                    has_valid_data_range=range_valid,
                    has_nans=has_nans,
                    has_infs=has_infs,
                    min_value=min_val,
                    max_value=max_val,
                    message=message
                )

        except Exception as e:
            return RasterValidationReport(
                is_valid=False,
                file_exists=True,
                can_open=False,
                dimensions_match_source=False,
                crs_matches_source=False,
                transform_matches_source=False,
                bounds_match_source=False,
                resolution_matches_source=False,
                nodata_properly_set=False,
                has_valid_data_range=False,
                has_nans=False,
                has_infs=False,
                min_value=float("nan"),
                max_value=float("nan"),
                message=f"Exception during GeoTIFF validation: {str(e)}"
            )
