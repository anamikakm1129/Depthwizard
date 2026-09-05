from typing import Tuple
import numpy as np
import cv2

from backend.app.inference.schemas import RawInferenceResult, PreprocessedInput

class Postprocessor:
    """
    Postprocesses raw model disparity into the internal DepthWizard
    relative depth representation. Strictly enforces RELATIVE_DEPTH tagging.
    """
    def __init__(self, target_range: Tuple[float, float] = (0.0, 1.0)):
        self.target_range = target_range

    def postprocess(self, raw_result: RawInferenceResult, preprocessed: PreprocessedInput) -> np.ndarray:
        """
        Squeezes raw tensor, resizes back to native image dimensions,
        and normalizes to the specified unitless disparity range.
        Returns: 2D float32 array matching original image dimensions.
        """
        raw = raw_result.raw_depth
        
        # Squeeze down to 2D
        depth_2d = np.squeeze(raw)
        if depth_2d.ndim != 2:
            raise ValueError(f"Unexpected raw output shape after squeeze: {depth_2d.shape}")

        orig_h, orig_w = preprocessed.original_dimensions

        # Bilinear resize to match original image spatial dimensions
        if depth_2d.shape != (orig_h, orig_w):
            resized_depth = cv2.resize(depth_2d, (orig_w, orig_h), interpolation=cv2.INTER_LINEAR)
        else:
            resized_depth = depth_2d

        # Min-max normalization to [0.0, 1.0] unitless relative depth
        d_min = float(resized_depth.min())
        d_max = float(resized_depth.max())

        if d_max > d_min:
            normalized_depth = (resized_depth - d_min) / (d_max - d_min)
        else:
            normalized_depth = np.zeros_like(resized_depth, dtype=np.float32)

        return normalized_depth.astype(np.float32)
