"""
DepthWizard Cross-Platform Unified Application Launcher
=======================================================
Performs pre-flight verification and starts the DepthWizard server
serving the FastAPI backend, ML inference engine, and Three.js 3D frontend.
Strictly adheres to .agents/rules/depthwizard-development.md (No Fake AI).
"""

import sys
import os
import argparse
from pathlib import Path

# Add project root to sys.path
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE_ROOT))

from backend.app.config import settings
from scripts.validate_setup import run_validation

def main():
    parser = argparse.ArgumentParser(description="DepthWizard Unified Launcher")
    parser.add_argument("--host", default=None, help=f"Server host (default: {settings.HOST})")
    parser.add_argument("--port", type=int, default=None, help=f"Server port (default: {settings.PORT})")
    parser.add_argument("--skip-validation", action="store_true", help="Skip pre-flight diagnostic check")
    parser.add_argument("--download-assets", action="store_true", help="Automatically acquire missing model assets")
    args = parser.parse_args()

    host = args.host or settings.HOST
    port = args.port or settings.PORT

    print("=" * 78)
    print("   DEPTHWIZARD SIH 2026: UNIFIED SYSTEM LAUNCHER")
    print("=" * 78)

    # 1. Pre-flight Environment Diagnostic
    if not args.skip_validation:
        status_code = run_validation()
        if status_code != 0:
            print("[ERROR] Environment validation failed. Please fix the above issues before starting.")
            sys.exit(1)

    # 2. Check Model Availability
    if not settings.MODEL_PATH.exists():
        print(f"\n[WARNING] Model weights not found at: {settings.MODEL_PATH}")
        if args.download_assets or "--download-assets" in sys.argv:
            print("[INFO] Initiating automated asset download...")
            from scripts.download_assets import download_model, download_sample_images
            download_model()
            download_sample_images()
        else:
            print("[ACTION REQUIRED] To acquire real model weights, run:")
            print("  python scripts/download_assets.py")
            print("Starting server in degraded mode (model endpoints will return HTTP 503).\n")

    # 3. Display Local Access Endpoints
    print("=" * 78)
    print(f"   STARTING DEPTHWIZARD SERVICE ON {host}:{port}")
    print("=" * 78)
    display_host = "localhost" if host in ("0.0.0.0", "127.0.0.1") else host
    print(f"\n  * Web Application (SPA) : http://{display_host}:{port}/app")
    print(f"  * Interactive API Docs  : http://{display_host}:{port}/docs")
    print(f"  * Alternative API Docs  : http://{display_host}:{port}/redoc")
    print(f"  * Health Check Endpoint : http://{display_host}:{port}/api/v1/health")
    print("\n  Press Ctrl+C to stop the server.\n")

    # 4. Launch Uvicorn
    import uvicorn
    uvicorn.run(
        "backend.app.main:app",
        host=host,
        port=port,
        reload=settings.DEBUG,
        workers=1,
        log_level="info"
    )

if __name__ == "__main__":
    main()
