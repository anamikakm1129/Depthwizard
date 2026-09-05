"""
Deterministic Scientific Evaluation Metrics
===========================================
Computes rigorous quantitative accuracy metrics comparing predicted elevation against
reference ground-truth elevation arrays.
Strictly adheres to .agents/rules/depthwizard-development.md (No Fake AI).
"""

from typing import Tuple, Optional
import numpy as np
from backend.app.evaluation.schemas import ElevationMetrics

class ElevationMetricComputer:
    """
    Computes standard remote-sensing and computer-vision elevation metrics.
    """

    @staticmethod
    def compute(
        pred: np.ndarray,
        reference: np.ndarray,
        nodata: Optional[float] = None
    ) -> ElevationMetrics:
        """
        Compute standard elevation accuracy metrics.

        Args:
            pred: Predicted elevation or depth array (2D float)
            reference: Reference ground-truth elevation array (2D float)
            nodata: Optional nodata value to mask out

        Returns:
            ElevationMetrics instance with MAE, RMSE, Bias, AbsRel, SqRel, delta metrics, R^2
        """
        if pred.shape != reference.shape:
            raise ValueError(f"Shape mismatch: pred {pred.shape} vs reference {reference.shape}")

        # Construct valid mask
        valid = np.isfinite(pred) & np.isfinite(reference)
        if nodata is not None:
            valid &= (reference != nodata) & (pred != nodata)

        total_points = pred.size
        valid_count = int(np.sum(valid))

        if valid_count < 3:
            raise ValueError(f"Insufficient valid evaluation points: found {valid_count}, minimum is 3.")

        y_hat = pred[valid].astype(np.float64)
        y = reference[valid].astype(np.float64)

        # 1. Linear Residuals
        diff = y_hat - y
        mae = float(np.mean(np.abs(diff)))
        rmse = float(np.sqrt(np.mean(diff ** 2)))
        bias = float(np.mean(diff))

        # 2. Pearson Correlation & Coefficient of Determination (R^2)
        std_hat = np.std(y_hat)
        std_ref = np.std(y)
        if std_hat > 1e-8 and std_ref > 1e-8:
            cov = np.mean((y_hat - np.mean(y_hat)) * (y - np.mean(y)))
            pearson_r = float(np.clip(cov / (std_hat * std_ref), -1.0, 1.0))
        else:
            pearson_r = 0.0

        ss_tot = np.sum((y - np.mean(y)) ** 2)
        ss_res = np.sum(diff ** 2)
        r_squared = float(1.0 - (ss_res / ss_tot)) if ss_tot > 1e-8 else 0.0

        # 3. Ratio-based Depth Metrics (computed on strictly positive reference values)
        pos_mask = (y > 1e-4) & (y_hat > 1e-4)
        if np.any(pos_mask):
            y_pos = y[pos_mask]
            y_hat_pos = y_hat[pos_mask]

            abs_rel = float(np.mean(np.abs(y_hat_pos - y_pos) / y_pos))
            sq_rel = float(np.mean(((y_hat_pos - y_pos) ** 2) / y_pos))

            ratio = np.maximum(y_hat_pos / y_pos, y_pos / y_hat_pos)
            delta_1 = float(np.mean(ratio < 1.25))
            delta_2 = float(np.mean(ratio < (1.25 ** 2)))
            delta_3 = float(np.mean(ratio < (1.25 ** 3)))
        else:
            # For data with zero/negative datum elevations where ratios are mathematically undefined
            abs_rel = float(mae / (np.mean(np.abs(y)) + 1e-6))
            sq_rel = float((rmse ** 2) / (np.mean(np.abs(y)) + 1e-6))
            delta_1 = 0.0
            delta_2 = 0.0
            delta_3 = 0.0

        coverage = float(valid_count / total_points)

        return ElevationMetrics(
            mae=mae,
            rmse=rmse,
            bias=bias,
            abs_rel=abs_rel,
            sq_rel=sq_rel,
            pearson_r=pearson_r,
            r_squared=r_squared,
            delta_1=delta_1,
            delta_2=delta_2,
            delta_3=delta_3,
            valid_points_count=valid_count,
            total_points_count=total_points,
            coverage_ratio=coverage
        )

