# TerraGuard AI — Project Handoff & Architecture Status

## 1. Project Overview & Vision
TerraGuard AI is an automated satellite-based land monitoring and potential encroachment detection system.
It monitors selected geographical areas using real Google Earth Engine satellite imagery (Sentinel-2 L2A), detects land-cover changes across different dates using deep learning (SNUNet-CD), performs GIS spatial analysis to extract vector change regions and calculate affected metric area (m² and hectares), and evaluates potential encroachment risk against statutory buffer corridors and cadastral parcels for human verification.

**Submission status (2026-11-11):** TerraGuard is a working prototype/demo, not a fully validated operational detection system. Genuine Earth Engine acquisition and SNUNet-CD inference have been verified for one monitoring zone only. The completed genuine run produced zero candidate detections; seeded demonstration alerts are separate from model-generated results.

**Important Legal & Ethical Principle**:
Detected land-cover changes are candidate areas for investigation and must **never** be described as legally confirmed encroachment without ground verification.

---

## 2. Environment & Critical Configuration
- **Project Root**: `C:\projects\TerraGuard-AI`
- **Operating System**: Windows 11
- **Python**: 3.13.5 (Virtual Environment at `.\.venv`)
  - Packages: `earthengine-api 1.7.51`, `torch 2.15.0+cpu`, `shapely 2.2.0`, `scikit-learn 1.8.0`, `fastapi 0.162.0`, `sqlalchemy 2.0.48`, `pillow 12.1.1`, `numpy 2.4.6`.
- **Node/Frontend**: React 18, Vite 5, TypeScript 5, Tailwind CSS, Leaflet 1.9.4, React-Leaflet 4.2.1.
- **Google Earth Engine (GEE)**:
  - Project ID: `terraguard-ai-513908`
  - Authentication: Validated during the 2026-11-06 live demonstration; not rechecked during the 2026-11-11 read-only audit.
  - Dataset: `COPERNICUS/S2_SR_HARMONIZED`
  - Service Module: `backend/app/services/earth_engine_service.py`
- **Trained Deep Learning Checkpoint**:
  - Model: SNUNet-CD (Nested Dense Channel Attention, `base_width=32`, 7,791,309 parameters)
  - Checkpoint: `training/experiments/EXP-02_SNUNet/checkpoints/full_seed42_512_recovery_v2/best.pt`
  - Inference Service: `backend/app/services/snunet_service.py`

---

## 3. Implementation Roadmap & Current Phase
- [x] **Phase 1**: Architecture Audit, Repository Inspection & Plan Approval.
- [x] **Phase 2**: Real Area Monitoring & Interactive Polygon Management (Completed).
- [x] **Phase 3**: Connect Monitored Boundaries to Google Earth Engine (implemented; authenticated preview/compare, stored-zone geometry resolution, and scene persistence are present).
- [x] **Phase 4**: Dual-Date Acquisition & Verification for Saved Boundaries (live historical/recent scenes acquired for saved zone 1, verified, and persisted on one common native grid).
- [x] **Phase 5**: Geospatial Alignment & Preprocessing Engine (Earth Engine exports to a snapped local UTM grid; Rasterio preserves and validates CRS, affine, dimensions, resolution and nodata; misaligned recent rasters are warped onto the historical grid).
- [x] **Phase 6**: SNUNet-CD Inference on Aligned Satellite Pairs (saved scenes retain PNG display paths while `metadata_json.raster_url` supplies the native GeoTIFF to the detection pipeline; invalid inputs are neutralized during inference and invalid outputs masked).
- [x] **Phase 7**: GIS Change Vectorization & Metric Area Extraction (pixel polygons use the raster affine, are clipped in the projected zone, area is calculated in projected square metres, and output geometry is transformed to WGS84).
- [ ] **Phase 8**: Rule-Based Potential Encroachment Assessment Layer (risk scoring and parcel-association behavior are implemented, and focused synthetic regression tests are present, including unknown/unmatched parcel handling; a genuine positive detection has not exercised this layer end to end).
- [ ] **Phase 9**: Real Data Dashboard & Mentor Demonstration Polish (in progress; acquisition metadata, imagery evidence, candidate summary, confidence, and domain-gap disclosure are connected to current UI pages. The genuine saved-zone run covers only zone 1 and produced zero candidates; the second location has not been independently live-verified).

---

## 4. Known Technical Notes & Architecture Decisions
- **Starlette TestClient / AnyIO on Windows Python 3.13**:
  `starlette.testclient.TestClient` deadlocks on Python 3.13 Windows when initiating `anyio.from_thread.start_blocking_portal()`. Do not run synchronous `TestClient` pytest suites that block. Unit and integration tests that verify services, database models, and mathematical/geospatial operations directly (or run async / live HTTP requests) execute flawlessly.
- **Pytest basetemp**:
  Always use `--basetemp=./.pytest_tmp` on this machine to avoid Windows temp directory permission restrictions outside the workspace.
- **Strict Dependency Policy**:
  Do not install or upgrade external dependencies without explicit user consent. All required libraries (`leaflet`, `shapely`, `torch`, `earthengine-api`) are already available.

---

## 5. Next Immediate Steps
1. Reconcile the saved zone 1 area attribute with its authoritative boundary before describing it as a 468.5 ha area. The stored attribute is 468.5 ha and the full stored polygon measures approximately 1,442.4 ha in EPSG:32643. Neither geometry nor database value was changed; no authoritative area is established here.
2. If the submission claims live monitoring of both locations, independently verify acquisition and inference for the second location. Its configuration is implemented, but it has not been live-verified.
3. Demonstrate and record a genuine positive candidate through GIS vectorization, parcel risk assessment, alert persistence, and human review before claiming that end-to-end operational path is verified. Existing seeded demo alerts are not model-generated detections.
4. Preserve candidate-change and human-review language. SNUNet-CD remains the implemented architecture; its LEVIR-CD+ to Sentinel-2 domain gap remains unvalidated and the existing Sentinel-2 training/validation roadmap remains future work.
5. Rasterio 1.5.2 is installed in the backend `.venv` with GDAL 3.12.2 / PROJ 9.7.1. Its required `affine` and `attrs` dependencies are installed; `pip check` is clean. Native GeoTIFF integration passed focused synthetic tests and a small live run; the full saved-zone run is documented below.

## 7. End-to-End Monitoring Demonstration: Integration Milestone
- Saved-zone navigation now carries the selected zone into imagery acquisition; imagery shows actual preview images and native grid, CRS, affine transform, nodata, and polygon-scoped valid-pixel coverage metadata.
- Analysis now presents only native GeoTIFF scenes belonging to the selected zone, defaults to a chronologically ordered pair, and sends selected zone/scene IDs. The API independently rejects missing, cross-zone, identical, or reversed-date pairs.
- Completed jobs persist acquisition dates, common-grid CRS/dimensions, valid-pixel count and coverage, total candidate area, per-candidate SNUNet mean/max probability scores, and preview/mask evidence URLs in existing job JSON; detected polygons and composite risk-confidence/area continue to be persisted in existing change/alert records.
- Every extracted region that passes existing minimum-area/pixel filters is persisted, keeping the stored candidate set consistent with the reported total candidate area.
- The Analysis and dashboard views show actual persisted run imagery, acquisition dates, valid coverage, candidate area/count, and confidence. The GIS map renders candidate polygons with area/confidence/date details. Zero-candidate text explicitly avoids claiming absence of change or encroachment.
- SNUNet failure no longer falls back to image-edge differences under the SNUNet label; the job fails visibly instead of storing substitute detections.
- At the time of this integration milestone, the sandbox could not read the user's existing Earth Engine credential file, so a live run was pending. Authentication was later verified from the existing Windows profile and the full saved-zone run completed as documented below. Previously verified 12×12 cached imagery was not used as a proxy. No Sentinel-2 accuracy claim is made; LEVIR-CD+ to Sentinel-2 remains an unvalidated domain shift.

## 8. Live Saved-Zone Demonstration: Completed 2026-11-06
- **Authentication diagnosis/fix:** the workspace sandbox could not read the existing Windows Earth Engine credential file; the same project `.venv`, backend working directory, and Windows account could read it outside the sandbox. The backend uses Application Default / interactive Earth Engine credentials from the existing profile. No duplicate credential was created and no credential content was logged. Backend startup now passes the existing root `.env` key and database/storage settings plus backend `GEE_PROJECT_ID` into the process. The resolved database remains `backend/terraguard.db`, storage remains `backend/storage`, and the backend listens on port 8000.
- **Health:** `/api/health` returned 200. Authenticated `/api/satellite/health` returned 200 with `configured`, dataset `COPERNICUS/S2_SR_HARMONIZED`, and project `terraguard-ai-513908`.
- **Acquired scenes:** saved zone 1 scene IDs 4 and 5, acquired on 2025-02-06 (Sentinel-2B) and 2025-11-10 (Sentinel-2A). PNG previews remain available. Both native TIFFs cover the saved polygon bounds and share EPSG:32643, affine `[10, 0, 788050, 0, -10, 1433710]`, 439×338 dimensions, 10 m pixels, and nodata −9999.0.
- **Valid coverage:** the polygon covers 144,220 grid pixels. Historical valid pixels: 144,220 (100%). Recent valid pixels: 91,412 (63.38%). The common inference mask used the 91,412 pixels valid in both scenes.
- **Inference/persistence:** job 2 (`JOB-0CDA023D`) completed using `SNUNET_CD` and `imagery_source=native_geotiff`; the persisted grid is 439×338 EPSG:32643. At threshold 0.30 it produced zero candidate regions, zero affected area, and no DetectedChange rows. Mean/max valid-pixel outputs were 0.0002/0.0296. The 439×338 zero mask is persisted at `/storage/masks/mask_JOB-0CDA023D.png` and returned HTTP 200. This is a completed model run, not evidence of no land change or encroachment.
- **Area attribute discrepancy:** the database stores `zone.area_hectares=468.5`, but the stored GeoJSON polygon measures approximately 1,442.4 ha when projected to EPSG:32643. The acquired grid covers the complete stored GeoJSON polygon, not a verified 468.5 ha footprint. The existing zone record and geometry were preserved; reconcile with the authoritative boundary before claiming the run represents exactly 468.5 ha.
- **Model limitation:** SNUNet-CD was trained on LEVIR-CD+; Sentinel-2 differs in sensor and resolution. No independent Sentinel-2 validation or accuracy claim is available.
- **Scope and downstream verification:** this is the only monitoring zone with documented genuine Earth Engine acquisition and SNUNet-CD inference. The second location is configured but not independently live-verified. Job `JOB-0CDA023D` completed successfully with zero candidate detections, so a genuine positive GIS → parcel risk → alert → human-review path has not been demonstrated. Alerts and review records in the seeded database are demonstration data, not outputs of this job.

## 6. Review Reference Note
The user asked to use a GitHub Copilot technical review report, but no report file or Page was present in the working directory or visible Page context during this implementation. The current phase selection was verified against the source and this handoff; do not treat unverified review claims as findings. Incorporate the report when it is available.

## 9. Final Read-Only Submission Audit — 2026-11-11
- **Readiness:** working prototype/demo; not a fully validated operational detection system.
- **Live scope:** real Earth Engine acquisition and SNUNet-CD inference are recorded for zone 1 only. The second monitoring location is implemented but has not been independently live-verified.
- **Genuine job:** `JOB-0CDA023D` completed successfully from native Sentinel-2 GeoTIFFs and produced zero candidate detections. No change or alert rows were generated by this job. Seeded alerts are demonstration records and must not be presented as model-generated results.
- **End-to-end claim boundary:** no genuine positive detection has demonstrated the GIS polygon → parcel risk → alert persistence → human-review workflow. Phase 8 remains unchecked: implementation and synthetic regressions exist, but positive live verification is outstanding. Phase 9 remains in progress.
- **Area:** the stored zone attribute is 468.5 ha; the full stored polygon is approximately 1,442.4 ha in EPSG:32643. The authoritative area/boundary remains unresolved; neither was changed or inferred.
- **Backend tests:** the latest explicit repository-recorded focused result is 23 passed; no full-suite result is recorded. No evidence substantiating a 96-test result was found in the repository records.
- **Model roadmap:** retain the SNUNet-CD architecture and existing Sentinel-2 training/validation roadmap. The LEVIR-CD+ checkpoint has no independent Sentinel-2 accuracy validation; this audit did not retrain or replace it.
