from dataclasses import dataclass, field
from typing import Tuple, Optional, Dict, Any
import numpy as np

@dataclass
class ImageMetadata:
    """Metadata extracted from the raw input image or raster."""
    original_height: int
    original_width: int
    channels: int
    format: str
    has_georeference: bool = False
    crs: Optional[str] = None
    transform: Optional[Tuple[float, ...]] = None
    bounds: Optional[Tuple[float, float, float, float]] = None
    nodata: Optional[float] = None

@dataclass
class PreprocessedInput:
    """Preprocessed tensor and spatial tracking data."""
    tensor: np.ndarray  # Shape: (1, 3, target_h, target_w), float32
    original_dimensions: Tuple[int, int]  # (height, width)
    model_dimensions: Tuple[int, int]     # (height, width)
    metadata: ImageMetadata

@dataclass
class RawInferenceResult:
    """Direct output from the neural network."""
    raw_depth: np.ndarray  # Direct model tensor, e.g. (1, 518, 518) or (518, 518)
    inference_time_seconds: float
    model_name: str
    execution_provider: str

@dataclass
class ValidationReport:
    """Validation report ensuring output integrity and absence of fake AI."""
    is_valid: bool
    has_nans: bool
    has_infs: bool
    is_constant: bool
    output_shape_matches_input: bool
    min_value: float
    max_value: float
    mean_value: float
    std_value: float
    message: str

@dataclass
class PipelineOutput:
    """End-to-end depth estimation result."""
    relative_depth: np.ndarray  # 2D float32 normalized disparity in [0.0, 1.0]
    depth_type: str             # Strictly 'RELATIVE_DEPTH'
    original_shape: Tuple[int, int]
    metadata: ImageMetadata
    validation: ValidationReport
    timing: Dict[str, float] = field(default_factory=dict)
