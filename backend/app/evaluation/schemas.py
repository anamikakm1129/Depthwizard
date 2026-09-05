"""
Evaluation Data Schemas
=======================
Typed Pydantic models for quantitative depth and elevation evaluation.
Strictly adheres to .agents/rules/depthwizard-development.md (No Fake AI).
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

class ElevationMetrics(BaseModel):
    """
    Standard remote-sensing elevation and monocular depth evaluation metrics.
    All metrics must be computed strictly against real reference data.
    """
    mae: float = Field(..., description="Mean Absolute Error in meters")
    rmse: float = Field(..., description="Root Mean Square Error in meters")
    bias: float = Field(..., description="Mean Error / elevation bias in meters")
    abs_rel: float = Field(..., description="Absolute Relative Error: mean(|y - y_hat| / y)")
    sq_rel: float = Field(..., description="Square Relative Error: mean((y - y_hat)^2 / y)")
    pearson_r: float = Field(..., description="Pearson correlation coefficient [-1.0, 1.0]")
    r_squared: float = Field(..., description="Coefficient of Determination R^2")
    delta_1: float = Field(..., description="Threshold accuracy: % of points with max(y/y_hat, y_hat/y) < 1.25")
    delta_2: float = Field(..., description="Threshold accuracy: % of points with max(y/y_hat, y_hat/y) < 1.25^2")
    delta_3: float = Field(..., description="Threshold accuracy: % of points with max(y/y_hat, y_hat/y) < 1.25^3")
    valid_points_count: int = Field(..., description="Number of valid, non-nodata evaluation points")
    total_points_count: int = Field(..., description="Total pixel count in the evaluated scene")
    coverage_ratio: float = Field(..., description="Ratio of evaluated valid pixels [0.0, 1.0]")

class EvaluationResponse(BaseModel):
    """
    Response schema for scene-level quantitative accuracy evaluation.
    """
    evaluation_id: str
    target_job_id: str
    reference_filename: str
    depth_type: str
    is_metric: bool
    metrics: ElevationMetrics
    error_map_download_url: str
    warnings: List[str] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)

