from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Tuple, Dict, Any
import numpy as np

class CalibrationMode(str, Enum):
    UNCALIBRATED_RELATIVE = "uncalibrated_relative"
    CANDIDATE_METRIC = "candidate_metric"
    VALIDATED_METRIC = "validated_metric"

class CalibrationMethod(str, Enum):
    NONE = "none"
    SCALE_AND_SHIFT = "scale_and_shift"
    GCP_AFFINE = "gcp_affine"
    KNOWN_HEIGHT_DELTA = "known_height_delta"

class CalibrationSourceType(str, Enum):
    NONE = "none"
    REFERENCE_DEM = "reference_dem"
    REFERENCE_DSM = "reference_dsm"
    SURVEYED_GCPS = "surveyed_gcps"
    NDSM_GAMUS = "ndsm_gamus"

@dataclass
class GroundControlPoint:
    """A surveyed or verified reference control point."""
    x_pixel: float
    y_pixel: float
    z_elevation: float
    point_id: Optional[str] = None
    description: Optional[str] = None

@dataclass
class CalibrationMetrics:
    """Rigorous statistical validation metrics against authentic reference data."""
    mae: float
    rmse: float
    bias: float
    pearson_r: float
    r_squared: float
    sample_count: int

@dataclass
class CalibrationResult:
    """Structured result of a calibration operation."""
    mode: CalibrationMode
    method: CalibrationMethod
    source_type: CalibrationSourceType
    source_identifier: Optional[str]
    is_metric: bool
    depth_type: str
    calibrated_array: np.ndarray
    scale_factor: Optional[float] = None
    shift_offset: Optional[float] = None
    metrics: Optional[CalibrationMetrics] = None
    warnings: List[str] = field(default_factory=list)
    limitations: List[str] = field(default_factory=list)
    rejection_reason: Optional[str] = None
