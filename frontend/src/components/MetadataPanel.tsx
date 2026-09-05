import React from 'react';
import { Download, Compass, Clock, CheckCircle2, ShieldCheck, MapPin, BarChart3, AlertTriangle } from 'lucide-react';
import { Download, Compass, Clock, CheckCircle2, ShieldCheck, MapPin, BarChart3, AlertTriangle, Box } from 'lucide-react';
import { Download, Compass, Clock, CheckCircle2, ShieldCheck, MapPin, BarChart3, AlertTriangle, Box, Activity } from 'lucide-react';
import type { ProcessImageResponse } from '../types/api';
import { getDownloadUrl } from '../services/api';

interface MetadataPanelProps {
  result: ProcessImageResponse;
  onOpenEvaluation?: () => void;
}

export const MetadataPanel: React.FC<MetadataPanelProps> = ({ result }) => {
export const MetadataPanel: React.FC<MetadataPanelProps> = ({ result, onOpenEvaluation }) => {
  const { input_metadata, calibration, validation, timings, depth_type } = result;

  const isMetric = calibration.is_metric;

  return (
    <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-5 shadow-lg space-y-4 text-xs">
      {/* Header & Calibration Badge */}
      <div className="flex items-center justify-between pb-3 border-b border-slate-800">
        <div>
          <span className="text-slate-400 font-mono text-[11px]">Job ID: {result.job_id.slice(0, 8)}...</span>
          <h2 className="text-sm font-semibold text-white mt-0.5">Output &amp; Geospatial Reasoning</h2>
        </div>
        <div
          className={`px-3 py-1 rounded-full text-xs font-semibold flex items-center space-x-1.5 border ${
            isMetric
              ? 'bg-emerald-950/60 text-emerald-300 border-emerald-700/60'
              : 'bg-cyan-950/60 text-cyan-300 border-cyan-700/60'
          }`}
        >
          {isMetric ? <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" /> : <Compass className="w-3.5 h-3.5 text-cyan-400" />}
          <span>{depth_type}</span>
        </div>
      </div>

      {/* Scientific Semantics Callout */}
      {!isMetric ? (
        <div className="bg-cyan-950/30 border border-cyan-800/50 p-3 rounded-lg text-cyan-200">
          <p className="font-medium text-[11px] text-cyan-300 mb-1 flex items-center space-x-1">
            <Compass className="w-3.5 h-3.5" />
            <span>Relative Disparity Surface (Uncalibrated)</span>
          </p>
          <p className="text-[11px] text-cyan-200/80 leading-relaxed">
            This output captures relative optical disparity [0.0, 1.0]. Per Rule §5, georeferencing alone does not constitute metric height calibration. Vertical values represent unitless scene relief.
          </p>
        </div>
      ) : (
        <div className="bg-emerald-950/30 border border-emerald-800/50 p-3 rounded-lg text-emerald-200">
          <p className="font-medium text-[11px] text-emerald-300 mb-1 flex items-center space-x-1">
            <CheckCircle2 className="w-3.5 h-3.5" />
            <span>Validated Metric DSM (Meters Above Datum)</span>
          </p>
          <p className="text-[11px] text-emerald-200/80 leading-relaxed">
            Calibrated via surveyed control points. Scale: {calibration.scale_factor?.toFixed(3)}, Shift: {calibration.shift_offset?.toFixed(2)}m, RMSE: {calibration.metrics?.rmse.toFixed(2)}m (R&sup2;: {calibration.metrics?.r_squared.toFixed(3)}).
          </p>
        </div>
      )}

      {/* Warnings & Limitations if any */}
      {(calibration.warnings.length > 0 || calibration.limitations.length > 0) && (
        <div className="bg-amber-950/30 border border-amber-800/50 p-3 rounded-lg text-amber-200 space-y-1">
          <p className="font-medium text-[11px] text-amber-300 flex items-center space-x-1">
            <AlertTriangle className="w-3.5 h-3.5" />
            <span>Scientific Warnings &amp; Quality Notes</span>
          </p>
          {calibration.warnings.map((w, idx) => (
            <p key={idx} className="text-[11px] text-amber-200/90 leading-relaxed">&bull; {w}</p>
          ))}
          {calibration.limitations.map((l, idx) => (
            <p key={idx} className="text-[10px] text-amber-300/70 leading-relaxed">&bull; Note: {l}</p>
          ))}
        </div>
      )}

      {/* Spatial Metadata Grid */}
      <div>
        <h3 className="text-slate-300 font-semibold text-[11px] uppercase tracking-wider mb-2 flex items-center space-x-1">
          <MapPin className="w-3.5 h-3.5 text-cyan-400" />
          <span>Geospatial Properties</span>
        </h3>
        <div className="grid grid-cols-2 gap-2 text-slate-300 font-mono text-[11px]">
          <div className="bg-slate-950/60 p-2 rounded border border-slate-800">
            <span className="text-slate-500 text-[10px] block">Dimensions</span>
            <span>{input_metadata.original_width} &times; {input_metadata.original_height} px</span>
          </div>
          <div className="bg-slate-950/60 p-2 rounded border border-slate-800">
            <span className="text-slate-500 text-[10px] block">Georeferenced</span>
            <span className={input_metadata.has_georeference ? 'text-emerald-400' : 'text-slate-400'}>
              {input_metadata.has_georeference ? 'Yes (Valid CRS)' : 'No (Local Grid)'}
            </span>
          </div>
          <div className="bg-slate-950/60 p-2 rounded border border-slate-800 col-span-2">
            <span className="text-slate-500 text-[10px] block">Coordinate Reference System</span>
            <span className="break-all">{input_metadata.crs || 'Local / None (Unprojected)'}</span>
          </div>
        </div>
      </div>

      {/* Numerical Validation Stats */}
      <div>
        <h3 className="text-slate-300 font-semibold text-[11px] uppercase tracking-wider mb-2 flex items-center space-x-1">
          <BarChart3 className="w-3.5 h-3.5 text-cyan-400" />
          <span>Surface Statistics</span>
        </h3>
        <div className="grid grid-cols-4 gap-2 text-slate-300 font-mono text-[11px]">
          <div className="bg-slate-950/60 p-2 rounded border border-slate-800 text-center">
            <span className="text-slate-500 text-[10px] block">Min</span>
            <span>{validation.min_value.toFixed(2)}</span>
          </div>
          <div className="bg-slate-950/60 p-2 rounded border border-slate-800 text-center">
            <span className="text-slate-500 text-[10px] block">Max</span>
            <span>{validation.max_value.toFixed(2)}</span>
          </div>
          <div className="bg-slate-950/60 p-2 rounded border border-slate-800 text-center">
            <span className="text-slate-500 text-[10px] block">Mean</span>
            <span>{validation.mean_value.toFixed(2)}</span>
          </div>
          <div className="bg-slate-950/60 p-2 rounded border border-slate-800 text-center">
            <span className="text-slate-500 text-[10px] block">Std</span>
            <span>{validation.std_value.toFixed(2)}</span>
          </div>
        </div>
      </div>

      {/* Latency / Timings */}
      <div>
        <h3 className="text-slate-300 font-semibold text-[11px] uppercase tracking-wider mb-2 flex items-center space-x-1">
          <Clock className="w-3.5 h-3.5 text-cyan-400" />
          <span>Processing Timings (Intel i3 Skylake CPU)</span>
        </h3>
        <div className="bg-slate-950/60 p-2.5 rounded border border-slate-800 space-y-1.5 font-mono text-[11px] text-slate-400">
          <div className="flex justify-between">
            <span>Inference (ONNX):</span>
            <span className="text-cyan-300 font-semibold">
              {((timings.inference_seconds !== undefined ? timings.inference_seconds * 1000 : (timings.inference_ms || 0))).toFixed(0)} ms
            </span>
          </div>
          <div className="flex justify-between">
            <span>Pipeline Total:</span>
            <span className="text-slate-200 font-semibold">
              {((timings.total_seconds !== undefined ? timings.total_seconds * 1000 : (timings.total_ms || 0))).toFixed(0)} ms
            </span>
          </div>
        </div>
      </div>

      {/* Download Action Buttons */}
      {/* Action Buttons */}
      <div className="pt-2 space-y-2">
        {onOpenEvaluation && (
          <button
            onClick={onOpenEvaluation}
            className="w-full bg-cyan-950/70 hover:bg-cyan-900/80 text-cyan-300 hover:text-cyan-200 py-2 px-3 rounded-lg flex items-center justify-center space-x-2 border border-cyan-800/80 transition-colors font-semibold text-xs shadow-sm"
          >
            <Activity className="w-4 h-4 text-cyan-400" />
            <span>Evaluate Accuracy Against Ground Truth</span>
          </button>
        )}
        <a
          href={getDownloadUrl(result.geotiff_download_url)}
          download
          className="w-full bg-slate-800 hover:bg-slate-750 text-slate-200 hover:text-white py-2 px-3 rounded-lg flex items-center justify-center space-x-2 border border-slate-700 transition-colors font-medium text-xs"
        >
          <Download className="w-4 h-4 text-cyan-400" />
          <span>Download GeoTIFF / Float32 Raster (.tif)</span>
        </a>
        {result.mesh_download_url && (
          <a
            href={getDownloadUrl(result.mesh_download_url)}
            download
            className="w-full bg-slate-950 hover:bg-slate-900 text-cyan-400 hover:text-cyan-300 py-1.5 px-3 rounded-lg flex items-center justify-center space-x-2 border border-slate-800 transition-colors text-[11px]"
          >
            <Box className="w-3.5 h-3.5" />
            <span>Download 3D Mesh (.obj)</span>
          </a>
        )}
        <a
          href={getDownloadUrl(result.preview_png_download_url)}
          download
          className="w-full bg-slate-950 hover:bg-slate-900 text-slate-400 hover:text-slate-200 py-1.5 px-3 rounded-lg flex items-center justify-center space-x-2 border border-slate-800 transition-colors text-[11px]"
        >
          <Download className="w-3.5 h-3.5" />
          <span>Download Colormapped Preview (.png)</span>
        </a>
      </div>
    </div>
  );
};
