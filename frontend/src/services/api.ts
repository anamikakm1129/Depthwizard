import type { HealthResponse, ProcessImageResponse, GCPInput, EvaluationResponse } from '../types/api';

const API_BASE = import.meta.env.VITE_API_URL || '';

export async function fetchHealth(): Promise<HealthResponse> {
  const resp = await fetch(`${API_BASE}/api/v1/health`);
  if (!resp.ok) {
    throw new Error(`Health check failed: HTTP ${resp.status}`);
  }
  return resp.json();
}

/**
 * Sanitizes backend error details to prevent exposing stack traces or filesystem paths.
 */
export function sanitizeErrorMessage(rawMessage: string, status?: number): string {
  if (!rawMessage || typeof rawMessage !== 'string') {
    return status ? `Server returned HTTP ${status}` : 'Unknown processing error occurred.';
  }

  // If message contains traceback/filesystem paths, clean them
  if (rawMessage.includes('Traceback (most recent call last)') || rawMessage.includes('File "') || rawMessage.includes('\\')) {
    // Extract the final error line if available
    const lines = rawMessage.trim().split('\n');
    const lastLine = lines[lines.length - 1].trim();
    if (lastLine.length > 0 && !lastLine.startsWith('File "')) {
      return lastLine;
    }
    return 'An internal processing error occurred in the geospatial pipeline.';
  }

  return rawMessage;
}

export async function processImage(
  file: File,
  gcps?: GCPInput[],
  onStageChange?: (stage: 'uploading' | 'processing') => void
): Promise<ProcessImageResponse> {
  const formData = new FormData();
  formData.append('file', file);

  if (gcps && gcps.length > 0) {
    formData.append('gcps_json', JSON.stringify(gcps));
  }

  onStageChange?.('uploading');

  let resp: Response;
  try {
    // Notify processing stage once request is sent
    setTimeout(() => {
      onStageChange?.('processing');
    }, 200);

    resp = await fetch(`${API_BASE}/api/v1/process`, {
      method: 'POST',
      body: formData,
    });
  } catch (netErr: any) {
    throw new Error('Network connection failed. Please ensure the DepthWizard backend server is running and reachable.');
  }

  if (!resp.ok) {
    let errorDetail = `HTTP ${resp.status}`;
    try {
      const errJson = await resp.json();
      if (typeof errJson.detail === 'string') {
        errorDetail = sanitizeErrorMessage(errJson.detail, resp.status);
      } else if (Array.isArray(errJson.detail)) {
        // Pydantic validation error array
        errorDetail = errJson.detail.map((d: any) => d.msg || JSON.stringify(d)).join('; ');
      }
    } catch {
      errorDetail = `Server request failed with status HTTP ${resp.status}.`;
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
