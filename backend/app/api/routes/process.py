import os
import uuid
import json
import time
from pathlib import Path
from typing import Optional, List
import cv2
import numpy as np
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status
from fastapi.responses import FileResponse

from backend.app.config import settings
from backend.app.inference.pipeline import DepthPipeline
from backend.app.geospatial.raster_io import RasterIO
from backend.app.geospatial.schemas import RasterExportConfig
from backend.app.geospatial.relative_dsm import RelativeDSMGenerator
from backend.app.geospatial.calibration import MetricCalibrator
from backend.app.geospatial.calibration_schemas import GroundControlPoint, MetricElevationProduct
from backend.app.mesh.terrain import TerrainMeshGenerator
from backend.app.api.schemas import (
    ProcessImageResponse,
    ImageMetadataResponse,
    ValidationResponse,
    CalibrationResponse,
    CalibrationMetricsResponse,
    ReliefMetricsResponse,
    GCPInput
)

router = APIRouter(tags=["Image Processing & Inference"])

# Singleton pipeline instance initialized on demand
_pipeline_instance: Optional[DepthPipeline] = None

def get_pipeline() -> DepthPipeline:
    global _pipeline_instance
    if not settings.MODEL_PATH.exists():
        _pipeline_instance = None
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Model checkpoint not found at {settings.MODEL_PATH}. Run 'python scripts/download_assets.py' to acquire official verified weights."
        )
    if _pipeline_instance is None or _pipeline_instance.model_path != settings.MODEL_PATH:
        _pipeline_instance = DepthPipeline(
            model_path=settings.MODEL_PATH,
            target_size=settings.MODEL_INPUT_SIZE,
            intra_op_threads=settings.ONNX_INTRA_OP_THREADS
        )
    return _pipeline_instance

def validate_magic_bytes(header: bytes, ext: str) -> bool:
    """Verifies file header bytes match the claimed image format."""
    if ext in (".tif", ".tiff"):
        return header[:4] in (b"II*\x00", b"MM\x00*", b"II+\x00", b"MM\x00+")
    elif ext == ".png":
        return header[:8] == b"\x89PNG\r\n\x1a\n"
    elif ext in (".jpg", ".jpeg"):
        return header[:3] == b"\xFF\xD8\xFF"
    return False

@router.post("/process", response_model=ProcessImageResponse)
async def process_image(
    file: UploadFile = File(...),
    gcps_json: Optional[str] = Form(None)
):
    """
    Executes real monocular depth estimation and optional metric calibration.
    Strictly forbids fake predictions or fabricated coordinates.
    """
    job_id = str(uuid.uuid4())
    filename = Path(file.filename).name
    ext = Path(filename).suffix.lower()

    if ext not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported format '{ext}'. Allowed extensions: {list(settings.ALLOWED_EXTENSIONS)}"
        )

    # Read header bytes for magic validation
    header = await file.read(16)
    if not validate_magic_bytes(header, ext):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File content does not match image format header (magic bytes check failed)."
        )

    # Rewind and stream to disk
    await file.seek(0)
    job_upload_dir = settings.UPLOAD_DIR / job_id
    job_upload_dir.mkdir(parents=True, exist_ok=True)
    input_file_path = job_upload_dir / filename

    content = await file.read()
    if len(content) > settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size exceeds maximum allowed size of {settings.MAX_UPLOAD_SIZE_MB} MB."
        )

    with open(input_file_path, "wb") as f:
        f.write(content)

    # 1. Execute Real Inference Pipeline
    pipeline = get_pipeline()
    try:
        pipeline_output = pipeline.process(input_file_path)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Inference execution failed: {str(e)}"
        )

    # Extract source spatial metadata
    source_meta = RasterIO.extract_metadata(input_file_path)

    # 2. Relative DSM Generation
    t_rdsm_start = time.perf_counter()
    relative_dsm_product = RelativeDSMGenerator.generate(
        relative_depth=pipeline_output.relative_depth,
        metadata=source_meta
    )
    t_rdsm = time.perf_counter() - t_rdsm_start

    # 3. Calibration Engine
    t_calib_start = time.perf_counter()
    parsed_gcps: List[GroundControlPoint] = []
    if gcps_json:
        try:
            raw_gcps = json.loads(gcps_json)
            for item in raw_gcps:
                parsed_gcps.append(GroundControlPoint(
                    x_pixel=float(item["x_pixel"]),
                    y_pixel=float(item["y_pixel"]),
                    z_elevation=float(item["z_elevation"]),
                    x_geo=float(item["x_geo"]) if item.get("x_geo") is not None else None,
                    y_geo=float(item["y_geo"]) if item.get("y_geo") is not None else None,
                    point_id=item.get("point_id"),
                    description=item.get("description")
                ))
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid GCPs JSON format: {str(e)}"
            )

    metric_product: MetricElevationProduct = relative_dsm_product.calibrate(
        gcps=parsed_gcps if parsed_gcps else None
    )
    calib_result = metric_product.calibration
    t_calibration = time.perf_counter() - t_calib_start

    # 4. Export Output GeoTIFF via MetricCalibrator
    output_geotiff_name = f"{job_id}_depth.tif"
    output_geotiff_path = settings.OUTPUT_DIR / output_geotiff_name
    export_cfg = RasterExportConfig(target_path=output_geotiff_path, compress="lzw")

    try:
        MetricCalibrator.export_metric_elevation(
            product=metric_product,
            target_path=output_geotiff_path,
            config=export_cfg
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"GeoTIFF export failed: {str(e)}"
        )

    # 5. Generate Visual Colormap Preview (PNG)
    output_preview_name = f"{job_id}_preview.png"
    output_preview_path = settings.OUTPUT_DIR / output_preview_name
    norm_disp = relative_dsm_product.array
    disp_uint8 = (norm_disp * 255.0).astype(np.uint8)
    colormap_img = cv2.applyColorMap(disp_uint8, cv2.COLORMAP_VIRIDIS)
    cv2.imwrite(str(output_preview_path), colormap_img)

    # 6. Generate 3D Terrain Mesh (Wavefront OBJ)
    t_mesh_start = time.perf_counter()
    output_mesh_name = f"{job_id}_mesh.obj"
    output_mesh_path = settings.OUTPUT_DIR / output_mesh_name
    terrain_mesh = TerrainMeshGenerator.generate_mesh(
        elevation_map=metric_product.array,
        max_resolution=256,
        vertical_scale=1.0 if metric_product.is_metric else 25.0,
        is_metric=metric_product.is_metric
    )
    TerrainMeshGenerator.export_to_obj(
        mesh=terrain_mesh,
        filepath=output_mesh_path,
        texture_name=output_preview_name
    )
    t_mesh = time.perf_counter() - t_mesh_start

    # Timing metrics aggregation
    timings = dict(pipeline_output.timing)
    timings["relative_dsm_seconds"] = t_rdsm
    timings["calibration_seconds"] = t_calibration
    timings["mesh_seconds"] = t_mesh
    timings["total_seconds"] += (t_rdsm + t_calibration + t_mesh)

    # Format Calibration Response
    calib_metrics_resp = None
    if calib_result.metrics:
        m = calib_result.metrics
        calib_metrics_resp = CalibrationMetricsResponse(
            mae=m.mae,
            rmse=m.rmse,
            bias=m.bias,
            pearson_r=m.pearson_r,
            r_squared=m.r_squared,
            sample_count=m.sample_count
        )

    calib_resp = CalibrationResponse(
        mode=calib_result.mode.value,
        method=calib_result.method.value,
        source_type=calib_result.source_type.value,
        source_identifier=calib_result.source_identifier,
        is_metric=calib_result.is_metric,
        depth_type=calib_result.depth_type,
        scale_factor=calib_result.scale_factor,
        shift_offset=calib_result.shift_offset,
        metrics=calib_metrics_resp,
        warnings=calib_result.warnings,
        limitations=calib_result.limitations,
        rejection_reason=calib_result.rejection_reason
    )

    # Format Relief Metrics
    rm = relative_dsm_product.metrics
    relief_metrics_resp = ReliefMetricsResponse(
        min_value=rm.min_value,
        max_value=rm.max_value,
        mean_value=rm.mean_value,
        std_value=rm.std_value,
        relief_range=rm.relief_range,
        roughness_iqr=rm.roughness_iqr,
        p10=rm.p10,
        p50=rm.p50,
        p90=rm.p90,
        valid_pixel_count=rm.valid_pixel_count
    )

    v = pipeline_output.validation
    val_resp = ValidationResponse(
        is_valid=v.is_valid,
        has_nans=v.has_nans,
        has_infs=v.has_infs,
        is_constant=v.is_constant,
        min_value=v.min_value,
        max_value=v.max_value,
        mean_value=v.mean_value,
        std_value=v.std_value,
        message=v.message
    )

    meta_resp = ImageMetadataResponse(
        original_height=source_meta.height,
        original_width=source_meta.width,
        channels=source_meta.count,
        format=source_meta.driver,
        has_georeference=source_meta.has_georeference,
        crs=source_meta.crs_string,
        transform=source_meta.transform,
        bounds=source_meta.bounds,
        resolution=source_meta.resolution,
        nodata=source_meta.nodata
    )

    return ProcessImageResponse(
        job_id=job_id,
        status="completed",
        depth_type=metric_product.depth_type,
        units=metric_product.units,
        is_metric=metric_product.is_metric,
        input_metadata=meta_resp,
        validation=val_resp,
        relief_metrics=relief_metrics_resp,
        calibration=calib_resp,
        timings=timings,
        geotiff_download_url=f"/api/v1/download/{output_geotiff_name}",
        preview_png_download_url=f"/api/v1/download/{output_preview_name}",
        mesh_download_url=f"/api/v1/download/{output_mesh_name}"
    )

@router.get("/download/{filename}")
async def download_file(filename: str):
    """
    Secure file download endpoint with path traversal prevention.
    """
    safe_name = Path(filename).name
    target_file = settings.OUTPUT_DIR / safe_name

    if not target_file.exists() or not target_file.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Requested output file not found."
        )

    # Determine media type
    # Determine media type accurately
    ext = target_file.suffix.lower()
    media_type = "image/tiff" if ext in (".tif", ".tiff") else "image/png"
    if ext in (".tif", ".tiff"):
        media_type = "image/tiff"
    elif ext == ".obj":
        media_type = "model/obj"
    elif ext == ".mtl":
        media_type = "text/plain"
    elif ext == ".json":
        media_type = "application/json"
    else:
        media_type = "image/png"

    return FileResponse(target_file, media_type=media_type, filename=safe_name)
