"""
Evaluation API Route
====================
Provides endpoints for rigorous, ground-truth-based quantitative evaluation.
Strictly adheres to .agents/rules/depthwizard-development.md (No Fake AI).
"""

import os
import uuid
import shutil
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status

from backend.app.config import settings
from backend.app.evaluation.schemas import EvaluationResponse
from backend.app.evaluation.evaluator import SceneEvaluator

router = APIRouter(tags=["Evaluation & Accuracy Assessment"])

ALLOWED_RASTER_EXTS = {".tif", ".tiff"}

def _validate_magic_bytes(content: bytes) -> bool:
    # TIFF magic bytes: Little-endian (II*\x00) or Big-endian (MM\x00*)
    return content.startswith(b"II*\x00") or content.startswith(b"MM\x00*")

@router.post("/evaluate", response_model=EvaluationResponse)
async def evaluate_prediction(
    job_id: str = Form(..., description="Job ID of the predicted raster to evaluate"),
    reference_file: UploadFile = File(..., description="Real reference elevation GeoTIFF (e.g., DEM/LiDAR)"),
    is_metric: bool = Form(False, description="Whether the prediction was calibrated to meters")
):
    """
    Evaluate a predicted elevation raster against a real reference GeoTIFF.
    Strictly adheres to Rule Section 2: Zero fabricated metrics or placeholder accuracy claims.
    """
    # 1. Locate predicted raster
    safe_job_id = Path(job_id).name
    pred_gtiff_path = settings.OUTPUT_DIR / f"{safe_job_id}_depth.tif"

    if not pred_gtiff_path.exists() or not pred_gtiff_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Predicted raster for job '{safe_job_id}' not found at {pred_gtiff_path}."
        )

    # 2. Validate Reference File
    ext = Path(reference_file.filename or "").suffix.lower()
    if ext not in ALLOWED_RASTER_EXTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Reference file must be a GeoTIFF raster (.tif, .tiff). Got '{ext}'."
        )

    header = await reference_file.read(8)
    await reference_file.seek(0)
    if not _validate_magic_bytes(header):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reference file failed TIFF magic bytes validation; not a valid GeoTIFF."
        )

    # 3. Save reference file to upload directory
    ref_filename = f"ref_{uuid.uuid4()}_{Path(reference_file.filename or 'ref.tif').name}"
    ref_path = settings.UPLOAD_DIR / ref_filename

    try:
        with open(ref_path, "wb") as f_out:
            shutil.copyfileobj(reference_file.file, f_out)

        # 4. Execute Scene Evaluation
        eval_response = SceneEvaluator.evaluate_rasters(
            predicted_raster_path=pred_gtiff_path,
            reference_raster_path=ref_path,
            job_id=safe_job_id,
            is_metric=is_metric,
            depth_type="CALIBRATED_DSM" if is_metric else "RELATIVE_DEPTH"
        )
        return eval_response

    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Evaluation calculation failed: {str(ve)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Scene evaluation failed: {str(e)}"
        )
    finally:
        # Clean up temporary uploaded reference file
        if ref_path.exists():
            try:
                os.remove(ref_path)
            except OSError:
                pass

