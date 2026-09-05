import os
import sys
import time
from pathlib import Path
import numpy as np

# Ensure project root in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.inference.pipeline import DepthPipeline

def get_process_memory_mb() -> float:
    """Returns the current process Working Set memory in megabytes."""
    try:
        import psutil
        process = psutil.Process(os.getpid())
        return process.memory_info().rss / (1024 * 1024)
    except ImportError:
        # Fallback to Windows ctypes API if psutil not installed
        try:
            import ctypes
            from ctypes import wintypes
            class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
                _fields_ = [
                    ('cb', wintypes.DWORD),
                    ('PageFaultCount', wintypes.DWORD),
                    ('PeakWorkingSetSize', ctypes.c_size_t),
                    ('WorkingSetSize', ctypes.c_size_t),
                    ('QuotaPeakPagedPoolUsage', ctypes.c_size_t),
                    ('QuotaPagedPoolUsage', ctypes.c_size_t),
                    ('QuotaPeakNonPagedPoolUsage', ctypes.c_size_t),
                    ('QuotaNonPagedPoolUsage', ctypes.c_size_t),
                    ('PagefileUsage', ctypes.c_size_t),
                    ('PeakPagefileUsage', ctypes.c_size_t),
                ]
            counters = PROCESS_MEMORY_COUNTERS()
            counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
            handle = ctypes.windll.kernel32.GetCurrentProcess()
            if ctypes.windll.psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
                return counters.WorkingSetSize / (1024 * 1024)
        except Exception:
            pass
    return 0.0

def run_benchmark():
    print("==========================================================")
    print("   DEPTHWIZARD PHASE 2 REAL MODEL & PIPELINE BENCHMARK    ")
    print("==========================================================")

    model_path = PROJECT_ROOT / "backend" / "models" / "depth_anything_v2_vits_int8.onnx"
    assert model_path.exists(), f"Model missing: {model_path}"

    initial_mem = get_process_memory_mb()
    print(f"Process initial memory: {initial_mem:.2f} MB")

    t_init_start = time.perf_counter()
    pipeline = DepthPipeline(model_path=model_path, target_size=518, intra_op_threads=2)
    t_init = time.perf_counter() - t_init_start
    print(f"Pipeline & ONNX session initialized in: {t_init:.3f} s")
    post_init_mem = get_process_memory_mb()
    print(f"Process memory post model-load: {post_init_mem:.2f} MB (Delta: {post_init_mem - initial_mem:.2f} MB)")

    test_images = [
        ("Aerial Raster (High-Res)", PROJECT_ROOT / "tests" / "data" / "sample_aerial.tif"),
        ("Satellite GeoTIFF (Georeferenced)", PROJECT_ROOT / "tests" / "data" / "sample_geotiff.tif")
    ]

    for label, img_path in test_images:
        print(f"\n--- Testing: {label} ---")
        print(f"Path: {img_path}")
        assert img_path.exists(), f"Image missing: {img_path}"

        # Run pipeline
        mem_before = get_process_memory_mb()
        output = pipeline.process(img_path)
        mem_after = get_process_memory_mb()

        timing = output.timing
        val = output.validation
        meta = output.metadata

        print(f"Original Dimensions: {output.original_shape[1]} x {output.original_shape[0]} (WxH)")
        print(f"Georeference Flag: {meta.has_georeference}")
        if meta.has_georeference:
            print(f" - CRS: {meta.crs}")
            print(f" - Affine Transform: {meta.transform[:6]}")
        print(f"Output Dimensions: {output.relative_depth.shape[1]} x {output.relative_depth.shape[0]} (WxH)")
        print(f"Output Depth Type: {output.depth_type} (Strictly unitless disparity)")
        print(f"Validation Report:")
        print(f" - Is Valid: {val.is_valid}")
        print(f" - Range: [{val.min_value:.4f}, {val.max_value:.4f}]")
        print(f" - Mean: {val.mean_value:.4f}, StdDev: {val.std_value:.4f}")
        print(f" - NaN/Inf: has_nan={val.has_nans}, has_inf={val.has_infs}")
        print(f" - Trivial/Constant Output: {val.is_constant}")
        print(f"Timing Breakdown:")
        print(f" - Preprocessing:  {timing['preprocessing_seconds']*1000:.1f} ms ({timing['preprocessing_seconds']:.4f} s)")
        print(f" - Real Inference: {timing['inference_seconds']*1000:.1f} ms ({timing['inference_seconds']:.4f} s)")
        print(f" - Postprocessing: {timing['postprocessing_seconds']*1000:.1f} ms ({timing['postprocessing_seconds']:.4f} s)")
        print(f" - Total End-to-End: {timing['total_seconds']:.4f} s")
        print(f"Peak Working Set Memory: {mem_after:.2f} MB (Delta: {mem_after - mem_before:.2f} MB)")

        assert val.is_valid, f"Validation failed: {val.message}"
        assert output.depth_type == "RELATIVE_DEPTH", "Violated Rule §5: Depth type must be RELATIVE_DEPTH"

    print("\n--- Stability & Repeatability Check (3 Consecutive Inferences) ---")
    sample_path = test_images[0][1]
    durations = []
    for i in range(3):
        t0 = time.perf_counter()
        res = pipeline.process(sample_path)
        dt = time.perf_counter() - t0
        durations.append(dt)
        print(f"Run {i+1}: {dt:.3f} s (Inference: {res.timing['inference_seconds']:.3f} s, StdDev: {res.validation.std_value:.4f})")
    
    print(f"Mean total latency: {np.mean(durations):.3f} s (Std: {np.std(durations):.3f} s)")
    print("\n==========================================================")
    print("   PHASE 2 BENCHMARK & PIPELINE VERIFICATION PASSED       ")
    print("==========================================================")

if __name__ == "__main__":
    run_benchmark()
