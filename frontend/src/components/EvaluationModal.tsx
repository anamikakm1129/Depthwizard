import React, { useState } from 'react';
import { X, Upload, CheckCircle2, AlertTriangle, Download, Activity, Compass, ShieldCheck } from 'lucide-react';
import type { EvaluationResponse } from '../types/api';
import { evaluateJob, getDownloadUrl } from '../services/api';

interface EvaluationModalProps {
  jobId: string;
  isMetricPrediction: boolean;
  depthType: string;
  isOpen: boolean;
  onClose: () => void;
}

export const EvaluationModal: React.FC<EvaluationModalProps> = ({
  jobId,
  isMetricPrediction,
  depthType,
  isOpen,
  onClose,
}) => {
  const [referenceFile, setReferenceFile] = useState<File | null>(null);
  const [isReferenceMetric, setIsReferenceMetric] = useState<boolean>(isMetricPrediction);
  const [isEvaluating, setIsEvaluating] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [evaluationResult, setEvaluationResult] = useState<EvaluationResponse | null>(null);

  if (!isOpen) return null;

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setReferenceFile(e.target.files[0]);
      setError(null);
    }
  };

  const handleRunEvaluation = async () => {
    if (!referenceFile) {
      setError('Please select a ground-truth reference raster or DEM file.');
      return;
    }

    setIsEvaluating(true);
    setError(null);

    try {
      const res = await evaluateJob(jobId, referenceFile, isReferenceMetric);
      setEvaluationResult(res);
    } catch (err: any) {
      setError(err.message || 'Evaluation failed. Please verify reference raster format.');
    } finally {
      setIsEvaluating(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 overflow-y-auto">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-3xl w-full p-6 shadow-2xl space-y-5 text-xs text-slate-200 my-8">
        {/* Header */}
        <div className="flex items-center justify-between pb-3 border-b border-slate-800">
          <div className="flex items-center space-x-2">
            <Activity className="w-5 h-5 text-cyan-400" />
            <div>
              <h2 className="text-base font-semibold text-white">Scientific Accuracy Evaluation Engine</h2>
              <p className="text-[11px] text-slate-400">Quantitative Benchmarking Against Real Ground-Truth Elevation / DEM</p>
              <p className="text-[11px] text-slate-400">Quantitative Benchmarking for {depthType} Against Real Ground-Truth DEM</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-white p-1 rounded-lg hover:bg-slate-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Input Section */}
        {!evaluationResult ? (
          <div className="space-y-4">
            <div className="bg-slate-950/60 p-4 rounded-xl border border-slate-800 space-y-3">
              <label className="block text-slate-300 font-medium text-xs">
                Upload Ground-Truth Reference Raster (GeoTIFF / DEM / nDSM)
              </label>
              <div className="flex items-center space-x-3">
                <label className="cursor-pointer bg-cyan-600 hover:bg-cyan-500 text-white px-4 py-2 rounded-lg font-semibold flex items-center space-x-2 transition-colors">
                  <Upload className="w-4 h-4" />
                  <span>Choose Reference File</span>
                  <input
                    type="file"
                    accept=".tif,.tiff,.png"
                    onChange={handleFileChange}
                    className="hidden"
                  />
                </label>
                <span className="text-slate-400 font-mono truncate max-w-xs">
                  {referenceFile ? referenceFile.name : 'No file selected (GeoTIFF recommended)'}
                </span>
              </div>
              <p className="text-[11px] text-slate-500">
                Rule &sect;2: Evaluation requires real ground-truth elevation. No simulated scores or synthetic references are permitted.
              </p>
            </div>

            <div className="flex items-center space-x-2 text-slate-300">
              <input
                type="checkbox"
                id="isMetricRef"
                checked={isReferenceMetric}
                onChange={(e) => setIsReferenceMetric(e.target.checked)}
                className="rounded bg-slate-950 border-slate-800 text-cyan-600 focus:ring-0"
              />
              <label htmlFor="isMetricRef" className="cursor-pointer select-none">
                Reference file contains absolute metric elevation values (meters)
              </label>
            </div>

            {error && (
              <div className="bg-rose-950/60 border border-rose-800 text-rose-300 p-3 rounded-lg flex items-center space-x-2">
                <AlertTriangle className="w-4 h-4 text-rose-400 flex-shrink-0" />
                <span>{error}</span>
              </div>
            )}

            <div className="flex justify-end space-x-3 pt-2">
              <button
                onClick={onClose}
                className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg transition-colors font-medium"
              >
                Cancel
              </button>
              <button
                onClick={handleRunEvaluation}
                disabled={!referenceFile || isEvaluating}
                className="px-5 py-2 bg-cyan-600 hover:bg-cyan-500 disabled:opacity-50 text-white rounded-lg font-semibold flex items-center space-x-2 transition-colors shadow-sm"
              >
                {isEvaluating ? (
                  <>
                    <Activity className="w-4 h-4 animate-spin" />
                    <span>Computing Metrics on CPU...</span>
                  </>
                ) : (
                  <>
                    <CheckCircle2 className="w-4 h-4" />
                    <span>Run Quantitative Evaluation</span>
                  </>
                )}
              </button>
            </div>
          </div>
        ) : (
          /* Results View */
          <div className="space-y-4">
            {/* Scientific Semantics Banner */}
            <div className={`p-3 rounded-xl border flex items-center justify-between ${
              evaluationResult.is_metric
                ? 'bg-emerald-950/40 border-emerald-800/60 text-emerald-300'
                : 'bg-cyan-950/40 border-cyan-800/60 text-cyan-300'
            }`}>
              <div className="flex items-center space-x-2">
                {evaluationResult.is_metric ? <ShieldCheck className="w-4 h-4" /> : <Compass className="w-4 h-4" />}
                <span className="font-semibold">Evaluated against: {evaluationResult.reference_filename}</span>
              </div>
              <span className="font-mono text-[11px] bg-slate-900/80 px-2 py-0.5 rounded border border-slate-800">
                {evaluationResult.depth_type}
              </span>
            </div>

            {/* Metrics Grid */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2.5 font-mono text-[11px]">
              <div className="bg-slate-950/80 p-2.5 rounded-lg border border-slate-800 text-center">
                <span className="text-slate-500 text-[10px] block font-sans">Mean Absolute Error</span>
                <span className="text-base font-bold text-white">{evaluationResult.metrics.mae.toFixed(3)}</span>
                <span className="text-[10px] text-slate-500 block">{evaluationResult.is_metric ? 'meters' : 'rel'}</span>
              </div>
              <div className="bg-slate-950/80 p-2.5 rounded-lg border border-slate-800 text-center">
                <span className="text-slate-500 text-[10px] block font-sans">Root Mean Square Error</span>
                <span className="text-base font-bold text-cyan-400">{evaluationResult.metrics.rmse.toFixed(3)}</span>
                <span className="text-[10px] text-slate-500 block">{evaluationResult.is_metric ? 'meters' : 'rel'}</span>
              </div>
              <div className="bg-slate-950/80 p-2.5 rounded-lg border border-slate-800 text-center">
                <span className="text-slate-500 text-[10px] block font-sans">Elevation Bias</span>
                <span className="text-base font-bold text-white">{evaluationResult.metrics.bias.toFixed(3)}</span>
                <span className="text-[10px] text-slate-500 block">{evaluationResult.is_metric ? 'meters' : 'rel'}</span>
              </div>
              <div className="bg-slate-950/80 p-2.5 rounded-lg border border-slate-800 text-center">
                <span className="text-slate-500 text-[10px] block font-sans">Pearson Correlation (r)</span>
                <span className="text-base font-bold text-emerald-400">{evaluationResult.metrics.pearson_r.toFixed(3)}</span>
                <span className="text-[10px] text-slate-500 block">[-1.0, 1.0]</span>
              </div>
            </div>

            {/* Secondary Threshold Metrics */}
            <div className="bg-slate-950/60 p-3 rounded-xl border border-slate-800 grid grid-cols-3 gap-2 font-mono text-center text-[11px]">
              <div>
                <span className="text-slate-500 text-[10px] block font-sans">&delta; &lt; 1.25</span>
                <span className="text-slate-200 font-semibold">{(evaluationResult.metrics.delta_1 * 100).toFixed(1)}%</span>
              </div>
              <div>
                <span className="text-slate-500 text-[10px] block font-sans">&delta; &lt; 1.25&sup2;</span>
                <span className="text-slate-200 font-semibold">{(evaluationResult.metrics.delta_2 * 100).toFixed(1)}%</span>
              </div>
              <div>
                <span className="text-slate-500 text-[10px] block font-sans">Valid Coverage</span>
                <span className="text-slate-200 font-semibold">{(evaluationResult.metrics.coverage_ratio * 100).toFixed(1)}%</span>
              </div>
            </div>

            {/* Diverging Spatial Error Map */}
            <div className="space-y-2">
              <h3 className="font-semibold text-slate-300 text-xs">Spatial Residual Error Map (e = pred - ref)</h3>
              <div className="bg-slate-950 p-2 rounded-xl border border-slate-800 flex flex-col items-center">
                <img
                  src={getDownloadUrl(evaluationResult.error_map_download_url)}
                  alt="Spatial Error Map"
                  className="max-h-56 rounded border border-slate-800 object-contain shadow-inner"
                />
                {/* Diverging Color Bar Legend */}
                <div className="w-full max-w-sm mt-3 space-y-1">
                  <div className="h-3 rounded-full w-full bg-gradient-to-r from-blue-600 via-slate-100 to-red-600 shadow-sm" />
                  <div className="flex justify-between text-[10px] font-mono text-slate-400">
                    <span>Under-estimation (Blue)</span>
                    <span className="text-slate-300 font-bold">Exact Agreement (0)</span>
                    <span>Over-estimation (Red)</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Warnings and Notes */}
            {evaluationResult.warnings.length > 0 && (
              <div className="bg-amber-950/30 border border-amber-800/50 p-3 rounded-lg text-amber-200 text-[11px] space-y-1">
                {evaluationResult.warnings.map((w, idx) => (
                  <p key={idx}>&bull; {w}</p>
                ))}
              </div>
            )}

            {/* Actions */}
            <div className="flex justify-between items-center pt-2">
              <a
                href={getDownloadUrl(evaluationResult.error_map_download_url)}
                download
                className="bg-slate-800 hover:bg-slate-700 text-slate-200 py-1.5 px-3 rounded-lg flex items-center space-x-1.5 text-[11px] transition-colors"
              >
                <Download className="w-3.5 h-3.5 text-cyan-400" />
                <span>Download Error Map (.png)</span>
              </a>
              <div className="space-x-2">
                <button
                  onClick={() => setEvaluationResult(null)}
                  className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-[11px] transition-colors"
                >
                  Evaluate Another File
                </button>
                <button
                  onClick={onClose}
                  className="px-4 py-1.5 bg-cyan-600 hover:bg-cyan-500 text-white rounded-lg text-[11px] font-semibold transition-colors"
                >
                  Close
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
