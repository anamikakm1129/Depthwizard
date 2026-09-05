---
trigger: always_on
---

# DepthWizard Development Rules

## 1. Core Objective
Build DepthWizard as a real, production-ready SIH 2026 solution for single-view optical remote-sensing image to elevation/height estimation and 3D terrain visualization.

## 2. No Fake AI
- Never create mock predictions, random height maps, fake DSMs, simulated inference, or placeholder AI outputs.
- Every displayed prediction must come from a real model/checkpoint or a clearly identified deterministic processing pipeline.
- Never claim model accuracy without actual evaluation results.

## 3. Understand Before Changing
- Inspect the existing project structure and relevant files before modifying anything.
- Do not overwrite, delete, or rewrite working code without a clear reason.
- Reuse existing components and utilities whenever possible.
- Make the smallest necessary change to accomplish the task.

## 4. Plan Before Implementation
For any substantial task:
1. Inspect the current implementation.
2. Identify dependencies and affected modules.
3. State the implementation plan.
4. Implement only after the plan is clear.
5. Verify the result with tests or appropriate validation.

Do not generate unnecessary files, duplicate implementations, or unused abstractions.

## 5. ML / Computer Vision
- The core pipeline must support:
  RGB image → monocular depth/height estimation → metric calibration → DSM/elevation output → 3D terrain.
- Prefer proven pretrained monocular depth backbones where appropriate.
- Clearly distinguish:
  - relative depth
  - above-ground height / nDSM
  - DTM / terrain elevation
  - absolute DSM
- GAMUS/nDSM data must not be incorrectly presented as absolute elevation ground truth.
- Metric calibration using DEM/GCP/georeferencing must be explicit and scientifically defensible.
- Never fabricate geospatial metadata, coordinates, CRS, elevations, or GCPs.
- Preserve valid spatial metadata when processing GeoTIFF or other georeferenced imagery.

## 6. Geospatial Correctness
- Use correct CRS, transforms, pixel resolution, bounds, nodata values, and raster dimensions.
- Do not silently discard georeferencing.
- Validate GeoTIFF outputs before considering them complete.
- Ensure DSM dimensions and spatial alignment correspond correctly to the source imagery.

## 7. 3D Visualization
- Generate the terrain mesh from actual predicted/generated elevation data.
- Use the original optical image as the terrain texture where appropriate.
- Do not create fake terrain merely for visual demonstration.
- Support first-person navigation and useful terrain/height/slope inspection.
- Keep the 3D viewer stable and performant.

## 8. Backend / Frontend
- Keep ML inference, geospatial processing, API, database, and visualization responsibilities separated.
- Use typed interfaces/contracts between modules.
- Handle large raster files safely.
- Show meaningful processing states, errors, and validation information to the user.
- Never hide inference failures behind fake successful results.

## 9. Database and Storage
- Store project metadata, uploaded-image metadata, processing jobs, model runs, metrics, and generated-output metadata where required.
- Store large images, DSMs, GeoTIFFs, and 3D assets outside the relational database when appropriate.
- Never store secrets, API keys, or credentials in source code.

## 10. Error Handling
- Fail clearly when required data, model weights, GPU resources, credentials, or dependencies are unavailable.
- Do not silently substitute mock implementations.
- Explain the actual blocker and provide the correct next action.

## 11. Testing and Verification
- Add tests for important functionality.
- Validate API contracts, file handling, raster dimensions, geospatial metadata, model inference, and frontend integration.
- Run relevant tests after significant changes.
- Do not mark a feature complete until it has been actually verified.

## 12. Code Quality
- Prefer simple, maintainable, production-oriented code.
- Avoid unnecessary dependencies.
- Avoid premature optimization.
- Avoid dead code and unused files.
- Follow the established project conventions.
- Keep changes focused and reviewable.

## 13. Security
- Never expose secrets or credentials.
- Validate uploaded files and user inputs.
- Prevent path traversal and unsafe file operations.
- Never execute destructive commands without explicit approval.
- Do not delete project data or important files automatically.

## 14. Documentation
- Document important architectural decisions, model choices, data sources, assumptions, limitations, and reproducibility steps.
- Clearly label experimental components.
- Never present an approximation as ground truth.

## 15. Stop Conditions
Stop and ask for clarification or required resources when:
- A required dataset is unavailable.
- A real model checkpoint is unavailable.
- A required API/key/credential is missing.
- The scientific/geospatial assumption is ambiguous.
- A destructive change would be required.
- The requested behavior conflicts with the project architecture.

## 16. Final Verification
Before declaring a task complete:
- Confirm the implementation actually exists.
- Confirm imports/builds/tests pass where applicable.
- Confirm no fake AI output was introduced.
- Confirm generated files are valid.
- Confirm geospatial metadata is preserved when applicable.
- Report what was changed and what was verified.