import React, { useState, useRef } from 'react';
import { UploadCloud, FileImage, Settings2, Play, AlertCircle, Plus, Trash2, Loader2 } from 'lucide-react';
import type { GCPInput, ProcessingStatus } from '../types/api';

interface UploadSectionProps {
  onProcess: (file: File, gcps?: GCPInput[]) => void;
  isProcessing: boolean;
  status?: ProcessingStatus;
}

export const UploadSection: React.FC<UploadSectionProps> = ({ onProcess, isProcessing, status = 'idle' }) => {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [showGcpPanel, setShowGcpPanel] = useState(false);
  const [showGeoCoords, setShowGeoCoords] = useState(false);
  const [gcps, setGcps] = useState<GCPInput[]>([]);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const allowedExtensions = ['.tif', '.tiff', '.png', '.jpg', '.jpeg'];

  const validateAndSelect = (file: File) => {
    setErrorMsg(null);
    const ext = '.' + file.name.split('.').pop()?.toLowerCase();
    if (!allowedExtensions.includes(ext)) {
      setErrorMsg(`Unsupported format: ${ext}. Supported: GeoTIFF, TIFF, PNG, JPEG.`);
      return;
    }
    if (file.size > 250 * 1024 * 1024) {
      setErrorMsg('File size exceeds maximum limit of 250 MB.');
      return;
    }
    setSelectedFile(file);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      validateAndSelect(e.dataTransfer.files[0]);
    }
  };

  const handleAddGcp = () => {
    setGcps([
      ...gcps,
      { x_pixel: 0, y_pixel: 0, z_elevation: 100, point_id: `GCP-${gcps.length + 1}` }
    ]);
  };

  const handleUpdateGcp = (index: number, field: keyof GCPInput, value: any) => {
    const updated = [...gcps];
    updated[index] = { ...updated[index], [field]: value };
    setGcps(updated);
  };

  const handleRemoveGcp = (index: number) => {
    setGcps(gcps.filter((_, i) => i !== index));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFile || isProcessing) return;
    onProcess(selectedFile, gcps.length > 0 ? gcps : undefined);
  };

  const getStatusLabel = () => {
    switch (status) {
      case 'validating':
        return 'Validating input file...';
      case 'uploading':
        return 'Uploading raster payload...';
      case 'processing':
        return 'Running ONNX CPU Inference & Geospatial Pipeline...';
      case 'success':
        return 'Pipeline Complete';
      default:
        return 'Running ONNX CPU Inference & Geospatial Pipeline...';
    }
  };

  return (
    <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-5 shadow-lg">
      <h2 className="text-sm font-semibold text-white mb-3 flex items-center space-x-2">
        <UploadCloud className="w-4 h-4 text-cyan-400" />
        <span>Optical Imagery Upload</span>
      </h2>

      {errorMsg && (
        <div className="mb-3 bg-rose-950/50 border border-rose-800/80 text-rose-300 text-xs p-3 rounded-lg flex items-center space-x-2">
          <AlertCircle className="w-4 h-4 text-rose-400 flex-shrink-0" />
          <span>{errorMsg}</span>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-4">
        <div
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
          className={`border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition-colors ${
            dragOver
              ? 'border-cyan-500 bg-cyan-950/20'
              : 'border-slate-700/80 hover:border-slate-600 bg-slate-950/40'
          }`}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept=".tif,.tiff,.png,.jpg,.jpeg"
            onChange={(e) => e.target.files?.[0] && validateAndSelect(e.target.files[0])}
            className="hidden"
          />
          <FileImage className="w-8 h-8 mx-auto mb-2 text-slate-400" />
          {selectedFile ? (
            <div>
              <p className="text-sm font-medium text-cyan-300 break-all">{selectedFile.name}</p>
              <p className="text-xs text-slate-400 mt-1">
                {(selectedFile.size / (1024 * 1024)).toFixed(2)} MB
              </p>
            </div>
          ) : (
            <div>
              <p className="text-xs font-medium text-slate-300">
                Drag &amp; drop GeoTIFF or standard image here, or click to browse
              </p>
              <p className="text-[11px] text-slate-500 mt-1">
                Supported: GeoTIFF (.tif, .tiff), PNG, JPEG (Max 250 MB)
              </p>
            </div>
          )}
        </div>

        {/* GCP Calibration Options Toggle */}
        <div>
          <button
            type="button"
            onClick={() => setShowGcpPanel(!showGcpPanel)}
            className="text-xs font-medium text-slate-400 hover:text-slate-200 flex items-center space-x-1.5 transition-colors"
          >
            <Settings2 className="w-3.5 h-3.5" />
            <span>
              {showGcpPanel ? 'Hide Metric Calibration Controls' : 'Add Ground Control Points (GCPs) for Metric Calibration'}
            </span>
          </button>

          {showGcpPanel && (
            <div className="mt-3 bg-slate-950/60 border border-slate-800 rounded-lg p-3 space-y-3">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-xs font-semibold text-slate-300">Ground Control Points (GCPs)</h3>
                  <p className="text-[11px] text-slate-400">
                    Provide &ge;3 non-collinear GCPs with surveyed elevation (m) to calibrate to absolute DSM.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={handleAddGcp}
                  className="bg-slate-800 hover:bg-slate-700 text-cyan-300 text-xs px-2.5 py-1 rounded flex items-center space-x-1 border border-slate-700"
                >
                  <Plus className="w-3 h-3" />
                  <span>Add GCP</span>
                </button>
              </div>

              {gcps.length === 0 ? (
                <p className="text-[11px] text-slate-500 italic">
                  No GCPs specified. Pipeline will produce relative disparity surface ([0.0, 1.0]).
                </p>
              ) : (
                <div className="space-y-2 max-h-56 overflow-y-auto pr-1">
                  <div className="flex items-center justify-between text-[11px] text-slate-400 pb-1">
                    <span>GCP Points List ({gcps.length})</span>
                    <button
                      type="button"
                      onClick={() => setShowGeoCoords(!showGeoCoords)}
                      className="text-cyan-400 hover:text-cyan-300 text-[10px] underline"
                    >
                      {showGeoCoords ? 'Hide Map Coordinates' : 'Add Map Coordinates (UTM/Geo)'}
                    </button>
                  </div>
                  {gcps.map((gcp, idx) => (
                    <div key={idx} className="space-y-1 bg-slate-900 p-2 rounded border border-slate-800">
                      <div className="flex items-center space-x-2 text-xs">
                        <input
                          type="text"
                          placeholder="ID"
                          value={gcp.point_id || ''}
                          onChange={(e) => handleUpdateGcp(idx, 'point_id', e.target.value)}
                          className="w-16 bg-slate-950 border border-slate-700 rounded px-1.5 py-1 text-slate-200 text-xs font-mono"
                        />
                        <input
                          type="number"
                          placeholder="X px"
                          value={gcp.x_pixel}
                          onChange={(e) => handleUpdateGcp(idx, 'x_pixel', parseFloat(e.target.value) || 0)}
                          className="w-16 bg-slate-950 border border-slate-700 rounded px-1.5 py-1 text-slate-200 text-xs font-mono"
                        />
                        <input
                          type="number"
                          placeholder="Y px"
                          value={gcp.y_pixel}
                          onChange={(e) => handleUpdateGcp(idx, 'y_pixel', parseFloat(e.target.value) || 0)}
                          className="w-16 bg-slate-950 border border-slate-700 rounded px-1.5 py-1 text-slate-200 text-xs font-mono"
                        />
                        <input
                          type="number"
                          placeholder="Elev (m)"
                          value={gcp.z_elevation}
                          onChange={(e) => handleUpdateGcp(idx, 'z_elevation', parseFloat(e.target.value) || 0)}
                          className="w-20 bg-slate-950 border border-slate-700 rounded px-1.5 py-1 text-emerald-400 text-xs font-mono"
                        />
                        <button
                          type="button"
                          onClick={() => handleRemoveGcp(idx)}
                          className="text-slate-500 hover:text-rose-400 p-1"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                      {showGeoCoords && (
                        <div className="flex items-center space-x-2 text-[11px] pt-1 border-t border-slate-800/80">
                          <input
                            type="number"
                            placeholder="X Map / UTM"
                            value={gcp.x_geo ?? ''}
                            onChange={(e) => handleUpdateGcp(idx, 'x_geo', e.target.value ? parseFloat(e.target.value) : null)}
                            className="w-24 bg-slate-950 border border-slate-700 rounded px-1.5 py-0.5 text-cyan-300 text-[11px] font-mono"
                          />
                          <input
                            type="number"
                            placeholder="Y Map / UTM"
                            value={gcp.y_geo ?? ''}
                            onChange={(e) => handleUpdateGcp(idx, 'y_geo', e.target.value ? parseFloat(e.target.value) : null)}
                            className="w-24 bg-slate-950 border border-slate-700 rounded px-1.5 py-0.5 text-cyan-300 text-[11px] font-mono"
                          />
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Submit Button */}
        <button
          type="submit"
          disabled={!selectedFile || isProcessing}
          className={`w-full py-2.5 px-4 rounded-xl text-xs font-semibold flex items-center justify-center space-x-2 transition-all shadow-md ${
            !selectedFile || isProcessing
              ? 'bg-slate-800 text-slate-500 cursor-not-allowed border border-slate-700/50'
              : 'bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 text-white border border-cyan-500/30 shadow-cyan-900/30'
          }`}
        >
          {isProcessing ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin text-cyan-300" />
              <span>{getStatusLabel()}</span>
            </>
          ) : (
            <>
              <Play className="w-4 h-4 fill-current" />
              <span>Execute DepthWizard Pipeline</span>
            </>
          )}
        </button>
      </form>
    </div>
  );
};
