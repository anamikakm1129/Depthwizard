from pathlib import Path
from typing import Set, List, Union
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="DEPTHWIZARD_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    PROJECT_NAME: str = "DepthWizard SIH 2026"
    VERSION: str = "1.0.0"
    API_PREFIX: str = "/api/v1"
    
    # Server Configuration
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    DEBUG: bool = False
    
    # Target Hardware & Processing Configuration
    TARGET_DEVICE: str = "CPU"
    ONNX_INTRA_OP_THREADS: int = 2
    MODEL_PATH: Path = PROJECT_ROOT / "backend" / "models" / "depth_anything_v2_vits_int8.onnx"
    MODEL_INPUT_SIZE: int = 518
    
    # File Storage Paths
    UPLOAD_DIR: Path = PROJECT_ROOT / "backend" / "uploads"
    OUTPUT_DIR: Path = PROJECT_ROOT / "backend" / "outputs"
    MAX_UPLOAD_SIZE_MB: int = 250
    
    # Allowed optical image extensions
    ALLOWED_EXTENSIONS: Set[str] = {".tif", ".tiff", ".png", ".jpg", ".jpeg"}

    # CORS Settings
    CORS_ORIGINS: List[str] = ["*"]

    @field_validator("MODEL_PATH", "UPLOAD_DIR", "OUTPUT_DIR", mode="before")
    @classmethod
    def resolve_paths(cls, v: Union[str, Path]) -> Path:
        p = Path(v)
        if not p.is_absolute():
            return (PROJECT_ROOT / p).resolve()
        return p.resolve()

settings = Settings()
settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
settings.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
