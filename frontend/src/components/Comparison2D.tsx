import React, { useState, useRef } from 'react';
import { Sliders, Eye, SplitSquareHorizontal, Layers } from 'lucide-react';
import { getDownloadUrl } from '../services/api';

interface Comparison2DProps {
  originalImageUrl: string;
  depthImageUrl: string;
  depthType: string;
}

export const Comparison2D: React.FC<Comparison2DProps> = ({
  originalImageUrl,
  depthImageUrl,
  depthType,
}) => {
  const [viewMode, setViewMode] = useState<'sideBySide' | 'split' | 'overlay'>('sideBySide');
  const [splitPos, setSplitPos] = useState<number>(50); // percentage
  const [overlayOpacity, setOverlayOpacity] = useState<number>(50);
  const containerRef = useRef<HTMLDivElement>(null);

  const fullDepthUrl = getDownloadUrl(depthImageUrl);

  return (
    <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-5 shadow-lg space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2 pb-3 border-b border-slate-800">
        <div className="flex items-center space-x-2">
          <Layers className="w-4 h-4 text-cyan-400" />
          <h2 className="text-sm font-semibold text-white">2D Optical vs Surface Comparison</h2>
        </div>

        {/* View Mode Switcher */}
        <div className="flex items-center bg-slate-950/80 p-1 rounded-lg border border-slate-800 text-xs">
          <button
            onClick={() => setViewMode('sideBySide')}
            className={`px-3 py-1 rounded-md font-medium transition-colors flex items-center space-x-1.5 ${
              viewMode === 'sideBySide'
                ? 'bg-cyan-600 text-white shadow-sm'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Eye className="w-3.5 h-3.5" />
            <span>Side-by-Side</span>
          </button>
          <button
            onClick={() => setViewMode('split')}
            className={`px-3 py-1 rounded-md font-medium transition-colors flex items-center space-x-1.5 ${
              viewMode === 'split'
                ? 'bg-cyan-600 text-white shadow-sm'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <SplitSquareHorizontal className="w-3.5 h-3.5" />
            <span>Split Slider</span>
          </button>
          <button
            onClick={() => setViewMode('overlay')}
            className={`px-3 py-1 rounded-md font-medium transition-colors flex items-center space-x-1.5 ${
              viewMode === 'overlay'
                ? 'bg-cyan-600 text-white shadow-sm'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Sliders className="w-3.5 h-3.5" />
            <span>Blend Overlay</span>
          </button>
        </div>
      </div>

      {/* Controls Bar for Slider/Overlay */}
      {viewMode === 'split' && (
        <div className="flex items-center space-x-3 bg-slate-950/60 p-2.5 rounded-lg border border-slate-800 text-xs text-slate-300">
          <span className="text-slate-400 font-mono">Split Position:</span>
          <input
            type="range"
            min="0"
            max="100"
            value={splitPos}
            onChange={(e) => setSplitPos(Number(e.target.value))}
            className="flex-1 accent-cyan-500 cursor-pointer"
          />
          <span className="font-mono text-cyan-400 w-10 text-right">{splitPos}%</span>
        </div>
      )}

      {viewMode === 'overlay' && (
        <div className="flex items-center space-x-3 bg-slate-950/60 p-2.5 rounded-lg border border-slate-800 text-xs text-slate-300">
          <span className="text-slate-400 font-mono">Surface Opacity:</span>
          <input
            type="range"
            min="0"
            max="100"
            value={overlayOpacity}
            onChange={(e) => setOverlayOpacity(Number(e.target.value))}
            className="flex-1 accent-cyan-500 cursor-pointer"
          />
          <span className="font-mono text-cyan-400 w-10 text-right">{overlayOpacity}%</span>
        </div>
      )}

      {/* Canvas / Image Display Area */}
      <div className="min-h-[460px] flex items-center justify-center bg-slate-950/80 rounded-xl border border-slate-800/80 p-3 overflow-hidden">
        {viewMode === 'sideBySide' && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 w-full">
            <div className="space-y-2">
              <div className="flex items-center justify-between text-xs text-slate-400 px-1">
                <span className="font-medium text-slate-300">Optical Imagery</span>
                <span className="text-[10px] font-mono">RGB Source</span>
              </div>
              <div className="aspect-square bg-slate-900 rounded-lg overflow-hidden border border-slate-800 flex items-center justify-center">
                <img
                  src={originalImageUrl}
                  alt="Optical Input"
                  className="max-h-full max-w-full object-contain"
                />
              </div>
            </div>

            <div className="space-y-2">
              <div className="flex items-center justify-between text-xs text-slate-400 px-1">
                <span className="font-medium text-slate-300">Estimated Relief / Surface</span>
                <span className="text-[10px] font-mono text-cyan-400">{depthType}</span>
              </div>
              <div className="aspect-square bg-slate-900 rounded-lg overflow-hidden border border-slate-800 flex items-center justify-center relative">
                <img
                  src={fullDepthUrl}
                  alt="Depth Map Output"
                  className="max-h-full max-w-full object-contain"
                />
              </div>
            </div>
          </div>
        )}

        {viewMode === 'split' && (
          <div
            ref={containerRef}
            className="relative w-full max-w-2xl aspect-square bg-slate-900 rounded-lg overflow-hidden border border-slate-800 select-none"
          >
            {/* Base layer: Optical Image */}
            <img
              src={originalImageUrl}
              alt="Optical Base"
              className="absolute inset-0 w-full h-full object-contain"
            />

            {/* Clipped overlay: Depth Image */}
            <div
              className="absolute inset-0 overflow-hidden"
              style={{ clipPath: `polygon(0 0, ${splitPos}% 0, ${splitPos}% 100%, 0 100%)` }}
            >
              <img
                src={fullDepthUrl}
                alt="Depth Overlay"
                className="absolute inset-0 w-full h-full object-contain"
              />
            </div>

            {/* Divider Line */}
            <div
              className="absolute top-0 bottom-0 w-0.5 bg-cyan-400 shadow-[0_0_10px_rgba(6,182,212,0.8)] pointer-events-none"
              style={{ left: `${splitPos}%` }}
            >
              <div className="absolute top-1/2 -translate-y-1/2 -translate-x-1/2 w-6 h-6 bg-slate-900 border-2 border-cyan-400 rounded-full flex items-center justify-center text-[9px] text-cyan-300 font-bold shadow-lg">
                &harr;
              </div>
            </div>

            <div className="absolute top-3 left-3 bg-slate-950/80 px-2 py-1 rounded text-[10px] text-cyan-300 font-mono border border-slate-800">
              Depth Map
            </div>
            <div className="absolute top-3 right-3 bg-slate-950/80 px-2 py-1 rounded text-[10px] text-slate-300 font-mono border border-slate-800">
              Optical RGB
            </div>
          </div>
        )}

        {viewMode === 'overlay' && (
          <div className="relative w-full max-w-2xl aspect-square bg-slate-900 rounded-lg overflow-hidden border border-slate-800">
            {/* Optical base */}
            <img
              src={originalImageUrl}
              alt="Optical Base"
              className="absolute inset-0 w-full h-full object-contain"
            />
            {/* Depth Map with opacity */}
            <img
              src={fullDepthUrl}
              alt="Depth Blended"
              className="absolute inset-0 w-full h-full object-contain pointer-events-none transition-opacity duration-75"
              style={{ opacity: overlayOpacity / 100 }}
            />
          </div>
        )}
      </div>

      {/* Color Scale Legend */}
      <div className="pt-2">
        <div className="flex items-center justify-between text-[11px] text-slate-400 mb-1 font-mono">
          <span>Low Elevation / Far Relief (0.0)</span>
          <span className="text-slate-300 font-sans font-medium">Viridis Palette (Deterministic Scientific Transfer)</span>
          <span>High Elevation / Near Relief (1.0)</span>
        </div>
        <div className="h-3 w-full rounded bg-gradient-to-r from-[#440154] via-[#21918c] to-[#fde725] border border-slate-700/60 shadow-inner" />
      </div>
    </div>
  );
};
