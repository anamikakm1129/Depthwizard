import pytest
from pathlib import Path
import numpy as np

def test_environment_packages():
    import onnxruntime as ort
    import rasterio
    import PIL
    import cv2
    assert "CPUExecutionProvider" in ort.get_available_providers()
    assert rasterio.__version__ is not None

def test_sample_image_loading():
    from PIL import Image
    path = Path("tests/data/sample_aerial.tif")
    assert path.exists(), "Sample aerial image missing"
    with Image.open(path) as img:
        assert img.size[0] > 0 and img.size[1] > 0

def test_geotiff_metadata_preservation():
    import rasterio
    path = Path("tests/data/sample_geotiff.tif")
    assert path.exists(), "Sample GeoTIFF missing"
    with rasterio.open(path) as src:
        assert src.crs is not None, "GeoTIFF must have valid CRS"
        assert src.transform is not None, "GeoTIFF must have valid Affine transform"
        assert src.width > 0 and src.height > 0
        data = src.read(1)
        assert data.size > 0

def test_real_model_inference_signature():
    import onnxruntime as ort
    model_path = Path("backend/models/depth_anything_v2_vits_int8.onnx")
    assert model_path.exists(), "Model file missing"
    
    session = ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])
    inputs = session.get_inputs()
    outputs = session.get_outputs()
    assert len(inputs) == 1
    assert len(outputs) == 1
    
    # Run test tensor
    dummy_input = np.zeros((1, 3, 518, 518), dtype=np.float32)
    output = session.run([outputs[0].name], {inputs[0].name: dummy_input})[0]
    assert output.shape[0] == 1
    assert output.ndim in (3, 4)
    assert not np.isnan(output).any()
