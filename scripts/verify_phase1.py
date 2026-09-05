import sys
from pathlib import Path
import numpy as np

def verify_all():
    print("==================================================")
    print("   DEPTHWIZARD PHASE 1 VERIFICATION HARNESS      ")
    print("==================================================")
    
    # 1. Environment & Packages
    print("\n[CHECK 1] Python & Core Packages...")
    import onnxruntime as ort
    import rasterio
    from PIL import Image
    import cv2
    print(f" - Python: {sys.version.split()[0]}")
    print(f" - ONNX Runtime: {ort.__version__} (Providers: {ort.get_available_providers()})")
    print(f" - Rasterio: {rasterio.__version__} (GDAL: {rasterio.__gdal_version__})")
    print(f" - OpenCV: {cv2.__version__}")
    print(f" - Pillow: {Image.__version__}")
    assert "CPUExecutionProvider" in ort.get_available_providers(), "CPUExecutionProvider missing!"
    print(" -> Environment verification PASSED.")

    # 2. Image Loading
    print("\n[CHECK 2] Sample Image Loading...")
    data_dir = Path("tests/data")
    aerial_path = data_dir / "sample_aerial.tif"
    assert aerial_path.exists(), f"Missing aerial sample at {aerial_path}"
    with Image.open(aerial_path) as img:
        print(f" - Aerial Image: {img.format} {img.size} mode={img.mode} ({aerial_path.stat().st_size / 1024:.1f} KB)")
        assert img.size[0] > 0 and img.size[1] > 0
    print(" -> Standard image loading PASSED.")

    # 3. GeoTIFF Geospatial Metadata Preservation
    print("\n[CHECK 3] Geospatial Rasterio Loading & Metadata Verification...")
    geotiff_path = data_dir / "sample_geotiff.tif"
    assert geotiff_path.exists(), f"Missing GeoTIFF sample at {geotiff_path}"
    with rasterio.open(geotiff_path) as src:
        print(f" - Dimensions: width={src.width}, height={src.height}, count={src.count}")
        print(f" - CRS: {src.crs}")
        print(f" - Transform:\n{src.transform}")
        print(f" - Bounds: {src.bounds}")
        print(f" - Nodata: {src.nodata}")
        assert src.crs is not None, "GeoTIFF has no valid CRS!"
        assert src.transform is not None, "GeoTIFF has no affine transform!"
        assert src.count >= 1, "GeoTIFF has no raster bands!"
        sample_data = src.read(1)
        print(f" - Band 1 data shape={sample_data.shape}, dtype={sample_data.dtype}, min={sample_data.min()}, max={sample_data.max()}")
    print(" -> Geospatial metadata verification PASSED.")

    # 4. Model Loading & Real Inference Execution (No Fake AI)
    print("\n[CHECK 4] ONNX Model Loading & Real Inference...")
    model_path = Path("backend/models/depth_anything_v2_vits_int8.onnx")
    assert model_path.exists(), f"Model file missing at {model_path}"
    print(f" - Model file exists: {model_path} ({model_path.stat().st_size / (1024*1024):.2f} MB)")
    
    session_options = ort.SessionOptions()
    session_options.intra_op_num_threads = 2
    session_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    session = ort.InferenceSession(str(model_path), sess_options=session_options, providers=["CPUExecutionProvider"])
    
    inputs = session.get_inputs()
    outputs = session.get_outputs()
    print(f" - Model Input: name={inputs[0].name}, shape={inputs[0].shape}, type={inputs[0].type}")
    print(f" - Model Output: name={outputs[0].name}, shape={outputs[0].shape}, type={outputs[0].type}")
    
    # Preprocess real aerial image
    with Image.open(aerial_path) as img:
        rgb_img = img.convert("RGB").resize((518, 518), Image.Resampling.BICUBIC)
        arr = np.array(rgb_img, dtype=np.float32) / 255.0
        mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
        std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
        norm_arr = (arr - mean) / std
        input_tensor = np.transpose(norm_arr, (2, 0, 1))[np.newaxis, ...] # [1, 3, 518, 518]
    
    import time
    t0 = time.perf_counter()
    output = session.run([outputs[0].name], {inputs[0].name: input_tensor})[0]
    elapsed = time.perf_counter() - t0
    
    print(f" - Inference executed in: {elapsed:.3f} seconds on CPU")
    print(f" - Output tensor shape: {output.shape}, dtype: {output.dtype}")
    print(f" - Output min={output.min():.4f}, max={output.max():.4f}, mean={output.mean():.4f}, std={output.std():.4f}")
    
    # Strict validation against fake or trivial output
    assert not np.isnan(output).any(), "Output tensor contains NaNs!"
    assert not np.isinf(output).any(), "Output tensor contains Infs!"
    assert output.std() > 0.01, "Output tensor has zero/trivial variance! (Model may be defective or mock)"
    print(" -> Real Model Inference PASSED.")
    
    print("\n==================================================")
    print("   ALL PHASE 1 VERIFICATIONS COMPLETED WITH SUCCESS")
    print("==================================================")

if __name__ == "__main__":
    verify_all()
