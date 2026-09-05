"""
Deployment, Configuration, and Packaging Tests
==============================================
Tests environment configuration loading, pre-flight diagnostics,
graceful missing model failure, and frontend distribution integration.
Strictly adheres to .agents/rules/depthwizard-development.md (No Fake AI).
"""

import os
from pathlib import Path
import pytest
from starlette.testclient import TestClient

from backend.app.config import Settings, PROJECT_ROOT, settings
from backend.app.main import app
from scripts.validate_setup import run_validation

client = TestClient(app)

def test_config_defaults_and_resolution():
    """Verify that default paths resolve relative to PROJECT_ROOT without machine-specific hardcoding."""
    cfg = Settings()
    assert cfg.PROJECT_NAME == "DepthWizard SIH 2026"
    assert cfg.TARGET_DEVICE == "CPU"
    assert cfg.HOST == "127.0.0.1"
    assert cfg.PORT == 8000
    assert cfg.MODEL_PATH.is_absolute()
    assert str(PROJECT_ROOT) in str(cfg.MODEL_PATH)
    assert cfg.UPLOAD_DIR.is_absolute()
    assert cfg.OUTPUT_DIR.is_absolute()

def test_config_env_overrides(monkeypatch):
    """Verify that DEPTHWIZARD_ environment variables override configuration."""
    monkeypatch.setenv("DEPTHWIZARD_PORT", "9090")
    monkeypatch.setenv("DEPTHWIZARD_HOST", "0.0.0.0")
    monkeypatch.setenv("DEPTHWIZARD_ONNX_INTRA_OP_THREADS", "4")
    
    cfg = Settings()
    assert cfg.PORT == 9090
    assert cfg.HOST == "0.0.0.0"
    assert cfg.ONNX_INTRA_OP_THREADS == 4

def test_preflight_validation_succeeds():
    """Verify that the diagnostic validator passes on the current environment."""
    exit_code = run_validation()
    assert exit_code == 0

def test_frontend_spa_serving():
    """Verify that the backend properly serves the SPA entry point at /app."""
    resp = client.get("/app")
    assert resp.status_code == 200
    assert "DepthWizard" in resp.text or "<div id=\"root\">" in resp.text

def test_missing_model_graceful_handling(monkeypatch):
    """Verify that missing model checkpoint fails safely with HTTP 503 and actionable guidance."""
    fake_model_path = PROJECT_ROOT / "backend" / "models" / "nonexistent_model.onnx"
    monkeypatch.setattr(settings, "MODEL_PATH", fake_model_path)
    
    # Health endpoint reports degraded
    resp_health = client.get("/api/v1/health")
    assert resp_health.status_code == 200
    assert resp_health.json()["status"] == "degraded"
    assert resp_health.json()["model_loaded"] is False

    # Process endpoint returns HTTP 503 with actionable message
    sample_tif = PROJECT_ROOT / "tests" / "data" / "sample_geotiff.tif"
    if sample_tif.exists():
        with open(sample_tif, "rb") as f:
            resp_proc = client.post(
                "/api/v1/process",
                files={"file": ("sample.tif", f.read(), "image/tiff")}
            )
        assert resp_proc.status_code == 503
        assert "download_assets.py" in resp_proc.json()["detail"]
