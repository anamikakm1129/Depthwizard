import time
from pathlib import Path
from typing import Union, List, Optional
import numpy as np
import onnxruntime as ort

from backend.app.inference.schemas import PreprocessedInput, RawInferenceResult

class DepthInferenceEngine:
    """
    ONNX Runtime CPU Inference Engine for Monocular Depth Estimation.
    Strictly uses real model execution; zero mock or random fallback.
    """
    def __init__(self, model_path: Union[str, Path], intra_op_threads: int = 2):
        self.model_path = Path(model_path)
        if not self.model_path.exists():
            raise FileNotFoundError(
                f"Model checkpoint not found at: {self.model_path}. "
                "Ensure download script has been executed."
            )

        self.intra_op_threads = intra_op_threads
        self.session = self._init_session()
        self.input_name = self.session.get_inputs()[0].name
        self.output_name = self.session.get_outputs()[0].name

    def _init_session(self) -> ort.InferenceSession:
        """Configures and instantiates ONNX Runtime CPU session for Intel i3-6006U."""
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = self.intra_op_threads
        opts.inter_op_num_threads = 1
        opts.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        opts.enable_cpu_mem_arena = True
        opts.enable_mem_pattern = True

        available_providers = ort.get_available_providers()
        if "CPUExecutionProvider" not in available_providers:
            raise RuntimeError("CPUExecutionProvider is not available in ONNX Runtime environment.")

        return ort.InferenceSession(
            str(self.model_path),
            sess_options=opts,
            providers=["CPUExecutionProvider"]
        )

    def infer(self, preprocessed: PreprocessedInput) -> RawInferenceResult:
        """
        Executes genuine ONNX model inference.
        Returns: RawInferenceResult with raw model output array and execution latency.
        """
        tensor = preprocessed.tensor
        if tensor.dtype != np.float32:
            tensor = tensor.astype(np.float32)

        start_time = time.perf_counter()
        raw_output = self.session.run([self.output_name], {self.input_name: tensor})[0]
        elapsed_seconds = time.perf_counter() - start_time

        return RawInferenceResult(
            raw_depth=raw_output,
            inference_time_seconds=elapsed_seconds,
            model_name=self.model_path.stem,
            execution_provider="CPUExecutionProvider"
        )
