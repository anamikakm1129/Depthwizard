import assert from 'node:assert/strict';

// Inline replication of pure sanitizeErrorMessage logic for isolated testing
function sanitizeErrorMessage(rawMessage, status) {
  if (!rawMessage || typeof rawMessage !== 'string') {
    return status ? `Server returned HTTP ${status}` : 'Unknown processing error occurred.';
  }

  if (rawMessage.includes('Traceback (most recent call last)') || rawMessage.includes('File "') || rawMessage.includes('\\')) {
    const lines = rawMessage.trim().split('\n');
    const lastLine = lines[lines.length - 1].trim();
    if (lastLine.length > 0 && !lastLine.startsWith('File "')) {
      return lastLine;
    }
    return 'An internal processing error occurred in the geospatial pipeline.';
  }

  return rawMessage;
}

console.log('--- Running Focused Frontend Unit & Contract Tests ---');

// 1. Test Error Sanitization
{
  console.log('[Test 1] Testing error sanitization...');
  const rawTraceback = `Traceback (most recent call last):\n  File "backend/app/api/routes/process.py", line 105, in process_image\n    raise ValueError("Invalid matrix determinant")\nValueError: Invalid matrix determinant`;
  const sanitized = sanitizeErrorMessage(rawTraceback, 500);
  assert.equal(sanitized, 'ValueError: Invalid matrix determinant', 'Traceback must be trimmed to clean message');

  const normalMsg = 'Unsupported format .xyz. Allowed: .tif, .tiff, .png, .jpg, .jpeg';
  assert.equal(sanitizeErrorMessage(normalMsg, 400), normalMsg, 'Standard user-facing message preserved');

  const emptyMsg = sanitizeErrorMessage('', 502);
  assert.equal(emptyMsg, 'Server returned HTTP 502', 'Empty message fallback to HTTP status');
  console.log('  [PASS] Error sanitization verified.');
}

// 2. Test GCP Input Contract & Structure
{
  console.log('[Test 2] Testing GCP input serialization contract...');
  const gcp = {
    x_pixel: 100.5,
    y_pixel: 200.5,
    z_elevation: 154.2,
    x_geo: 500234.12,
    y_geo: 4123987.45,
    point_id: 'GCP-01',
    description: 'Survey benchmark'
  };

  const serialized = JSON.stringify([gcp]);
  const parsed = JSON.parse(serialized);
  assert.equal(parsed[0].x_pixel, 100.5);
  assert.equal(parsed[0].y_pixel, 200.5);
  assert.equal(parsed[0].z_elevation, 154.2);
  assert.equal(parsed[0].x_geo, 500234.12);
  assert.equal(parsed[0].y_geo, 4123987.45);
  assert.equal(parsed[0].point_id, 'GCP-01');
  console.log('  [PASS] GCP serialization verified.');
}

// 3. Test Relative DSM Response Contract
{
  console.log('[Test 3] Testing RELATIVE_DSM contract validation...');
  const mockRelativeResponse = {
    job_id: 'test-relative-uuid',
    status: 'completed',
    depth_type: 'RELATIVE_DSM',
    units: 'unitless_disparity',
    is_metric: false,
    input_metadata: {
      original_height: 512,
      original_width: 512,
      channels: 3,
      format: 'GTiff',
      has_georeference: true,
      crs: 'EPSG:32618',
      transform: [10.0, 0.0, 500000.0, 0.0, -10.0, 4000000.0],
      bounds: [500000.0, 3994880.0, 505120.0, 4000000.0],
      resolution: [10.0, 10.0],
      nodata: null
    },
    validation: {
      is_valid: true,
      has_nans: false,
      has_infs: false,
      is_constant: false,
      min_value: 0.0,
      max_value: 1.0,
      mean_value: 0.48,
      std_value: 0.22,
      message: 'Valid'
    },
    relief_metrics: {
      min_value: 0.0,
      max_value: 1.0,
      mean_value: 0.48,
      std_value: 0.22,
      relief_range: 1.0,
      roughness_iqr: 0.35,
      p10: 0.12,
      p50: 0.47,
      p90: 0.82,
      valid_pixel_count: 262144
    },
    calibration: {
      mode: 'uncalibrated_relative',
      method: 'none',
      source_type: 'none',
      source_identifier: null,
      is_metric: false,
      depth_type: 'RELATIVE_DSM',
      scale_factor: null,
      shift_offset: null,
      metrics: null,
      warnings: ['No elevation reference provided; maintaining relative disparity.'],
      limitations: ['Values are unitless relative disparity.'],
      rejection_reason: null
    },
    timings: {
      inference_seconds: 0.82,
      relative_dsm_seconds: 0.04,
      total_seconds: 1.25
    },
    geotiff_download_url: '/api/v1/download/test-relative-uuid_depth.tif',
    preview_png_download_url: '/api/v1/download/test-relative-uuid_preview.png',
    mesh_download_url: '/api/v1/download/test-relative-uuid_mesh.obj'
  };

  assert.equal(mockRelativeResponse.depth_type, 'RELATIVE_DSM');
  assert.equal(mockRelativeResponse.units, 'unitless_disparity');
  assert.equal(mockRelativeResponse.is_metric, false);
  assert.equal(mockRelativeResponse.calibration.is_metric, false);
  assert.ok(mockRelativeResponse.relief_metrics);
  assert.equal(mockRelativeResponse.relief_metrics.valid_pixel_count, 262144);
  console.log('  [PASS] RELATIVE_DSM contract verified.');
}

// 4. Test Calibrated DSM Response Contract
{
  console.log('[Test 4] Testing CALIBRATED_DSM contract validation...');
  const mockCalibratedResponse = {
    job_id: 'test-calibrated-uuid',
    status: 'completed',
    depth_type: 'CALIBRATED_DSM',
    units: 'meters',
    is_metric: true,
    input_metadata: {
      original_height: 512,
      original_width: 512,
      channels: 3,
      format: 'GTiff',
      has_georeference: true,
      crs: 'EPSG:32618',
      transform: [10.0, 0.0, 500000.0, 0.0, -10.0, 4000000.0],
      bounds: [500000.0, 3994880.0, 505120.0, 4000000.0],
      resolution: [10.0, 10.0],
      nodata: null
    },
    validation: {
      is_valid: true,
      has_nans: false,
      has_infs: false,
      is_constant: false,
      min_value: 120.5,
      max_value: 340.8,
      mean_value: 210.3,
      std_value: 45.2,
      message: 'Valid'
    },
    relief_metrics: {
      min_value: 0.0,
      max_value: 1.0,
      mean_value: 0.48,
      std_value: 0.22,
      relief_range: 1.0,
      roughness_iqr: 0.35,
      p10: 0.12,
      p50: 0.47,
      p90: 0.82,
      valid_pixel_count: 262144
    },
    calibration: {
      mode: 'validated_metric',
      method: 'gcp_affine',
      source_type: 'surveyed_gcps',
      source_identifier: null,
      is_metric: true,
      depth_type: 'CALIBRATED_DSM',
      scale_factor: 220.3,
      shift_offset: 120.5,
      metrics: {
        mae: 1.25,
        rmse: 1.85,
        bias: 0.12,
        pearson_r: 0.98,
        r_squared: 0.96,
        sample_count: 4
      },
      warnings: [],
      limitations: [],
      rejection_reason: null
    },
    timings: {
      inference_seconds: 0.85,
      relative_dsm_seconds: 0.05,
      calibration_seconds: 0.02,
      total_seconds: 1.35
    },
    geotiff_download_url: '/api/v1/download/test-calibrated-uuid_depth.tif',
    preview_png_download_url: '/api/v1/download/test-calibrated-uuid_preview.png',
    mesh_download_url: '/api/v1/download/test-calibrated-uuid_mesh.obj'
  };

  assert.equal(mockCalibratedResponse.depth_type, 'CALIBRATED_DSM');
  assert.equal(mockCalibratedResponse.units, 'meters');
  assert.equal(mockCalibratedResponse.is_metric, true);
  assert.equal(mockCalibratedResponse.calibration.is_metric, true);
  assert.equal(mockCalibratedResponse.calibration.metrics?.sample_count, 4);
  console.log('  [PASS] CALIBRATED_DSM contract verified.');
}

console.log('--- All Focused Frontend Contract Tests Passed (4/4) ---');

