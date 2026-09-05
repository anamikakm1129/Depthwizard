"""
DepthWizard Environment & System Validation Tool
================================================
Conducts pre-flight diagnostics of the environment, hardware capabilities,
geospatial libraries, and model asset status.
Strictly adheres to .agents/rules/depthwizard-development.md (No Fake AI).
"""

import sys
import os
import platform
import shutil
from pathlib import Path

# Add project root to sys.path
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE_ROOT))

def run_validation():
    print("=" * 78)
    print("   DEPTHWIZARD SIH 2026: SYSTEM & ENVIRONMENT PRE-FLIGHT VALIDATION")
    print("=" * 78)

    all_passed = True
    warnings = []

    # 1. Python Environment
    print("\n[1/6] Python Runtime...")
    py_ver = sys.version_info
    py_str = f"{py_ver.major}.{py_ver.minor}.{py_ver.micro}"
    if py_ver.major == 3 and py_ver.minor >= 10:
        print(f"  [PASS] Python {py_str} ({platform.architecture()[0]})")
    else:
        print(f"  [FAIL] Python {py_str} is unsupported. Python 3.10 or 3.11 is required.")
        all_passed = False

    # 2. Critical Dependency Audit
    print("\n[2/6] Dependency Verification...")
    required_packages = [
        ("fastapi", "FastAPI web framework"),
        ("uvicorn", "ASGI production server"),
        ("pydantic", "Data validation"),
        ("pydantic_settings", "Settings management"),
        ("onnxruntime", "ONNX CPU inference runtime"),
        ("numpy", "Numerical tensor operations"),
        ("scipy", "Scientific & calibration computing"),
        ("PIL", "Image I/O (Pillow)"),
        ("cv2", "Computer vision (OpenCV)"),
        ("rasterio", "GDAL Geospatial raster I/O"),
    ]

    for pkg_name, desc in required_packages:
        try:
            mod = __import__(pkg_name)
            ver = getattr(mod, "__version__", "installed")
            print(f"  [PASS] {pkg_name} ({ver}) - {desc}")
        except ImportError:
            print(f"  [FAIL] {pkg_name} is missing! ({desc})")
            all_passed = False

    # 3. Geospatial & GDAL Bindings Check
    print("\n[3/6] Geospatial Engine (GDAL/PROJ)...")
    try:
        import rasterio
        from rasterio.crs import CRS
        test_crs = CRS.from_epsg(4326)
        print(f"  [PASS] RasterIO {rasterio.__version__} with bundled GDAL bindings operational")
        print(f"  [PASS] EPSG authority database accessible (tested {test_crs.to_string()})")
    except Exception as e:
        print(f"  [FAIL] Geospatial subsystem failed: {e}")
        all_passed = False

    # 4. Target Hardware & Telemetry
    print("\n[4/6] Target Hardware & Resource Assessment...")
    cpu_name = platform.processor() or platform.machine()
    logical_cpus = os.cpu_count() or 1
    print(f"  [INFO] Platform: {platform.system()} {platform.release()} ({platform.machine()})")
    print(f"  [INFO] Processor: {cpu_name}")
    print(f"  [INFO] Logical Cores: {logical_cpus}")

    # Pure CPU optimization assessment
    if "Intel" in cpu_name or "AMD" in cpu_name or platform.machine() in ("AMD64", "x86_64"):
        print("  [INFO] Architecture: x86_64 / AVX2 capable")
    elif "arm" in platform.machine().lower() or "apple" in cpu_name.lower():
        print("  [INFO] Architecture: ARM64 (Apple Silicon / ARM NEON capable)")

    try:
        from backend.app.config import settings
        print(f"  [PASS] Configured ONNX intra-op threads: {settings.ONNX_INTRA_OP_THREADS}")
        print(f"  [PASS] Target execution provider: {settings.TARGET_DEVICE}")
    except Exception as e:
        print(f"  [FAIL] Configuration loading error: {e}")
        all_passed = False

    # 5. Real Model Asset Verification (Rule Section 2: No Fake AI)
    print("\n[5/6] Model Checkpoint & Asset Integrity...")
    from backend.app.config import settings
    model_path = settings.MODEL_PATH

    if model_path.exists():
        size_mb = model_path.stat().st_size / (1024 * 1024)
        print(f"  [PASS] Model checkpoint verified: {model_path.name} ({size_mb:.2f} MB)")
        try:
            import onnxruntime as ort
            sess_opts = ort.SessionOptions()
            sess_opts.intra_op_num_threads = settings.ONNX_INTRA_OP_THREADS
            sess = ort.InferenceSession(str(model_path), sess_opts, providers=["CPUExecutionProvider"])
            inputs = [inp.name for inp in sess.get_inputs()]
            outputs = [out.name for out in sess.get_outputs()]
            print(f"  [PASS] ONNX Runtime session successfully created")
            print(f"  [INFO] Input tensor: {inputs}, Output tensor: {outputs}")
        except Exception as e:
            print(f"  [FAIL] ONNX model corrupted or invalid: {e}")
            all_passed = False
    else:
        print(f"  [WARN] Model checkpoint NOT FOUND at: {model_path}")
        print(f"  [ACTION REQUIRED] Run 'python scripts/download_assets.py' to acquire official weights.")
        warnings.append("Model weights missing. Server will run in degraded mode until downloaded.")

    # 6. Frontend Build Distribution
    print("\n[6/6] Frontend Distribution...")
    frontend_dist = WORKSPACE_ROOT / "frontend" / "dist"
    index_file = frontend_dist / "index.html"
    if index_file.exists():
        print(f"  [PASS] Production frontend build found at {frontend_dist}")
        print(f"  [INFO] SPA ready for single-origin serving at http://127.0.0.1:8000/app")
    else:
        print(f"  [WARN] Frontend build not found at {frontend_dist}")
        print(f"  [ACTION REQUIRED] Run 'cd frontend && npm install && npm run build'")
        warnings.append("Frontend dist missing. Single-origin SPA will not be served.")

    # Final Summary
    print("\n" + "=" * 78)
    if all_passed and not warnings:
        print("   PRE-FLIGHT STATUS: ALL SYSTEMS OPERATIONAL (READY FOR DEPLOYMENT)")
    elif all_passed:
        print("   PRE-FLIGHT STATUS: ENVIRONMENT READY WITH WARNINGS:")
        for w in warnings:
            print(f"   - {w}")
    else:
        print("   PRE-FLIGHT STATUS: CRITICAL ISSUES DETECTED. FIX FAILURES ABOVE.")
    print("=" * 78 + "\n")

    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(run_validation())
