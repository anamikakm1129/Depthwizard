"""
Spatial Residual Error Map Generator
====================================
Generates 2D spatial difference rasters and colormapped residual images.
Uses a diverging colormap:
- Negative residuals (Under-estimation): Blue
- Zero residual (Exact agreement): Neutral White / Light Gray
- Positive residuals (Over-estimation): Red
Strictly adheres to .agents/rules/depthwizard-development.md (No Fake AI).
"""

from pathlib import Path
from typing import Tuple, Optional
import numpy as np
import cv2

class ErrorMapGenerator:
    """
    Computes spatial residuals and renders diverging color residual maps.
    """

    @staticmethod
    def _create_diverging_lut() -> np.ndarray:
        """
        Create a smooth 256-entry Coolwarm/Seismic diverging Look-Up Table (BGR).
        0 = Blue, 128 = Light Gray/White, 255 = Red.
        """
        lut = np.zeros((256, 3), dtype=np.uint8)
        # Blue to White (0 -> 128)
        for i in range(128):
            t = i / 128.0
            b = int(220 + (245 - 220) * t)
            g = int(60 + (245 - 60) * t)
            r = int(30 + (245 - 30) * t)
            lut[i] = [b, g, r]
        # White to Red (128 -> 256)
        for i in range(128, 256):
            t = (i - 128) / 127.0
            b = int(245 - (245 - 30) * t)
            g = int(245 - (245 - 60) * t)
            r = int(245 + (220 - 245) * t)
            lut[i] = [b, g, r]
        return lut

    @classmethod
    def generate_error_map(
        cls,
        pred: np.ndarray,
        reference: np.ndarray,
        output_filepath: Path,
        nodata: Optional[float] = None
    ) -> Tuple[np.ndarray, Path]:
        """
        Compute residual array e = pred - reference and write a diverging color PNG.

        Args:
            pred: Predicted elevation/depth (2D float)
            reference: Reference ground truth (2D float)
            output_filepath: Output PNG destination path
            nodata: Optional nodata value to mask

        Returns:
            Tuple of (raw residual float array, Path to output PNG)
        """
        if pred.shape != reference.shape:
            raise ValueError(f"Shape mismatch: pred {pred.shape} vs reference {reference.shape}")

        output_filepath = Path(output_filepath)
        output_filepath.parent.mkdir(parents=True, exist_ok=True)

        residuals = pred.astype(np.float32) - reference.astype(np.float32)

        valid_mask = np.isfinite(pred) & np.isfinite(reference)
        if nodata is not None:
            valid_mask &= (pred != nodata) & (reference != nodata)

        if not np.any(valid_mask):
            raise ValueError("No valid overlapping pixels to generate error map.")

        valid_res = residuals[valid_mask]
        # Robust symmetric range around zero (98th percentile to suppress single-pixel outliers)
        p98 = float(np.percentile(np.abs(valid_res), 98))
        max_abs = max(p98, 1e-3)

        # Normalize to [-1.0, 1.0] -> [0, 255]
        norm_res = np.clip(residuals / max_abs, -1.0, 1.0)
        uint8_map = ((norm_res + 1.0) * 127.5).astype(np.uint8)

        lut = cls._create_diverging_lut()
        colored_bgr = lut[uint8_map]

        # Apply dark background / mask for invalid / nodata pixels
        colored_bgr[~valid_mask] = [20, 20, 25] # Dark slate for nodata

        # Write PNG
        cv2.imwrite(str(output_filepath), colored_bgr)

        return residuals, output_filepath

