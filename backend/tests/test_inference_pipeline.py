import pytest
from pathlib import Path
import numpy as np

from backend.app.inference.schemas import ImageMetadata, PreprocessedInput, RawInferenceResult
from backend.app.inference.preprocessing import Preprocessor
from backend.app.inference.engine import DepthInferenceEngine
from backend.app.inference.postprocessing import Postprocessor
from backend.app.inference.validation import OutputValidator
from backend.app.inference.pipeline import DepthPipeline

DATA_DIR = Path("tests/data")
MODEL_PATH = Path("backend/models/depth_anything_v2_vits_int8.onnx")

def test_preprocessor_with_numpy_array():
    pre = Preprocessor(target_size=518)
    dummy = np.random.randint(0, 255, (300, 400, 3), dtype=np.uint8)
    prep = pre.preprocess(dummy)
    assert prep.tensor.shape == (1, 3, 518, 518)
    assert prep.tensor.dtype == np.float32
    assert prep.original_dimensions == (300, 400)
    assert prep.model_dimensions == (518, 518)

def test_preprocessor_with_geotiff():
    pre = Preprocessor(target_size=518)
    geotiff_path = DATA_DIR / "sample_geotiff.tif"
    assert geotiff_path.exists()
    
    prep = pre.preprocess(geotiff_path)
    assert prep.tensor.shape == (1, 3, 518, 518)
    assert prep.metadata.has_georeference is True
    assert prep.metadata.crs is not None
    assert prep.metadata.transform is not None

def test_engine_missing_model_fails_hard():
    with pytest.raises(FileNotFoundError):
        DepthInferenceEngine(model_path="nonexistent_model.onnx")

def test_engine_real_inference_execution():
    assert MODEL_PATH.exists()
    engine = DepthInferenceEngine(model_path=MODEL_PATH, intra_op_threads=2)
    pre = Preprocessor(target_size=518)
    prep = pre.preprocess(DATA_DIR / "sample_geotiff.tif")
    
    raw = engine.infer(prep)
    assert raw.inference_time_seconds > 0.0
    assert raw.model_name == "depth_anything_v2_vits_int8"
    assert raw.raw_depth.ndim in (3, 4)
    assert not np.isnan(raw.raw_depth).any()

def test_postprocessor_normalization_and_shape():
    post = Postprocessor()
    pre = Preprocessor(target_size=518)
    prep = pre.preprocess(DATA_DIR / "sample_aerial.tif")
    
    # Create synthetic test disparity to test exact bounds
    raw_depth = np.linspace(1.0, 5.0, 518*518, dtype=np.float32).reshape(1, 518, 518)
    raw_res = RawInferenceResult(
        raw_depth=raw_depth,
        inference_time_seconds=0.1,
        model_name="test",
        execution_provider="CPU"
    )
    
    out = post.postprocess(raw_res, prep)
    orig_h, orig_w = prep.original_dimensions
    assert out.shape == (orig_h, orig_w)
    assert np.isclose(out.min(), 0.0, atol=1e-5)
    assert np.isclose(out.max(), 1.0, atol=1e-5)

def test_validator_catches_fake_or_corrupt_outputs():
    val = OutputValidator()
    
    # Test 1: NaN presence
    nan_arr = np.zeros((100, 100), dtype=np.float32)
    nan_arr[5, 5] = np.nan
    rep1 = val.validate(nan_arr, (100, 100))
    assert rep1.is_valid is False
    assert rep1.has_nans is True

    # Test 2: Constant/flat fake array (zero std dev)
    flat_arr = np.full((100, 100), 0.5, dtype=np.float32)
    rep2 = val.validate(flat_arr, (100, 100))
    assert rep2.is_valid is False
    assert rep2.is_constant is True

    # Test 3: Shape mismatch
    valid_pattern = np.linspace(0, 1, 10000, dtype=np.float32).reshape(100, 100)
    rep3 = val.validate(valid_pattern, (200, 200))
    assert rep3.is_valid is False
    assert rep3.output_shape_matches_input is False

    # Test 4: Genuine valid array
    rep4 = val.validate(valid_pattern, (100, 100))
    assert rep4.is_valid is True
    assert rep4.is_constant is False

def test_end_to_end_depth_pipeline():
    pipeline = DepthPipeline(model_path=MODEL_PATH, target_size=518, intra_op_threads=2)
    output = pipeline.process(DATA_DIR / "sample_geotiff.tif")
    
    assert output.depth_type == "RELATIVE_DEPTH"
    assert output.validation.is_valid is True
    assert output.validation.min_value >= 0.0
    assert output.validation.max_value <= 1.0
    assert output.relative_depth.shape == output.original_shape
    assert output.timing["inference_seconds"] > 0
    assert output.timing["total_seconds"] > output.timing["inference_seconds"]
