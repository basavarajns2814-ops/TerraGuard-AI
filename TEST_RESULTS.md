# TerraGuard AI — Test Execution & Verification Log

## Test Environment
- **Platform**: Windows 11
- **Python**: 3.13.5 (`.\.venv`)
- **Node**: Vite 5.4.21 / TypeScript 5.2.2

---

## Baseline Verification (Phase 1)

| Test Suite / Target | Description | Status | Notes |
| :--- | :--- | :--- | :--- |
| **Frontend Production Build** | `npm --prefix frontend run build` (`tsc && vite build`) | **PASSED** | Built in 15.80s with 0 TS errors. |
| **EXP-02 Checkpoint Loading** | `backend/tests/test_snunet_integration.py::test_actual_exp02_checkpoint_loads_and_reports_epoch_ten` | **PASSED** | Model loaded with `base_width=32`, 7.79M params, epoch 10. |
| **SNUNet Normalization & Inference** | `test_snunet_integration.py` (7 direct service tests) | **PASSED** | Tiled edge-aligned inference on $300\times300$, $512\times512$, $900\times900$ verified. |
| **Database Demonstration Seeding** | Direct execution of `app.seed.seed_database_if_empty()` | **PASSED** | Seeding completes in 0.96s with Karnataka monitoring zones and demo records. |
| **Google Earth Engine Integration** | `ee.Initialize(project="terraguard-ai-513908")` | **VERIFIED** | Connected and queries Sentinel-2 SR Harmonized. |
| **FastAPI TestClient AnyIO (Pytest)** | Starlette `TestClient` tests via pytest | **SKIPPED / WINDOWS ISSUE** | Known deadlock in `anyio.from_thread.start_blocking_portal()` on Python 3.13 Windows. Alternative verification used. |

---

## Phase-by-Phase Verification Log

### Phase 2: Real Area Monitoring & Interactive Polygon Management
| Test Target | Description | Result | Details |
| :--- | :--- | :--- | :--- |
| **Geometry Validation (Valid)** | `test_validate_and_compute_zone_geometry_valid_polygon` | **PASSED** | Validates GeoJSON Polygon ring, calculates ~270 ha geodesic area. |
| **Self-Intersecting Rejection** | `test_validate_and_compute_zone_geometry_self_intersecting_rejected` | **PASSED** | Detects bowtie/self-intersection and rejects with HTTP 422. |
| **Out-of-Bounds Rejection** | `test_validate_and_compute_zone_geometry_out_of_bounds_rejected` | **PASSED** | Rejects invalid coordinate ranges outside [-180, 180], [-90, 90]. |
| **Database Zone CRUD** | `test_zone_crud_in_database` | **PASSED** | Create, query, update, and delete monitoring zones in SQLite DB. |
| **Frontend Production Build** | `npm --prefix frontend run build` | **PASSED** | TypeScript + Vite compiled with 0 errors in 15.30s. |

### Phase 4: Dual-Date Acquisition & Verification (Completed)
| Test Target | Description | Result | Details |
| :--- | :--- | :--- | :--- |
| **Compare Date Window Validation** | `test_compare_request_requires_ordered_non_overlapping_date_windows` | **PASSED** | Accepts ordered non-overlapping windows; rejects overlap and reversed historical dates. |
| **Valid Compare + Scene Persistence** | Direct focused call to `satellite_compare` with mocked Earth Engine acquisition and DB session | **PASSED** | Ordered January/February windows invoked acquisition twice in order and persisted historical/recent scene records with IDs 1 and 2. |
| **Earth Engine Initialization Compatibility** | `test_mocked_initialization_uses_configured_project` | **PASSED** | Existing configured project initialization behavior remains intact. |
| **Empty Collection Compatibility** | `test_mocked_empty_collection_is_not_synthetic` | **PASSED** | Existing no-imagery behavior still raises the explicit empty-collection condition. |
| **Focused regression run** | Three targeted Earth Engine integration tests with `--basetemp=./.pytest_tmp` | **PASSED** | 3 passed. Environment emitted Starlette/httpx deprecation and restricted pytest cache-directory warnings. No full suite run. |

**Date-window diff verification:** inspected `git diff -- backend/app/schemas.py`; `SatelliteCompareRequest.validate_temporal_order` is the only new validator logic. It parses all four ISO dates, rejects reversed windows and requires the recent start to be later than the historical end. Other uncommitted schema additions shown in the same file predate this validation change and were preserved.

### Phase 5–7 Integration Milestone: Valid-Pixel Mask Through Vectorization
| Test Target | Description | Result | Details |
| :--- | :--- | :--- | :--- |
| **Invalid Pixel Exclusion** | `test_invalid_pixels_are_excluded_from_mask_and_probability_map` | **PASSED** | Invalid pixels are zeroed in model mask and probability map before GIS region extraction. |
| **Mask Shape Guard** | `test_valid_data_mask_rejects_mismatched_dimensions` | **PASSED** | A mask with incompatible dimensions is rejected explicitly. |
| **Focused regression run** | Valid-pixel tests plus date-window regression | **PASSED** | 3 passed; same environment warnings as above. |

**Initial limit resolved:** new Earth Engine scenes now retain PNGs for display but carry a native `raster_url` in scene metadata; analysis reads those GeoTIFF pixels and their native georeferencing.

### Native GeoTIFF Integration: Milestone 1
| Test Target | Description | Result | Details |
| :--- | :--- | :--- | :--- |
| **Rasterio/GDAL/PROJ imports** | Backend `.venv` import/version check | **PASSED** | Rasterio 1.5.2, GDAL 3.12.2, PROJ 9.7.1; EPSG:32643 CRS roundtrip succeeded. |
| **Dependency consistency** | `python -m pip check` in backend `.venv` | **PASSED** | No broken requirements. Installed Rasterio plus required `affine==3.0.1` and `attrs==26.1.0`; no unrelated package upgrades. |
| **Synthetic native GeoTIFF read/grid tests** | `test_geospatial_raster_pipeline.py` | **PASSED** | 3 passed: preserves pixels, CRS, transform, shape, 10 m resolution and nodata mask; accepts matching grids and rejects transform/CRS mismatch. |

### Native GeoTIFF Integration: End-to-End Verification
| Test Target | Description | Result | Details |
| :--- | :--- | :--- | :--- |
| **Earth Engine common-grid exports** | Live small-area acquisition for historical and recent date windows | **PASSED** | Acquired 2025-01-22 and 2025-02-06. Both EPSG:32643, 10 m, 12×12, identical affine `[10, 0, 782140, 0, -10, 1427620]`, nodata -9999; both PNG preview files exist. |
| **PNG and GeoTIFF contract** | Mocked Earth Engine service acquisition test | **PASSED** | PNG display output retained; exported GeoTIFF CRS/affine/dimensions/nodata validated; compare persistence keeps `image_path` on PNG and stores `raster_url` metadata. |
| **Native raster to trained SNUNet** | Live acquired pair through Rasterio preprocessing and EXP-02 checkpoint | **PASSED** | Epoch 10 checkpoint loaded; 12×12 aligned raster arrays reached inference; 144 valid pixels; invalid output pixels: 0. Model produced 0 candidate regions for this sample. |
| **Projected polygon and area** | Synthetic EPSG:32643 4×4 pixel change fixture | **PASSED** | Polygon transformed to expected WGS84 location; computed 1,600 m² / 0.16 ha from 10 m pixels in the projected CRS. |
| **Focused regression set** | Native raster module plus selected existing Earth Engine, SNUNet, and mask tests | **PASSED** | 20 passed; one existing Starlette/httpx deprecation warning. No full suite run. |

The live sample verifies data flow and grid alignment only; its zero detections are not model-accuracy evidence.

### End-to-End Monitoring Integration: Milestone 1
| Test Target | Description | Result | Details |
| :--- | :--- | :--- | :--- |
| **Saved-zone scene pairing** | Direct API route tests for cross-zone, reversed-date, and valid ordered same-zone scene pairs | **PASSED** | Invalid scene pairs return 422; a valid pair creates a pending job and queues the existing worker. Tests use the isolated test DB. |
| **Polygon-scoped valid coverage** | Synthetic EPSG:32643 raster and saved-zone polygon | **PASSED** | Counts valid pixels only inside the transformed polygon (9/10; 90%), preserving nodata exclusion. |
| **No substitute detections** | Force SNUNet inference failure | **PASSED** | SNUNet strategy raises an explicit failure rather than generating edge-difference detections. |
| **Per-candidate model score persistence** | Store SNUNet mean/max probabilities in the detection-job JSON and read them through the changes API | **PASSED** | Synthetic persisted candidate returns the model probability values separately from composite risk confidence. |
| **Focused backend regressions** | Zone pairing, native GeoTIFF pipeline, and Earth Engine integration modules | **PASSED** | 23 passed, one existing Starlette/httpx deprecation warning. No full suite run. |
| **Frontend production build** | `npm.cmd --prefix frontend run build` | **PASSED** | TypeScript and Vite production build completed; Vite reports the existing >500 kB chunk advisory. |
| **Saved-zone live acquisition** | Historical/recent acquisition for saved zone 1's stored polygon footprint | **PASSED — see live run below** | Initial attempt was blocked by sandbox access to the existing credential file. The backend was restarted with the existing project environment and credentials; native scenes and a persisted SNUNet job were then verified. |

This milestone connects saved-zone acquisition metadata, native-only analysis selection, existing job/change/alert persistence, and dashboard/GIS evidence presentation. A live saved-zone run is recorded below. The LEVIR-CD+ checkpoint has not been independently validated on Sentinel-2; model confidence is not an accuracy measure. A zero-candidate run does not establish absence of change or encroachment.

### Live Saved-Zone Demonstration: 2026-11-06
| Test Target | Description | Result | Details |
| :--- | :--- | :--- | :--- |
| **Credential discovery and runtime context** | Initialize Earth Engine from the project `.venv` outside the restricted sandbox; verify backend process uses that interpreter, Windows profile, backend working directory, and project ID | **PASSED** | Existing Earth Engine credentials were readable and initialized successfully for `terraguard-ai-513908`; no key contents were printed and no duplicate credentials were created. Backend API was restarted on port 8000 with the existing stable app key and the same database/storage paths. |
| **Backend health endpoints** | HTTP `/api/health` and authenticated `/api/satellite/health` | **PASSED** | Both returned 200. Satellite health reports configured, `COPERNICUS/S2_SR_HARMONIZED`, and `terraguard-ai-513908`. |
| **Saved zone 1 acquisition** | Full polygon, historical 2025-01-01..2025-03-31 and recent 2025-09-01..2025-11-30 | **PASSED** | Persisted scene IDs 4/5; actual dates 2025-02-06 and 2025-11-10. Both exports cover the stored polygon bounds, retain preview PNGs, and have identical EPSG:32643 / 10 m / 439×338 grid and affine `[10, 0, 788050, 0, -10, 1433710]`; nodata −9999.0. |
| **Polygon-scoped validity** | Rasterio validity and geometry-mask check on both actual TIFFs | **PASSED** | 144,220 polygon pixels; historical 144,220 valid (100%), recent 91,412 valid (63.38%). Inference used the 91,412-pixel intersection mask. |
| **Actual native SNUNet job** | POST `/api/analysis/run` for saved zone 1, scenes 4/5, `SNUNET_CD`, threshold 0.30 | **PASSED — 0 candidates** | Persisted job 2 `JOB-0CDA023D` completed from native GeoTIFFs. 439×338 EPSG:32643; mean/max valid-pixel probabilities 0.0002/0.0296; zero candidate polygons and 0 ha detected. This does not establish that the area has no change or encroachment. |
| **Persisted GIS evidence** | Read-only DB and static evidence check | **PASSED** | Job record is completed with scene IDs, acquisition dates, CRS, valid coverage, totals and mask URL. No `DetectedChange` rows were fabricated. The 439×338 zero mask is stored and its endpoint returns HTTP 200. |

**Saved-area label discrepancy discovered:** zone 1's database attribute says 468.5 ha, while its stored GeoJSON area is approximately 1,442.4 ha in EPSG:32643. The rasters cover the full stored polygon, not a verified 468.5 ha footprint. No existing zone data was changed; confirm the authoritative boundary/area before labeling this demonstration “468.5 ha.”

---

## Final Read-Only Submission Audit — 2026-11-11

This audit updated documentation only; it did not run tests, acquire imagery, or change application data. TerraGuard is a working prototype/demo, not a fully validated operational detection system.

| Audit finding | Status | Evidence boundary |
| :--- | :--- | :--- |
| **Latest explicit backend regression result** | **23 FOCUSED TESTS PASSED** | Latest recorded focused run is the zone-pairing, native GeoTIFF pipeline, and Earth Engine integration modules (23 passed, one existing Starlette/httpx deprecation warning). No full-suite result is recorded. No repository evidence substantiates a claim of 96 tests passed. |
| **Genuine Earth Engine acquisition and SNUNet-CD inference** | **VERIFIED FOR ONE ZONE ONLY** | Saved monitoring zone 1; acquisition dates 2025-02-06 and 2025-11-10. No fresh acquisition occurred during this audit. |
| **Persisted genuine job `JOB-0CDA023D`** | **COMPLETED — ZERO CANDIDATES** | Native GeoTIFF SNUNet-CD job completed successfully with zero candidate polygons, zero affected area, and no associated detected-change or alert records. This is not evidence that no change exists. |
| **GIS → parcel risk → alert → human review on a genuine positive result** | **NOT DEMONSTRATED** | GIS, risk, and review implementations have focused/synthetic coverage, but the only documented genuine SNUNet run had no candidates. Seeded demo alerts/review records are not model-generated detections. |
| **Second monitoring location** | **IMPLEMENTED, NOT LIVE-VERIFIED** | A second location is configured; independent live acquisition and inference evidence is absent. |
| **Monitoring zone 1 area** | **UNRESOLVED** | Stored area is 468.5 ha; the full stored polygon is approximately 1,442.4 ha in EPSG:32643. No authoritative area was established and no geometry/database value was changed. |
| **Sentinel-2 model accuracy** | **NOT VALIDATED** | SNUNet-CD remains the existing LEVIR-CD+ architecture/checkpoint. Sentinel-2 accuracy is not established; preserve the existing Sentinel-2 training/validation roadmap. |

The 23-test result is focused regression evidence, not live end-to-end proof. Phase 8 risk scoring and parcel-association implementation and synthetic regression tests are present, but no separate executed result for those parcel/risk tests is recorded here; Phase 8 remains unchecked pending genuine positive-path verification. Phase 9 remains in progress. No new test or runtime verification was performed for this audit.
