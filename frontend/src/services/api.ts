import type { HealthResponse, ProcessImageResponse, GCPInput, EvaluationResponse } from '../types/api';

const API_BASE = import.meta.env.VITE_API_URL || '';

export async function fetchHealth(): Promise<HealthResponse> {
  const resp = await fetch(`${API_BASE}/api/v1/health`);
  if (!resp.ok) {
    throw new Error(`Health check failed: HTTP ${resp.status}`);
  }
  return resp.json();
}

export async function processImage(file: File, gcps?: GCPInput[]): Promise<ProcessImageResponse> {
  const formData = new FormData();
  formData.append('file', file);

  if (gcps && gcps.length > 0) {
    formData.append('gcps_json', JSON.stringify(gcps));
  }

  const resp = await fetch(`${API_BASE}/api/v1/process`, {
    method: 'POST',
    body: formData,
  });

  if (!resp.ok) {
    let errorDetail = `HTTP ${resp.status}`;
    try {
      const errJson = await resp.json();
      if (errJson.detail) errorDetail = errJson.detail;
    } catch {
      // ignore
    }
    throw new Error(errorDetail);
  }

  return resp.json();
}

export async function evaluateJob(
  jobId: string,
  referenceFile: File,
  isMetric: boolean = false
): Promise<EvaluationResponse> {
  const formData = new FormData();
  formData.append('job_id', jobId);
  formData.append('is_metric', isMetric ? 'true' : 'false');
  formData.append('reference_file', referenceFile);

  const resp = await fetch(`${API_BASE}/api/v1/evaluate`, {
    method: 'POST',
    body: formData,
  });

  if (!resp.ok) {
    let errorDetail = `HTTP ${resp.status}`;
    try {
      const errJson = await resp.json();
      if (errJson.detail) errorDetail = errJson.detail;
    } catch {
      // ignore
    }
    throw new Error(errorDetail);
  }

  return resp.json();
}

export function getDownloadUrl(path: string): string {
  if (path.startsWith('http://') || path.startsWith('https://')) {
    return path;
  }
  return `${API_BASE}${path}`;
}
