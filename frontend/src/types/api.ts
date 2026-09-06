export interface HealthResponse {
  status: string;
  model_name: string;
  model_loaded: boolean;
  execution_provider: string;
  device: string;
  version: string;
}

export interface ImageMetadataResponse {
  original_height: number;
  original_width: number;
  channels: number;
  format: string;
  has_georeference: boolean;
  crs: string | null;
  transform: [number, number, number, number, number, number] | null;
  bounds: [number, number, number, number] | null;
  resolution?: [number, number] | null;
  nodata: number | null;
}

export interface ValidationResponse {
  is_valid: boolean;
  has_nans: boolean;
  has_infs: boolean;
  is_constant: boolean;
  min_value: number;
  max_value: number;
  mean_value: number;
  std_value: number;
  message: string;
}

export interface CalibrationMetricsResponse {
  mae: number;
  rmse: number;
  bias: number;
  pearson_r: number;
  r_squared: number;
  sample_count: number;
}

export interface CalibrationResponse {
  mode: string;
  method: string;
  source_type: string;
  source_identifier: string | null;
  is_metric: boolean;
  depth_type: string;
  scale_factor: number | null;
  shift_offset: number | null;
  metrics: CalibrationMetricsResponse | null;
  warnings: string[];
  limitations: string[];
  rejection_reason: string | null;
}

export interface ReliefMetricsResponse {
  min_value: number;
  max_value: number;
  mean_value: number;
  std_value: number;
  relief_range: number;
  roughness_iqr: number;
  p10: number;
  p50: number;
  p90: number;
  valid_pixel_count: number;
}

export interface ProcessImageResponse {
  job_id: string;
  status: string;
  depth_type: string;
  units: string;
  is_metric: boolean;
  input_metadata: ImageMetadataResponse;
  validation: ValidationResponse;
  relief_metrics?: ReliefMetricsResponse | null;
  calibration: CalibrationResponse;
  timings: Record<string, number>;
  geotiff_download_url: string;
  preview_png_download_url: string;
  mesh_download_url?: string;
}

export interface GCPInput {
  x_pixel: number;
  y_pixel: number;
  z_elevation: number;
  x_geo?: number | null;
  y_geo?: number | null;
  point_id?: string;
  description?: string;
}

export type ProcessingStatus = 'idle' | 'validating' | 'uploading' | 'processing' | 'success' | 'error';

export interface ElevationMetrics {
  mae: number;
  rmse: number;
  bias: number;
  abs_rel: number;
  sq_rel: number;
  pearson_r: number;
  r_squared: number;
  delta_1: number;
  delta_2: number;
  delta_3: number;
  valid_points_count: number;
  total_points_count: number;
  coverage_ratio: number;
}

export interface EvaluationResponse {
  evaluation_id: string;
  target_job_id: string;
  reference_filename: string;
  depth_type: string;
  is_metric: boolean;
  metrics: ElevationMetrics;
  error_map_download_url: string;
  warnings: string[];
  limitations: string[];
}
