import { useState, useEffect } from 'react';
import { Header } from './components/Header';
import { UploadSection } from './components/UploadSection';
import { MetadataPanel } from './components/MetadataPanel';
import { Comparison2D } from './components/Comparison2D';
import { Terrain3D } from './components/Terrain3D';
import { EvaluationModal } from './components/EvaluationModal';
import type { HealthResponse, ProcessImageResponse, GCPInput, ProcessingStatus } from './types/api';
import { fetchHealth, processImage } from './services/api';
import { Layers, Box, AlertCircle } from 'lucide-react';

export function App() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [healthLoading, setHealthLoading] = useState<boolean>(true);
  const [processingStatus, setProcessingStatus] = useState<ProcessingStatus>('idle');
  const [processResult, setProcessResult] = useState<ProcessImageResponse | null>(null);
  const [originalImageUrl, setOriginalImageUrl] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'2d' | '3d'>('2d');
  const [isEvaluationModalOpen, setIsEvaluationModalOpen] = useState<boolean>(false);

  useEffect(() => {
    fetchHealth()
      .then((data) => setHealth(data))
      .catch((err) => console.warn('Health check unreachable:', err))
      .finally(() => setHealthLoading(false));
  }, []);

  const handleProcess = async (file: File, gcps?: GCPInput[]) => {
    setProcessingStatus('validating');
    setErrorMessage(null);

    // Create local object URL for instant 2D preview & texture mapping
    const localUrl = URL.createObjectURL(file);
    setOriginalImageUrl(localUrl);

    try {
      const res = await processImage(file, gcps, (stage) => {
        setProcessingStatus(stage);
      });
      setProcessResult(res);
      setProcessingStatus('success');
    } catch (err: any) {
      setErrorMessage(err.message || 'Processing failed. Please check backend server.');
      setProcessingStatus('error');
    }
  };

  const isProcessing = processingStatus === 'validating' || processingStatus === 'uploading' || processingStatus === 'processing';

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
      <Header health={health} loading={healthLoading} />

      <main className="flex-1 p-6 max-w-7xl w-full mx-auto space-y-6">
        {errorMessage && (
          <div className="bg-rose-950/60 border border-rose-800 text-rose-300 p-4 rounded-xl flex items-center space-x-3 text-sm shadow-lg">
            <AlertCircle className="w-5 h-5 text-rose-400 flex-shrink-0" />
            <span>{errorMessage}</span>
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Left Column: Upload & Metadata */}
          <div className="lg:col-span-4 space-y-6">
            <UploadSection onProcess={handleProcess} isProcessing={isProcessing} status={processingStatus} />
            {processResult && (
              <MetadataPanel
                result={processResult}
                onOpenEvaluation={() => setIsEvaluationModalOpen(true)}
              />
            )}
          </div>

          {/* Right Column: 2D View & 3D Terrain */}
          <div className="lg:col-span-8 space-y-4">
            {processResult && originalImageUrl ? (
              <>
                {/* View Switcher Tabs */}
                <div className="flex items-center space-x-2 border-b border-slate-800 pb-2">
                  <button
                    onClick={() => setActiveTab('2d')}
                    className={`px-4 py-2 rounded-lg text-xs font-semibold flex items-center space-x-2 transition-colors ${
                      activeTab === '2d'
                        ? 'bg-cyan-600 text-white shadow-sm'
                        : 'bg-slate-900 text-slate-400 hover:text-slate-200 border border-slate-800'
                    }`}
                  >
                    <Layers className="w-4 h-4" />
                    <span>2D Optical &amp; Surface Comparison</span>
                  </button>

                  <button
                    onClick={() => setActiveTab('3d')}
                    className={`px-4 py-2 rounded-lg text-xs font-semibold flex items-center space-x-2 transition-colors ${
                      activeTab === '3d'
                        ? 'bg-cyan-600 text-white shadow-sm'
                        : 'bg-slate-900 text-slate-400 hover:text-slate-200 border border-slate-800'
                    }`}
                  >
                    <Box className="w-4 h-4" />
                    <span>3D Terrain Mesh Viewer</span>
                  </button>
                </div>

                {/* View Content */}
                {activeTab === '2d' ? (
                  <Comparison2D
                    originalImageUrl={originalImageUrl}
                    depthImageUrl={processResult.preview_png_download_url}
                    depthType={processResult.depth_type}
                  />
                ) : (
                  <Terrain3D
                    originalImageUrl={originalImageUrl}
                    depthImageUrl={processResult.preview_png_download_url}
                    meshDownloadUrl={processResult.mesh_download_url}
                    depthType={processResult.depth_type}
                    units={processResult.units}
                    isMetric={processResult.calibration.is_metric}
                  />
                )}
              </>
            ) : (
              <div className="bg-slate-900/50 border border-slate-800/80 rounded-2xl h-[520px] flex flex-col items-center justify-center p-8 text-center text-slate-400 space-y-3">
                <div className="bg-slate-800/80 p-4 rounded-2xl border border-slate-700/60 shadow-inner">
                  <Box className="w-10 h-10 text-slate-500" />
                </div>
                <h3 className="text-base font-semibold text-slate-200">
                  Awaiting Optical Remote Sensing Imagery
                </h3>
                <p className="text-xs max-w-md text-slate-400 leading-relaxed">
                  Upload a satellite GeoTIFF or high-resolution aerial orthophoto on the left to trigger genuine ONNX Runtime CPU inference and visualize the resulting 2D relief and 3D terrain surface.
                </p>
              </div>
            )}
          </div>
        </div>
      </main>

      {processResult && (
        <EvaluationModal
          jobId={processResult.job_id}
          isMetricPrediction={processResult.calibration.is_metric}
          depthType={processResult.depth_type}
          isOpen={isEvaluationModalOpen}
          onClose={() => setIsEvaluationModalOpen(false)}
        />
      )}

      <footer className="border-t border-slate-900 bg-slate-950 py-3 text-center text-[11px] text-slate-600 font-mono">
        DepthWizard &mdash; Smart India Hackathon (SIH) 2026 Solution &bull; Scientific Single-View Elevation Pipeline
      </footer>
    </div>
  );
}

export default App;
