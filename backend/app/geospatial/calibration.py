from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any, Union
import numpy as np
from scipy import stats
from rasterio.transform import Affine

from backend.app.geospatial.schemas import GeoMetadata, RasterExportConfig, ExportResult
from backend.app.geospatial.raster_io import RasterIO
from backend.app.geospatial.calibration_schemas import (
    CalibrationMode,
    CalibrationMethod,
    CalibrationSourceType,
    GroundControlPoint,
    CalibrationMetrics,
    CalibrationResult,
    MetricElevationProduct
)

class MetricCalibrator:
    """
    Geospatial calibration engine.
    Strictly separates relative disparity from metric elevation.
    Does NOT fabricate reference data or claim accuracy without empirical validation.
    """
    @staticmethod
    def fallback_to_relative(
        depth_map: np.ndarray,
        reason: str = "No valid elevation reference provided."
    ) -> CalibrationResult:
        """
        Guaranteed safe fallback: retains relative disparity representation.
        Zero fabricated metrics or elevations.
        """
        return CalibrationResult(
            mode=CalibrationMode.UNCALIBRATED_RELATIVE,
            method=CalibrationMethod.NONE,
            source_type=CalibrationSourceType.NONE,
            source_identifier=None,
            is_metric=False,
            depth_type="RELATIVE_DEPTH",
            calibrated_array=depth_map.astype(np.float32),
            scale_factor=None,
            shift_offset=None,
            metrics=None,
            warnings=["Calibration reference absent or rejected; maintaining unitless relative depth."],
            limitations=["Output values are relative disparity [0, 1] and must not be interpreted as meters or elevation."],
            rejection_reason=reason
        )

    @classmethod
    def calibrate_with_gcps(
        cls,
        depth_map: np.ndarray,
        gcps: List[GroundControlPoint],
        metadata: Optional[GeoMetadata] = None,
        max_rmse_threshold: float = 15.0,
        min_r2_threshold: float = 0.20
    ) -> CalibrationResult:
        """
        Calibrates relative depth using surveyed Ground Control Points.
        Requires at least 3 valid, distinct GCPs within image boundaries.
        Supports both direct pixel coordinates and projected map coordinates (x_geo, y_geo).
        """
        if not gcps or len(gcps) < 3:
            return cls.fallback_to_relative(
                depth_map,
                reason=f"Insufficient GCPs: provided {len(gcps) if gcps else 0}, minimum required is 3."
            )

        h, w = depth_map.shape
        valid_pairs = []

        for gcp in gcps:
            # Map coordinate projection if geographic coordinates provided with georeferenced metadata
            if (
                gcp.x_geo is not None
                and gcp.y_geo is not None
                and metadata is not None
                and metadata.has_georeference
                and metadata.transform is not None
            ):
                t = Affine(
                    metadata.transform[0], metadata.transform[1], metadata.transform[2],
                    metadata.transform[3], metadata.transform[4], metadata.transform[5]
                )
                from rasterio.transform import rowcol
                py, px = rowcol(t, gcp.x_geo, gcp.y_geo)
            else:
                px = int(round(gcp.x_pixel))
                py = int(round(gcp.y_pixel))

            if 0 <= px < w and 0 <= py < h:
                d_val = float(depth_map[py, px])
                valid_pairs.append((d_val, gcp.z_elevation))

        if len(valid_pairs) < 3:
            return cls.fallback_to_relative(
                depth_map,
                reason=f"Only {len(valid_pairs)} GCPs fall within raster boundaries ({w}x{h}); minimum 3 required."
            )

        d_vals = np.array([p[0] for p in valid_pairs], dtype=np.float64)
        z_vals = np.array([p[1] for p in valid_pairs], dtype=np.float64)

        # Check for collinear or constant values
        if np.std(d_vals) < 1e-5:
            return cls.fallback_to_relative(
                depth_map,
                reason="GCP relative depth values have near-zero variance; cannot solve scale and shift."
            )

        # Fit least-squares: Z = s * d + t
        A = np.vstack([d_vals, np.ones_like(d_vals)]).T
        solution, residuals, rank, s_svd = np.linalg.lstsq(A, z_vals, rcond=None)
        scale = float(solution[0])
        shift = float(solution[1])

        # Compute predicted elevations at GCPs
        z_pred = scale * d_vals + shift

        # Validation metrics
        errors = z_pred - z_vals
        mae = float(np.mean(np.abs(errors)))
        rmse = float(np.sqrt(np.mean(errors ** 2)))
        bias = float(np.mean(errors))
        
        # Pearson correlation
        r_val, _ = stats.pearsonr(d_vals, z_vals)
        pearson_r = float(r_val) if not np.isnan(r_val) else 0.0

        # R-squared
        ss_tot = np.sum((z_vals - np.mean(z_vals)) ** 2)
        ss_res = np.sum(errors ** 2)
        r_squared = float(1.0 - (ss_res / ss_tot)) if ss_tot > 1e-6 else 0.0

        metrics = CalibrationMetrics(
            mae=mae,
            rmse=rmse,
            bias=bias,
            pearson_r=pearson_r,
            r_squared=r_squared,
            sample_count=len(valid_pairs)
        )

        warnings = []
        limitations = [
            "Scale-and-shift assumes a linear relationship between monocular disparity and absolute elevation.",
            f"Derived from {len(valid_pairs)} point measurements; spatial interpolation across terrain may vary in accuracy."
        ]

        # Gating checks
        if rmse > max_rmse_threshold or r_squared < min_r2_threshold:
            rejection = f"Calibration rejected: RMSE ({rmse:.2f}m) exceeds threshold ({max_rmse_threshold:.2f}m) or R2 ({r_squared:.2f}) is below ({min_r2_threshold:.2f})."
            warnings.append(rejection)
            return CalibrationResult(
                mode=CalibrationMode.CANDIDATE_METRIC,
                method=CalibrationMethod.GCP_AFFINE,
                source_type=CalibrationSourceType.SURVEYED_GCPS,
                source_identifier="user_provided_gcps",
                is_metric=False,
                depth_type="RELATIVE_DEPTH",
                calibrated_array=depth_map.astype(np.float32),
                scale_factor=scale,
                shift_offset=shift,
                metrics=metrics,
                warnings=warnings,
                limitations=limitations,
                rejection_reason=rejection
            )

        # Successfully validated metric output
        calibrated_array = (scale * depth_map + shift).astype(np.float32)
        return CalibrationResult(
            mode=CalibrationMode.VALIDATED_METRIC,
            method=CalibrationMethod.GCP_AFFINE,
            source_type=CalibrationSourceType.SURVEYED_GCPS,
            source_identifier="user_provided_gcps",
            is_metric=True,
            depth_type="CALIBRATED_DSM",
            calibrated_array=calibrated_array,
            scale_factor=scale,
            shift_offset=shift,
            metrics=metrics,
            warnings=warnings,
            limitations=limitations,
            rejection_reason=None
        )

    @classmethod
    def calibrate_with_reference_raster(
        cls,
        depth_map: np.ndarray,
        reference_array: np.ndarray,
        source_type: CalibrationSourceType,
        source_identifier: str,
        nodata_value: Optional[float] = None,
        max_rmse_threshold: float = 15.0,
        min_r2_threshold: float = 0.20
    ) -> CalibrationResult:
        """
        Calibrates relative depth against an overlapping reference elevation raster
        (e.g., Copernicus DEM, SRTM, or GAMUS nDSM).
        """
        if depth_map.shape != reference_array.shape:
            return cls.fallback_to_relative(
                depth_map,
                reason=f"Shape mismatch: depth map is {depth_map.shape}, reference raster is {reference_array.shape}."
            )

        # Valid mask
        mask = np.isfinite(reference_array) & np.isfinite(depth_map)
        if nodata_value is not None:
            mask = mask & (reference_array != nodata_value)

        valid_count = int(np.sum(mask))
        if valid_count < 100:
            return cls.fallback_to_relative(
                depth_map,
                reason=f"Insufficient overlapping valid reference pixels: found {valid_count}, minimum 100 required."
            )

        d_vals = depth_map[mask].astype(np.float64)
        z_vals = reference_array[mask].astype(np.float64)

        if np.std(d_vals) < 1e-5 or np.std(z_vals) < 1e-5:
            return cls.fallback_to_relative(
                depth_map,
                reason="Reference or depth values have zero variance; cannot perform regression."
            )

        # Least-squares fit: Z = s * d + t
        A = np.vstack([d_vals, np.ones_like(d_vals)]).T
        solution, _, _, _ = np.linalg.lstsq(A, z_vals, rcond=None)
        scale = float(solution[0])
        shift = float(solution[1])

        z_pred = scale * d_vals + shift
        errors = z_pred - z_vals

        mae = float(np.mean(np.abs(errors)))
        rmse = float(np.sqrt(np.mean(errors ** 2)))
        bias = float(np.mean(errors))
        
        r_val, _ = stats.pearsonr(d_vals, z_vals)
        pearson_r = float(r_val) if not np.isnan(r_val) else 0.0

        ss_tot = np.sum((z_vals - np.mean(z_vals)) ** 2)
        ss_res = np.sum(errors ** 2)
        r_squared = float(1.0 - (ss_res / ss_tot)) if ss_tot > 1e-6 else 0.0

        metrics = CalibrationMetrics(
            mae=mae,
            rmse=rmse,
            bias=bias,
            pearson_r=pearson_r,
            r_squared=r_squared,
            sample_count=valid_count
        )

        warnings = []
        limitations = [
            f"Reference alignment based on {valid_count} spatial pixel correspondences.",
            "Linear scale-and-shift does not correct for non-linear optical lens distortion or atmospheric curvature."
        ]

        # Domain semantics distinction (Rule §5 & Requirement 6)
        depth_type = "CALIBRATED_DSM"
        if source_type == CalibrationSourceType.NDSM_GAMUS:
            warnings.append(
                "DOMAIN WARNING: Reference dataset is GAMUS / nDSM. This captures Normalized Digital Surface Model "
                "(height of structures/trees above ground level), NOT absolute elevation above mean sea level."
            )
            limitations.append("Values represent calibrated height above local terrain, not sea-level DSM.")

        # Gating checks
        if rmse > max_rmse_threshold or r_squared < min_r2_threshold:
            rejection = f"Calibration rejected: RMSE ({rmse:.2f}m) exceeds threshold ({max_rmse_threshold:.2f}m) or R2 ({r_squared:.2f}) below ({min_r2_threshold:.2f})."
            warnings.append(rejection)
            return CalibrationResult(
                mode=CalibrationMode.CANDIDATE_METRIC,
                method=CalibrationMethod.SCALE_AND_SHIFT,
                source_type=source_type,
                source_identifier=source_identifier,
                is_metric=False,
                depth_type="RELATIVE_DEPTH",
                calibrated_array=depth_map.astype(np.float32),
                scale_factor=scale,
                shift_offset=shift,
                metrics=metrics,
                warnings=warnings,
                limitations=limitations,
                rejection_reason=rejection
            )

        calibrated_array = (scale * depth_map + shift).astype(np.float32)
        return CalibrationResult(
            mode=CalibrationMode.VALIDATED_METRIC,
            method=CalibrationMethod.SCALE_AND_SHIFT,
            source_type=source_type,
            source_identifier=source_identifier,
            is_metric=True,
            depth_type=depth_type,
            calibrated_array=calibrated_array,
            scale_factor=scale,
            shift_offset=shift,
            metrics=metrics,
            warnings=warnings,
            limitations=limitations,
            rejection_reason=None
        )

    @classmethod
    def calibrate_relative_dsm(
        cls,
        product: Any,
        gcps: Optional[List[GroundControlPoint]] = None,
        reference_raster: Optional[np.ndarray] = None,
        source_type: CalibrationSourceType = CalibrationSourceType.NONE,
        source_identifier: Optional[str] = None,
        nodata_value: Optional[float] = None,
        max_rmse_threshold: float = 15.0,
        min_r2_threshold: float = 0.20,
        strict_raise: bool = False
    ) -> MetricElevationProduct:
        """
        Calibrates a RelativeDSMProduct against Ground Control Points or a reference raster.
        Integrates empirical calibration with geospatial metadata and relative surface products.

        Gating & Safety:
        - If neither GCPs nor reference raster are provided, or if validation fails, safely
          falls back to unitless relative representation (is_metric=False, depth_type="RELATIVE_DSM").
        - If strict_raise is True, raises ValueError upon calibration rejection or missing data.
        """
        calib_result: Optional[CalibrationResult] = None

        if gcps is not None and len(gcps) > 0:
            calib_result = cls.calibrate_with_gcps(
                depth_map=product.array,
                gcps=gcps,
                metadata=product.geo_metadata,
                max_rmse_threshold=max_rmse_threshold,
                min_r2_threshold=min_r2_threshold
            )
        elif reference_raster is not None:
            effective_source = (
                source_type if source_type != CalibrationSourceType.NONE else CalibrationSourceType.REFERENCE_DEM
            )
            calib_result = cls.calibrate_with_reference_raster(
                depth_map=product.array,
                reference_array=reference_raster,
                source_type=effective_source,
                source_identifier=source_identifier or "reference_elevation_raster",
                nodata_value=nodata_value,
                max_rmse_threshold=max_rmse_threshold,
                min_r2_threshold=min_r2_threshold
            )
        else:
            calib_result = cls.fallback_to_relative(
                depth_map=product.array,
                reason="No calibration reference (GCPs or reference raster) provided; maintaining unitless relative surface relief."
            )

        # Enforce strict error raising if requested
        if strict_raise and not calib_result.is_metric:
            raise ValueError(f"Calibration failed: {calib_result.rejection_reason or 'Validation gates not met'}")

        # Enforce exact output semantics:
        # 1. Uncalibrated / rejected: depth_type = "RELATIVE_DSM", units = "unitless_disparity", is_metric = False
        # 2. Calibrated: depth_type = "CALIBRATED_DSM", units = "meters", is_metric = True
        if not calib_result.is_metric:
            depth_type = "RELATIVE_DSM"
            units = "unitless_disparity"
        else:
            depth_type = "CALIBRATED_DSM"
            units = "meters"

        return MetricElevationProduct(
            array=calib_result.calibrated_array,
            depth_type=depth_type,
            units=units,
            is_metric=calib_result.is_metric,
            calibration=calib_result,
            geo_metadata=product.geo_metadata,
            source_relative_dsm=product,
            export_result=None
        )

    @classmethod
    def export_metric_elevation(
        cls,
        product: MetricElevationProduct,
        target_path: Union[str, Path],
        config: Optional[RasterExportConfig] = None
    ) -> ExportResult:
        """
        Exports a MetricElevationProduct to GeoTIFF with rigorous geospatial validation.
        Writes explicit calibration provenance into GeoTIFF tags (scale, shift, RMSE, method).
        """
        target = Path(target_path)
        if config is None:
            config = RasterExportConfig(target_path=target, compress="lzw")
        else:
            config.target_path = target

        # Call RasterIO with explicit calibration parameters
        export_result = RasterIO.export_depth_to_geotiff(
            depth_map=product.array,
            source_metadata=product.geo_metadata,
            config=config,
            depth_type=product.depth_type,
            is_calibrated=product.is_metric
        )

        # Attach calibration provenance tags to GeoTIFF if calibrated
        if product.is_metric and product.calibration is not None:
            try:
                import rasterio
                with rasterio.open(target, "r+") as dst:
                    extra_tags = {
                        "CALIBRATION_MODE": str(product.calibration.mode.value),
                        "CALIBRATION_METHOD": str(product.calibration.method.value),
                        "CALIBRATION_SOURCE": str(product.calibration.source_type.value),
                        "SCALE_FACTOR": f"{product.calibration.scale_factor:.6f}" if product.calibration.scale_factor is not None else "None",
                        "SHIFT_OFFSET": f"{product.calibration.shift_offset:.6f}" if product.calibration.shift_offset is not None else "None",
                    }
                    if product.calibration.metrics:
                        extra_tags["CALIBRATION_RMSE"] = f"{product.calibration.metrics.rmse:.4f}"
                        extra_tags["CALIBRATION_MAE"] = f"{product.calibration.metrics.mae:.4f}"
                        extra_tags["CALIBRATION_R2"] = f"{product.calibration.metrics.r_squared:.4f}"
                    dst.update_tags(**extra_tags)
            except Exception:
                pass

        product.export_result = export_result
        return export_result
