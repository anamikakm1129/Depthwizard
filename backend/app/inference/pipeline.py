import time
from pathlib import Path
from typing import Union
import numpy as np

from backend.app.inference.schemas import PipelineOutput, PreprocessedInput
from backend.app.inference.preprocessing import Preprocessor
from backend.app.inference.engine import DepthInferenceEngine
from backend.app.inference.postprocessing import Postprocessor
from backend.app.inference.validation import OutputValidator

class DepthPipeline:
    """
    End-to-End Monocular Depth Estimation Pipeline.
    Strictly adheres to:
    - Real model execution (no fake AI)
    - Relative depth tagging (never elevation/DSM)
    - Preservation of spatial dimensions and georeferencing metadata
    """
    def __init__(self, model_path: Union[str, Path], target_size: int = 518, intra_op_threads: int = 2):
        self.model_path = Path(model_path)
        self.preprocessor = Preprocessor(target_size=target_size)
        self.engine = DepthInferenceEngine(model_path=model_path, intra_op_threads=intra_op_threads)
        self.postprocessor = Postprocessor()
        self.validator = OutputValidator()

    def process(self, input_source: Union[str, Path, np.ndarray]) -> PipelineOutput:
        """
        Executes end-to-end depth estimation on input image or raster.
        Measures execution latency across each step.
        """
        total_start = time.perf_counter()

        # 1. Preprocessing
        t0 = time.perf_counter()
        preprocessed = self.preprocessor.preprocess(input_source)
        t_preprocess = time.perf_counter() - t0

        # 2. Genuine Model Inference
        raw_result = self.engine.infer(preprocessed)
        t_inference = raw_result.inference_time_seconds

        # 3. Postprocessing
        t1 = time.perf_counter()
        relative_depth = self.postprocessor.postprocess(raw_result, preprocessed)
        t_postprocess = time.perf_counter() - t1

        # 4. Output Validation
        orig_h, orig_w = preprocessed.original_dimensions
        validation = self.validator.validate(relative_depth, (orig_h, orig_w))

        total_elapsed = time.perf_counter() - total_start

        timing = {
            "preprocessing_seconds": t_preprocess,
            "inference_seconds": t_inference,
            "postprocessing_seconds": t_postprocess,
            "total_seconds": total_elapsed
        }

        return PipelineOutput(
            relative_depth=relative_depth,
            depth_type="RELATIVE_DEPTH",
            original_shape=(orig_h, orig_w),
            metadata=preprocessed.metadata,
            validation=validation,
            timing=timing
        )
