from typing import Tuple
import numpy as np

from backend.app.inference.schemas import ValidationReport

class OutputValidator:
    """
    Validates postprocessed depth maps against dimensional mismatches,
    unphysical values, NaNs, Infs, or trivial/constant outputs.
    """
    @staticmethod
    def validate(
        depth_map: np.ndarray,
        expected_shape: Tuple[int, int]
    ) -> ValidationReport:
        has_nans = bool(np.isnan(depth_map).any())
        has_infs = bool(np.isinf(depth_map).any())
        
        shape_matches = (depth_map.shape == expected_shape)
        
        min_val = float(depth_map.min()) if not has_nans and depth_map.size > 0 else float("nan")
        max_val = float(depth_map.max()) if not has_nans and depth_map.size > 0 else float("nan")
        mean_val = float(depth_map.mean()) if not has_nans and depth_map.size > 0 else float("nan")
        std_val = float(depth_map.std()) if not has_nans and depth_map.size > 0 else float("nan")

        # Check if output is non-trivial (not flat zero or constant mock array)
        is_constant = (std_val < 1e-4) if not has_nans else True

        is_valid = (
            not has_nans and
            not has_infs and
            shape_matches and
            not is_constant and
            min_val >= -1e-6 and
            max_val <= 1.0 + 1e-6
        )

        messages = []
        if has_nans:
            messages.append("Output contains NaN values.")
        if has_infs:
            messages.append("Output contains Inf values.")
        if not shape_matches:
            messages.append(f"Shape mismatch: got {depth_map.shape}, expected {expected_shape}.")
        if is_constant:
            messages.append("Output has zero or trivial variance (flat array).")
        if not messages:
            messages.append("Output is numerically valid and spatially aligned.")

        return ValidationReport(
            is_valid=is_valid,
            has_nans=has_nans,
            has_infs=has_infs,
            is_constant=is_constant,
            output_shape_matches_input=shape_matches,
            min_value=min_val,
            max_value=max_val,
            mean_value=mean_val,
            std_value=std_val,
            message="; ".join(messages)
        )
