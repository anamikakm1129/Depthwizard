import React from 'react';
import { Mountain, Cpu, CheckCircle2, AlertTriangle } from 'lucide-react';
import type { HealthResponse } from '../types/api';

interface HeaderProps {
  health: HealthResponse | null;
  loading: boolean;
}

export const Header: React.FC<HeaderProps> = ({ health, loading }) => {
  return (
    <header className="bg-slate-900 border-b border-slate-800 text-white px-6 py-4 flex items-center justify-between shadow-md">
      <div className="flex items-center space-x-3">
        <div className="bg-gradient-to-tr from-cyan-500 to-blue-600 p-2 rounded-xl text-white shadow-lg">
          <Mountain className="w-6 h-6" />
        </div>
        <div>
          <div className="flex items-center space-x-2">
            <h1 className="font-bold text-lg tracking-wide text-white">DepthWizard</h1>
            <span className="bg-blue-900/60 text-blue-300 text-xs px-2 py-0.5 rounded border border-blue-700/50 font-mono">
              SIH 2026
            </span>
          </div>
          <p className="text-xs text-slate-400">
            Monocular Optical Remote Sensing to Elevation &amp; 3D Terrain
          </p>
        </div>
      </div>

      <div className="flex items-center space-x-4 text-xs">
        <div className="flex items-center space-x-1.5 bg-slate-800/80 px-3 py-1.5 rounded-lg border border-slate-700/70">
          <Cpu className="w-4 h-4 text-cyan-400" />
          <span className="text-slate-300 font-mono">
            {health ? `${health.device} (${health.execution_provider})` : 'Connecting...'}
          </span>
        </div>

        <div className="flex items-center space-x-1.5 bg-slate-800/80 px-3 py-1.5 rounded-lg border border-slate-700/70">
          {loading ? (
            <span className="w-2.5 h-2.5 rounded-full bg-amber-400 animate-pulse" />
          ) : health?.model_loaded ? (
            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
          ) : (
            <AlertTriangle className="w-4 h-4 text-rose-400" />
          )}
          <span className="text-slate-300 font-mono">
            {health?.model_loaded ? 'Model: DA-V2-Small INT8' : 'Model: Missing'}
          </span>
        </div>
      </div>
    </header>
  );
};
