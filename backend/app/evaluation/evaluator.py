"""
Scene Evaluator Engine
======================
Coordinates spatial alignment, quantitative accuracy calculation, and error map generation.
Strictly adheres to .agents/rules/depthwizard-development.md (No Fake AI).
"""

import uuid
from pathlib import Path
from typing import Optional, Tuple, List
import numpy as np
import cv2
import rasterio

from backend.app.config import settings
from backend.app.geospatial.raster_io import RasterIO
from backend.app.evaluation.schemas import EvaluationResponse, ElevationMetrics
from backend.app.evaluation.metrics import ElevationMetricComputer
from backend.app.evaluation.error_map import ErrorMapGenerator

class SceneEvaluator:
    """
    Evaluates predicted elevation against real ground-truth reference rasters.
    """

    @classmethod
    def evaluate_rasters(
        cls,
        predicted_raster_path: Path,
        reference_raster_path: Path,
        job_id: str,
        is_metric: bool = False,
        depth_type: str = "RELATIVE_DEPTH"
    ) -> EvaluationResponse:
        """
        Perform rigorous evaluation of a predicted raster against a reference raster.

        Args:
            predicted_raster_path: Path to predicted GeoTIFF
            reference_raster_path: Path to reference ground-truth raster
            job_id: Associated job identifier
            is_metric: Whether the prediction was calibrated to meters
            depth_type: Prediction depth type tag

        Returns:
            EvaluationResponse with metrics, error map URL, and scientific warnings
        """
        predicted_raster_path = Path(predicted_raster_path)
        reference_raster_path = Path(reference_raster_path)

        if not predicted_raster_path.exists():
            raise FileNotFoundError(f"Predicted raster not found at {predicted_raster_path}")
        if not reference_raster_path.exists():
            raise FileNotFoundError(f"Reference raster not found at {reference_raster_path}")

        # 1. Read Predicted Raster
        with rasterio.open(predicted_raster_path) as src_pred:
            pred_arr = src_pred.read(1).astype(np.float32)
            pred_meta = src_pred.meta
            pred_crs = src_pred.crs

        # 2. Read Reference Raster
        with rasterio.open(reference_raster_path) as src_ref:
            ref_arr = src_ref.read(1).astype(np.float32)
            ref_meta = src_ref.meta
            ref_crs = src_ref.crs
            ref_nodata = src_ref.nodata

        warnings: List[str] = []
        limitations: List[str] = []

        # 3. Spatial Alignment Check & Resampling
        if pred_arr.shape != ref_arr.shape:
            # Resample reference to predicted raster dimensions via bilinear interpolation
            ref_arr = cv2.resize(
                ref_arr,
                (pred_arr.shape[1], pred_arr.shape[0]),
                interpolation=cv2.INTER_LINEAR
            )
            warnings.append(
                f"Reference raster dimensions ({ref_meta['width']}x{ref_meta['height']}) differed from "
                f"prediction ({pred_arr.shape[1]}x{pred_arr.shape[0]}); bilinearly resampled for pixel-level alignment."
            )

        # 4. Check CRS consistency
        if pred_crs and ref_crs and pred_crs != ref_crs:
            warnings.append(
                f"CRS mismatch: prediction is {pred_crs.to_string()}, reference is {ref_crs.to_string()}."
            )

        # 5. Scientific Semantics Warning for Uncalibrated Relative Depth
        if not is_metric:
            warnings.append(
                "Prediction is uncalibrated relative disparity [0.0, 1.0]. Linear metrics (MAE, RMSE, Bias) "
                "reflect magnitude scale divergence from metric elevation. Pearson R evaluates structural slope correlation."
            )
            limitations.append(
                "Quantitative metric elevation accuracy cannot be certified on uncalibrated disparity."
            )

        # 6. Compute Metrics
        metrics = ElevationMetricComputer.compute(
            pred=pred_arr,
            reference=ref_arr,
            nodata=ref_nodata
        )

        # 7. Generate Spatial Residual Error Map
        eval_id = str(uuid.uuid4())
        error_map_filename = f"{job_id}_errormap_{eval_id[:8]}.png"
        error_map_path = settings.OUTPUT_DIR / error_map_filename

        ErrorMapGenerator.generate_error_map(
            pred=pred_arr,
            reference=ref_arr,
            output_filepath=error_map_path,
            nodata=ref_nodata
        )

        return EvaluationResponse(
            evaluation_id=eval_id,
            target_job_id=job_id,
            reference_filename=reference_raster_path.name,
            depth_type=depth_type,
            is_metric=is_metric,
            metrics=metrics,
            error_map_download_url=f"/api/v1/download/{error_map_filename}",
            warnings=warnings,
            limitations=limitations
        )

