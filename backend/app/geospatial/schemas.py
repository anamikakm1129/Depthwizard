from dataclasses import dataclass
from typing import Tuple, Optional, Dict, Any
from pathlib import Path

@dataclass
class GeoMetadata:
    """Detailed spatial metadata extracted from a source raster."""
    width: int
    height: int
    count: int
    dtype: str
    driver: str
    has_georeference: bool
    crs_wkt: Optional[str] = None
    crs_epsg: Optional[int] = None
    crs_string: Optional[str] = None
    transform: Optional[Tuple[float, float, float, float, float, float]] = None  # (a, b, c, d, e, f)
    bounds: Optional[Tuple[float, float, float, float]] = None  # (left, bottom, right, top)
    resolution: Optional[Tuple[float, float]] = None  # (pixel_x, pixel_y)
    nodata: Optional[float] = None

@dataclass
class RasterExportConfig:
    """Configuration options for GeoTIFF export."""
    target_path: Path
    driver: str = "GTiff"
    dtype: str = "float32"
    compress: str = "lzw"
    nodata: float = -9999.0
    tiled: bool = True
    blockxsize: int = 256
    blockysize: int = 256

@dataclass
class RasterValidationReport:
    """Rigorous validation report comparing exported GeoTIFF against source."""
    is_valid: bool
    file_exists: bool
    can_open: bool
    dimensions_match_source: bool
    crs_matches_source: bool
    transform_matches_source: bool
    bounds_match_source: bool
    resolution_matches_source: bool
    nodata_properly_set: bool
    has_valid_data_range: bool
    has_nans: bool
    has_infs: bool
    min_value: float
    max_value: float
    message: str

@dataclass
class ExportResult:
    """Complete summary of raster export operation."""
    file_path: Path
    file_size_bytes: int
    depth_type: str
    geo_metadata: GeoMetadata
    validation: RasterValidationReport
