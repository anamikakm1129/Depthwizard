from fastapi import APIRouter
from backend.app.config import settings
from backend.app.api.schemas import HealthResponse, ModelInfoResponse

router = APIRouter(tags=["Health & Status"])

@router.get("/health", response_model=HealthResponse)
async def health_check():
    model_exists = settings.MODEL_PATH.exists()
    return HealthResponse(
        status="ok" if model_exists else "degraded",
        model_name="depth_anything_v2_vits_int8",
        model_loaded=model_exists,
        execution_provider="CPUExecutionProvider",
        device=settings.TARGET_DEVICE,
        version=settings.VERSION
    )

@router.get("/model/info", response_model=ModelInfoResponse)
async def model_info():
    return ModelInfoResponse(
        model_name="Depth Anything V2 Small (INT8 ONNX)",
        model_path=str(settings.MODEL_PATH),
        input_resolution=settings.MODEL_INPUT_SIZE,
        license="Apache-2.0",
        output_type="Monocular Relative Disparity [0.0, 1.0]",
        target_hardware="Intel Core i3-6006U (Pure CPU, AVX2)",
        description=(
            "Optimized 24.8M parameter Vision Transformer quantized to INT8. "
            "Produces dense monocular relative depth. Requires external calibration "
            "reference to produce metric elevation."
        )
    )
