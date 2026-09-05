from pydantic import BaseModel, Field
from typing import Optional, List, Tuple, Dict, Any

class HealthResponse(BaseModel):
    status: str = "ok"
    model_name: str
    model_loaded: bool
    execution_provider: str
    device: str
    version: str

class ModelInfoResponse(BaseModel):
    model_name: str
    model_path: str
    input_resolution: int
    license: str
    output_type: str
    target_hardware: str
    description: str

class ImageMetadataResponse(BaseModel):
    original_height: int
    original_width: int
    channels: int
    format: str
    has_georeference: bool
    crs: Optional[str] = None
    transform: Optional[Tuple[float, float, float, float, float, float]] = None
    bounds: Optional[Tuple[float, float, float, float]] = None
    nodata: Optional[float] = None

class ValidationResponse(BaseModel):
    is_valid: bool
    has_nans: bool
    has_infs: bool
    is_constant: bool
    min_value: float
    max_value: float
    mean_value: float
    std_value: float
    message: str

class CalibrationMetricsResponse(BaseModel):
    mae: float
    rmse: float
    bias: float
    pearson_r: float
    r_squared: float
    sample_count: int

class CalibrationResponse(BaseModel):
    mode: str
    method: str
    source_type: str
    source_identifier: Optional[str] = None
    is_metric: bool
    depth_type: str
    scale_factor: Optional[float] = None
    shift_offset: Optional[float] = None
    metrics: Optional[CalibrationMetricsResponse] = None
    warnings: List[str] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)
    rejection_reason: Optional[str] = None

class ProcessImageResponse(BaseModel):
    job_id: str
    status: str
    depth_type: str
    input_metadata: ImageMetadataResponse
    validation: ValidationResponse
    calibration: CalibrationResponse
    timings: Dict[str, float]
    geotiff_download_url: str
    preview_png_download_url: str
    mesh_download_url: Optional[str] = None

class GCPInput(BaseModel):
    x_pixel: float
    y_pixel: float
    z_elevation: float
    point_id: Optional[str] = None
    description: Optional[str] = None
