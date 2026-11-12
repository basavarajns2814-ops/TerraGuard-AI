# TerraGuard AI — Implementation Changelog

All changes adhere to the principle of preserving existing working functionality, maintaining strict type safety, preserving security and audit logging, and building genuine geospatial and AI pipelines.

---

## [Phase 1: Architecture Audit & Strategy Approval] — 2026-11-06
- Completed deep inspection of backend (`routers`, `services`, `models`, `database`, `config`), frontend (`pages`, `components`, `api`, `types`), and `training` (`EXP-02_SNUNet`).
- Verified trained SNUNet-CD checkpoint integrity (`best.pt`, 7.79M params, epoch 10).
- Verified Google Earth Engine authentication and initialization (`terraguard-ai-513908`).
- Identified architecture gaps: missing zone update/delete endpoints, hardcoded polygon coordinates in modal, missing interactive Leaflet polygon drawer, decoupled Earth Engine to AI inference pipeline.
- Created `PROJECT_HANDOFF.md`, `TEST_RESULTS.md`, and `CHANGELOG.md`.

---

## [Phase 2: Real Area Monitoring & Interactive Polygon Management] — 2026-11-06 (COMPLETED)
- **Backend API Extensions** (`backend/app/routers/zones.py`, `backend/app/schemas.py`):
  - Added `MonitoringZoneUpdate` schema.
  - Added `PUT /api/zones/{zone_id}` for editing boundary geometry, district, and metadata.
  - Added `DELETE /api/zones/{zone_id}` with cascade cleanup of associated detections and scenes.
  - Expanded role permissions on `POST /api/zones` to include `MONITORING_OFFICER`.
  - Added `validate_and_compute_zone_geometry` enforcing polygon closure, minimum 3 vertices, valid coordinate ranges, self-intersection rejection via Shapely, and geodesic area calculation in hectares.
- **Frontend Interactive GIS Map** (`frontend/src/components/GISMapViewer.tsx`, `frontend/src/pages/GISMap.tsx`):
  - Implemented interactive Leaflet polygon drawing with click-to-add vertices, polyline/polygon preview, draggable vertex markers, and click-to-close on first vertex.
  - Added real-time geodesic area calculator HUD showing square meters and hectares.
  - Added Basemap provider switcher: Satellite Imagery (Esri World Imagery), Dark GIS (CartoDB), and Street Map (OSM).
  - Added Karnataka location presets (Bellandur, Varthur, Bannerghatta, Hebbal, Sarjapur, Whitefield, Mysuru, Hubballi) and lat/lng geocoding.
  - Added "Save New Monitoring Area" modal with automatic area population.
  - Added Zone inspection side panel with actions to Acquire Satellite Scenes, View on Map, or Delete.
- **Frontend API Client** (`frontend/src/api/client.ts`):
  - Added `updateZone(zoneId, data)` and `deleteZone(zoneId)` methods.
- **Verification**:
  - `backend/tests/test_zone_monitoring.py`: All 4 unit/integration tests passed.
  - Frontend production build: Passed with 0 errors.

---

## [Phase 3: Connect Monitored Boundaries to Earth Engine] — Verified Complete
- Source comparison confirmed authenticated preview/compare endpoints resolve stored zone geometry, acquire Sentinel-2 imagery, and persist acquired scenes for saved zones. Remaining work is temporal validation and reliable raster-pair processing, tracked in later phases.

## [Phase 4: Dual-Date Acquisition & Verification] — Completed for Saved Zone 1
- Verified that authenticated Earth Engine preview/compare routes, monitoring-zone geometry lookup, and acquisition scene persistence already exist; the review finding should not claim these features are absent.
- Added validation to `SatelliteCompareRequest` so date strings must be ISO formatted, each date window must be ordered, and the recent window must begin after the historical window ends. This prevents overlapping or reversed pairs from reaching Earth Engine.
- Added a focused schema regression test. Result: passed (1 test); pytest emitted existing environment warnings about Starlette/httpx deprecation and restricted backend cache creation.
- Live historical and recent Sentinel-2 acquisition and verification were completed for saved zone 1, as detailed in the live saved-zone demonstration below. This completion does not establish live verification for the second monitoring location.
- The Copilot technical review report was not available in the project files or Page context; this phase was selected from source verification and `PROJECT_HANDOFF.md`.

## [Phases 5–7: Geospatial Inference Integration] — Completed
- Verified the existing run path loads two saved scene images, invokes SNUNet-CD through the detection strategy, vectorizes the cleaned mask, and computes polygon areas geodesically.
- Updated the run path to mask invalid pixels from both the binary prediction and probability map before vector extraction, and reapply the mask after morphology so dilation cannot expand detections into no-data pixels.
- Added focused tests for exclusion and dimension mismatch; 3 selected tests passed (including date-window regression).
- The initial preview-PNG/bounds-derived analysis path was replaced for new Earth Engine scenes by the native GeoTIFF path described below; legacy uploaded/demo scenes keep their existing image workflow.

## [Native GeoTIFF Integration: Milestone 1] — Reader and Grid Validation
- Added pinned `rasterio==1.5.2` to backend requirements and installed only it plus its required `affine==3.0.1` and `attrs==26.1.0` packages in the existing backend `.venv`.
- Verified Rasterio 1.5.2, GDAL 3.12.2, and PROJ 9.7.1 imports and confirmed `pip check` reports no broken requirements.
- Added a native GeoTIFF reader preserving RGB-band values, CRS, affine transform, width/height, pixel resolution, nodata metadata, and per-band validity masks; added strict matching-grid validation.
- Synthetic tests passed (3): pixel/metadata/nodata preservation, matching grid acceptance, and CRS/transform mismatch rejection.
- Earth Engine now downloads each acquisition on a snapped local WGS84 UTM grid using the same CRS, affine transform, dimensions, and pixel resolution for the same saved zone. Cloud/nodata pixels are explicitly filled with a declared -9999 nodata value and the downloaded GeoTIFF is validated before scene use.
- Cached GeoTIFFs are revalidated against their requested grid before reuse; invalid cache entries trigger reacquisition.
- PNG preview URLs and `SatelliteScene.image_path` remain unchanged for existing display and image consumers. The native `raster_url` is persisted in scene metadata and resolved from inside the configured storage root by the analysis pipeline.
- Rasterio aligns the recent image onto the historical grid if metadata differs, reads all masks, and derives SNUNet input RGB values from the TIFF reflectance bands. SNUNet receives a validity mask; invalid pixels are neutralized after normalization and zeroed in the probability output. The existing post-inference and post-morphology mask guards remain in place.
- GIS vectorization uses the full raster affine, clips in the projected monitoring zone, calculates affected area in projected square metres, and transforms result polygons to WGS84 GeoJSON.
- Verification: live Earth Engine acquired 2025-01-22 and 2025-02-06 samples with identical EPSG:32643 10 m 12×12 grids and working PNG previews. The aligned actual TIFF arrays reached the epoch-10 checkpoint; the small sample produced no candidate polygons. Synthetic tests confirmed valid-grid checks, reprojection, nodata exclusion, WGS84 positioning, and 1,600 m² area calculation.
- Focused regression run: 20 passed (one existing Starlette/httpx deprecation warning). No full suite run; no checkpoints, weights, datasets, or database records were modified.

## [End-to-End Monitoring Integration: Milestone 1] — 2026-11-06
- Passed the selected monitoring-zone ID from Monitoring Areas into the Imagery acquisition page. The acquisition view now reports native raster dimensions, CRS, affine, resolution, nodata-related metadata, and valid pixel coverage within the saved polygon while retaining PNG previews.
- Added a Rasterio polygon-scoped coverage summary to Earth Engine acquisition metadata and persisted it with each scene.
- Restricted the real-area Analysis selectors to native GeoTIFF scenes from the chosen zone, ordered by acquisition date; added an acquire-scenes route for zones without a native pair.
- Hardened `POST /api/analysis/run` against missing zones/scenes, cross-zone scene pairs, identical scenes, and non-chronological pairs.
- Persisted common-grid valid-pixel coverage, acquisition dates, CRS/dimensions, candidate area totals, model-score summary, image URLs, and mask evidence URL in the existing detection job parameters. GIS now renders stored candidate polygons and exposes area, confidence, and acquisition dates; dashboard displays imagery and run evidence.
- Persisted each candidate polygon’s mean and maximum SNUNet probabilities in existing job JSON and returned them through the changes API, separately from the combined risk-confidence score.
- Removed the persistence cap on the top 25 candidate regions so persisted polygon records match the extracted candidate set and reported total area; the existing minimum-pixel parameter is now honored as well.
- Removed the SNUNet strategy's edge-difference fallback so failed checkpoint/model execution fails the job instead of creating substitute detections under the SNUNet label.
- Added focused regressions for date/zone pairing, polygon-scoped nodata coverage, and inference failure behavior. Result: 23 backend tests passed. Frontend production build passed (Vite emitted its existing large-chunk advisory).
- The initial full-footprint acquisition attempt was blocked because the restricted process could not read the existing Windows Earth Engine credential file. This was resolved in the follow-up live demonstration below; the older 12×12 sample was not used as a substitute. No Sentinel-2 accuracy claim is made.

## [Live Saved-Zone Demonstration: Authentication and Execution] — 2026-11-06
- Diagnosed the authentication difference: the restricted workspace process could not access the existing Windows Earth Engine credential file, but the existing project `.venv` under the same Windows profile initialized successfully outside the sandbox. Reused existing Earth Engine credentials; created no duplicate key and printed no credential contents.
- Restarted FastAPI on port 8000 using `C:\projects\TerraGuard-AI\.venv\Scripts\python.exe`, backend working directory, existing `terraguard-ai-513908` GEE setting, existing root `.env` secret, and unchanged backend database/storage paths. `/api/health` and authenticated `/api/satellite/health` both returned HTTP 200.
- Acquired and persisted real saved-zone 1 scenes (IDs 4/5; 2025-02-06 and 2025-11-10). Full stored polygon bounds are covered on identical EPSG:32643 10 m 439×338 grids with the same affine and nodata. Polygon-scoped valid coverage is 100% historical and 63.38% recent; inference used their 91,412-pixel intersection.
- Ran persisted native GeoTIFF SNUNet job 2 (`JOB-0CDA023D`) to completion. It produced zero candidates, 0 ha, and no change/alert geometry. Mean/max valid-pixel model scores were 0.0002/0.0296; the real 439×338 zero mask is persisted and served successfully. This is not proof of no change or encroachment.
- Verified a pre-existing area metadata inconsistency: zone 1 says 468.5 ha, but its full stored GeoJSON polygon measures about 1,442.4 ha in EPSG:32643. The complete GeoJSON footprint was acquired; no existing boundary or database value was edited. Reconcile the authoritative area before claiming the live run represents exactly 468.5 ha.

## [Final Read-Only Submission Audit] — 2026-11-11
- Recorded TerraGuard's status as a working prototype/demo, not a fully validated operational detection system.
- Clarified that genuine Earth Engine acquisition and SNUNet-CD inference are documented for zone 1 only; the second configured monitoring location has not been independently live-verified.
- Recorded job `JOB-0CDA023D` as completed successfully with zero candidate detections, zero affected area, and no job-generated change or alert records. Seeded demo alerts and review records are distinct from model-generated detections.
- Clarified that a genuine positive GIS polygon → parcel risk → alert persistence → human-review workflow has not yet been demonstrated. Phase 8 remains unchecked despite implementation and synthetic regression coverage; Phase 9 remains in progress.
- Reiterated the unresolved area discrepancy: 468.5 ha stored versus approximately 1,442.4 ha for the stored polygon in EPSG:32643. No authoritative area was invented and no geometry/database value was changed.
- Recorded 23 focused backend tests as the latest explicit repository-recorded result. No full-suite or verifiable 96-test result is claimed.
- Preserved the existing SNUNet-CD architecture and Sentinel-2 training/validation roadmap. No code, model, data, tests, or runtime behavior was changed or newly verified during this documentation-only audit.
