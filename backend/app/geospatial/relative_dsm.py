"""
DepthWizard: Real Relative DSM & Raster Generation Module
=========================================================
Implements dedicated processing for unitless relative surface relief
and relative digital surface models (rDSM) from monocular depth predictions.

Scientific Principles:
- Strictly relative: values represent unitless normalized disparity or relative depth.
- Never assert metric elevation, absolute DSM, nDSM, or AGL without calibration.
- Preserve source geospatial metadata (CRS, transform, resolution, bounds).
- Zero fake AI: accepts only authentic model predictions or deterministic arrays.
"""

from enum import Enum
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple, Union
import numpy as np

from backend.app.geospatial.schemas import GeoMetadata, RasterExportConfig, ExportResult
from backend.app.geospatial.raster_io import RasterIO
from backend.app.geospatial.validation import RasterValidator
from backend.app.inference.pipeline import DepthPipeline


class RelativeSurfaceConvention(str, Enum):
    """
    Surface elevation/depth conventions for relative products:
    - SURFACE_RELIEF_DISPARITY: Higher values = closer to sensor / elevated relief (standard photogrammetric disparity).
    - CAMERA_DISTANCE_DEPTH: Higher values = farther from sensor (optical perspective depth).
    """
    SURFACE_RELIEF_DISPARITY = "surface_relief_disparity"
    CAMERA_DISTANCE_DEPTH = "camera_distance_depth"


@dataclass
class RelativeReliefMetrics:
    """Statistical summary of relative surface relief across valid pixels."""
    min_value: float
    max_value: float
    mean_value: float
    std_value: float
    relief_range: float
    roughness_iqr: float
    p10: float
    p50: float
    p90: float
    valid_pixel_count: int


@dataclass
class RelativeRasterConfig:
    """Configuration for relative DSM generation and raster formatting."""
    convention: RelativeSurfaceConvention = RelativeSurfaceConvention.SURFACE_RELIEF_DISPARITY
    invert_convention: bool = False
    apply_percentile_clip: bool = False
    percentile_range: Tuple[float, float] = (0.5, 99.5)
    compress: str = "lzw"
    nodata_value: float = -9999.0


@dataclass
class RelativeDSMProduct:
    """Complete relative surface model representation."""
    array: np.ndarray
    depth_type: str
    convention: RelativeSurfaceConvention
    is_metric: bool
    metrics: RelativeReliefMetrics
    geo_metadata: GeoMetadata
    export_result: Optional[ExportResult] = None


class RelativeDSMGenerator:
    """
    Production-quality Relative DSM generation engine.
    Transforms authentic monocular depth predictions into standardized
    relative surface relief models with geospatial integrity.
    """

    @staticmethod
    def compute_relief_metrics(array: np.ndarray) -> RelativeReliefMetrics:
        """
        Computes robust relief and surface roughness statistics on relative values.
        """
        valid_mask = np.isfinite(array)
        valid_pixels = array[valid_mask]

        if valid_pixels.size == 0:
            raise ValueError("Cannot compute relief metrics: array contains no finite values.")

        min_val = float(np.min(valid_pixels))
        max_val = float(np.max(valid_pixels))
        mean_val = float(np.mean(valid_pixels))
        std_val = float(np.std(valid_pixels))
        relief_range = float(max_val - min_val)

        p10, p25, p50, p75, p90 = np.percentile(valid_pixels, [10.0, 25.0, 50.0, 75.0, 90.0])
        roughness_iqr = float(p75 - p25)

        return RelativeReliefMetrics(
            min_value=min_val,
            max_value=max_val,
            mean_value=mean_val,
            std_value=std_val,
            relief_range=relief_range,
            roughness_iqr=roughness_iqr,
            p10=float(p10),
            p50=float(p50),
            p90=float(p90),
            valid_pixel_count=int(valid_pixels.size)
        )

    @classmethod
    def generate(
        cls,
        relative_depth: np.ndarray,
        metadata: GeoMetadata,
        config: Optional[RelativeRasterConfig] = None
    ) -> RelativeDSMProduct:
        """
        Generates a standardized Relative DSM product from a 2D depth/disparity array.

        Enforces:
        - Exact spatial shape alignment with source metadata.
        - Numerical validity (no NaN/Inf).
        - Unitless relative bounds [0.0, 1.0].
        - Immutable is_metric=False.
        """
        if config is None:
            config = RelativeRasterConfig()

        if relative_depth.ndim != 2:
            raise ValueError(f"Relative depth must be 2D, got shape {relative_depth.shape}.")

        h, w = relative_depth.shape
        if (h, w) != (metadata.height, metadata.width):
            raise ValueError(
                f"Dimension mismatch: array is ({h}x{w}) but metadata requires ({metadata.height}x{metadata.width})."
            )

        if np.isnan(relative_depth).any() or np.isinf(relative_depth).any():
            raise ValueError("Input relative depth contains NaN or Inf values.")

        processed_array = relative_depth.astype(np.float32).copy()

        # Handle convention conversion / inversion
        if config.invert_convention:
            processed_array = 1.0 - processed_array
            effective_convention = (
                RelativeSurfaceConvention.CAMERA_DISTANCE_DEPTH
                if config.convention == RelativeSurfaceConvention.SURFACE_RELIEF_DISPARITY
                else RelativeSurfaceConvention.SURFACE_RELIEF_DISPARITY
            )
        else:
            effective_convention = config.convention

        # Optional robust percentile normalization/clipping
        if config.apply_percentile_clip:
            p_low, p_high = np.percentile(processed_array, config.percentile_range)
            if p_high > p_low:
                processed_array = np.clip(processed_array, p_low, p_high)
                processed_array = (processed_array - p_low) / (p_high - p_low)

        # Ensure normalized [0.0, 1.0] range
        arr_min = float(np.min(processed_array))
        arr_max = float(np.max(processed_array))
        if arr_max > arr_min:
            processed_array = (processed_array - arr_min) / (arr_max - arr_min)
        else:
            processed_array = np.zeros_like(processed_array, dtype=np.float32)

        # Compute relief statistics
        metrics = cls.compute_relief_metrics(processed_array)

        return RelativeDSMProduct(
            array=processed_array,
            depth_type="RELATIVE_DSM",
            convention=effective_convention,
            is_metric=False,
            metrics=metrics,
            geo_metadata=metadata,
            export_result=None
        )

    @classmethod
    def export(
        cls,
        product: RelativeDSMProduct,
        target_path: Union[str, Path],
        config: Optional[RasterExportConfig] = None
    ) -> ExportResult:
        """
        Exports a RelativeDSMProduct to GeoTIFF with full geospatial preservation.
        Enforces unitless relative tags and disallows metric elevation claims.
        """
        target = Path(target_path)
        if config is None:
            config = RasterExportConfig(target_path=target, compress="lzw")
        else:
            config.target_path = target

        export_result = RasterIO.export_depth_to_geotiff(
            depth_map=product.array,
            source_metadata=product.geo_metadata,
            config=config,
            depth_type="RELATIVE_DSM",
            is_calibrated=False
        )

        product.export_result = export_result
        return export_result

    @classmethod
    def process_raster(
        cls,
        input_source: Union[str, Path],
        pipeline: DepthPipeline,
        config: Optional[RelativeRasterConfig] = None,
        export_path: Optional[Union[str, Path]] = None
    ) -> RelativeDSMProduct:
        """
        End-to-end execution:
        Input Source -> Real Inference Pipeline -> Metadata Extraction -> Relative DSM -> Optional GeoTIFF Export.
        """
        input_path = Path(input_source)
        if not input_path.exists():
            raise FileNotFoundError(f"Input source not found: {input_path}")

        # 1. Extract genuine metadata
        metadata = RasterIO.extract_metadata(input_path)

        # 2. Execute genuine inference
        pipeline_output = pipeline.process(input_path)

        # 3. Generate Relative DSM Product
        product = cls.generate(
            relative_depth=pipeline_output.relative_depth,
            metadata=metadata,
            config=config
        )

        # 4. Optional GeoTIFF export
        if export_path:
            cls.export(product, Path(export_path))

        return product

