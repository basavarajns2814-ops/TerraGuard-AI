import io
import zipfile

import numpy as np
import pytest
import rasterio
import torch
from PIL import Image
from shapely.geometry import box, mapping, shape
from rasterio.transform import from_origin
from rasterio.warp import transform_geom

from app.services.geospatial_preprocessing import (
    GeospatialAlignmentError,
    align_geotiff_pair,
    read_geotiff_scene,
    require_matching_raster_grids,
)
from app.services.gis_change_analysis import GISChangeAnalysisService
from app.services.change_detection.deep_learning import DeepLearningSegmentationStrategy
from app.services.change_detection.service import ChangeDetectionService
from app.services.snunet_service import SNUNetCDInferenceService
from app.services.earth_engine_service import EarthEngineService
from app.config import settings
from app.schemas import SatelliteCompareRequest


def write_test_raster(path, *, transform=None, crs="EPSG:32643", nodata=-9999, width=5, height=4):
    transform = transform or from_origin(500000, 1500000, 10, 10)
    data = np.full((3, height, width), 1200, dtype=np.int16)
    data[:, min(1, height - 1), min(2, width - 1)] = nodata
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=width,
        height=height,
        count=3,
        dtype=data.dtype,
        crs=crs,
        transform=transform,
        nodata=nodata,
    ) as dataset:
        dataset.write(data)
    return data


def test_native_geotiff_read_preserves_grid_pixels_and_nodata(tmp_path):
    raster_path = tmp_path / "scene.tif"
    expected = write_test_raster(raster_path)

    scene = read_geotiff_scene(raster_path)

    assert scene.crs.to_epsg() == 32643
    assert scene.transform == from_origin(500000, 1500000, 10, 10)
    assert (scene.width, scene.height) == (5, 4)
    assert scene.resolution == (10.0, 10.0)
    assert scene.nodata == -9999
    np.testing.assert_array_equal(scene.pixels, np.moveaxis(expected, 0, -1))
    assert not scene.valid_mask[1, 2]
    assert scene.valid_mask.sum() == 19


def test_earth_engine_valid_coverage_counts_pixels_inside_zone_in_raster_crs(tmp_path):
    raster_path = tmp_path / "coverage.tif"
    write_test_raster(
        raster_path,
        transform=from_origin(500000, 1500000, 10, 10),
        width=5,
        height=4,
    )
    geometry = transform_geom(
        "EPSG:32643", "EPSG:4326", mapping(box(500000, 1499980, 500050, 1500000))
    )

    summary = EarthEngineService._valid_pixel_summary(str(raster_path), geometry)

    assert summary == {
        "valid_pixel_count": 9,
        "zone_pixel_count": 10,
        "valid_pixel_coverage_percentage": 90.0,
    }


def test_common_grid_accepts_matching_scenes_and_rejects_transform_mismatch(tmp_path):
    first = tmp_path / "first.tif"
    matching = tmp_path / "matching.tif"
    shifted = tmp_path / "shifted.tif"
    write_test_raster(first)
    write_test_raster(matching)
    write_test_raster(shifted, transform=from_origin(500010, 1500000, 10, 10))

    require_matching_raster_grids(read_geotiff_scene(first), read_geotiff_scene(matching))
    with pytest.raises(GeospatialAlignmentError, match="affine transforms differ"):
        require_matching_raster_grids(read_geotiff_scene(first), read_geotiff_scene(shifted))


def test_common_grid_rejects_crs_mismatch(tmp_path):
    first = tmp_path / "first.tif"
    other_crs = tmp_path / "other_crs.tif"
    write_test_raster(first)
    write_test_raster(other_crs, crs="EPSG:32644")

    with pytest.raises(GeospatialAlignmentError, match="CRS values differ"):
        require_matching_raster_grids(read_geotiff_scene(first), read_geotiff_scene(other_crs))


def test_common_grid_rejects_dimension_mismatch(tmp_path):
    first = tmp_path / "first.tif"
    different_size = tmp_path / "different_size.tif"
    write_test_raster(first)
    write_test_raster(different_size, width=6)

    with pytest.raises(GeospatialAlignmentError, match="dimensions differ"):
        require_matching_raster_grids(read_geotiff_scene(first), read_geotiff_scene(different_size))


def test_alignment_warps_recent_scene_to_historical_grid_and_combines_nodata(tmp_path):
    historical_path = tmp_path / "historical.tif"
    recent_path = tmp_path / "recent.tif"
    write_test_raster(historical_path)
    write_test_raster(
        recent_path,
        transform=from_origin(500010, 1500000, 10, 10),
    )

    aligned = align_geotiff_pair(historical_path, recent_path)

    assert aligned["resampled_recent"] is True
    assert aligned["transform"]["crs"] == "EPSG:32643"
    assert aligned["transform"]["affine"] == [10.0, 0.0, 500000.0, 0.0, -10.0, 1500000.0]
    assert aligned["historical_aligned"].shape == aligned["recent_aligned"].shape == (4, 5, 3)
    assert not aligned["valid_mask"][:, 0].any()


def test_native_affine_maps_polygons_to_wgs84_and_area_uses_projected_metres():
    affine = [10.0, 0.0, 500000.0, 0.0, -10.0, 1500000.0]
    zone_projected = box(500000, 1499960, 500040, 1500000)
    zone_geojson = transform_geom(
        "EPSG:32643", "EPSG:4326", mapping(zone_projected), precision=9
    )
    analysis = GISChangeAnalysisService().extract_change_regions(
        binary_mask=np.full((4, 4), 255, dtype=np.uint8),
        probability_map=np.ones((4, 4), dtype=np.float32),
        transform_info={"crs": "EPSG:32643", "affine": affine, "width": 4, "height": 4},
        zone_geojson=zone_geojson,
        min_area_sqm=1,
        min_pixels=1,
    )

    assert analysis["region_count"] == 1
    assert analysis["total_changed_area_sqm"] == pytest.approx(1600.0, abs=1.0)
    assert analysis["total_changed_area_hectares"] == pytest.approx(0.16)
    polygon = shape(analysis["regions"][0]["geojson"])
    assert polygon.bounds[0] == pytest.approx(75.0, abs=0.001)
    assert polygon.bounds[2] > polygon.bounds[0]
    assert 13.0 < polygon.centroid.y < 14.0


class FixtureSNUNet(torch.nn.Module):
    def __init__(self, base_width=32, pretrained=False):
        super().__init__()
        self.logit = torch.nn.Parameter(torch.tensor(0.5))

    def forward(self, earlier, recent):
        return self.logit.expand(earlier.shape[0], 1, earlier.shape[2], earlier.shape[3])


def write_reflectance_raster(path, value):
    data = np.full((3, 8, 8), value, dtype=np.float32)
    data[:, 0, 0] = -9999.0
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=8,
        height=8,
        count=3,
        dtype="float32",
        crs="EPSG:32643",
        transform=from_origin(500000, 1500000, 10, 10),
        nodata=-9999.0,
    ) as dataset:
        dataset.write(data)


def test_native_geotiff_pixels_reach_snunet_and_nodata_is_excluded(tmp_path, monkeypatch):
    import app.services.snunet_service as snunet_module

    historical_path = tmp_path / "historical.tif"
    recent_path = tmp_path / "recent.tif"
    write_reflectance_raster(historical_path, 0.12)
    write_reflectance_raster(recent_path, 0.24)
    aligned = align_geotiff_pair(historical_path, recent_path)

    checkpoint_path = tmp_path / "fixture.pt"
    fixture_model = FixtureSNUNet()
    torch.save(
        {
            "model_state_dict": fixture_model.state_dict(),
            "configuration": {"base_width": 32, "patch_size": 512},
            "normalization": {"mean": [0, 0, 0], "std": [1, 1, 1]},
        },
        checkpoint_path,
    )
    inference = SNUNetCDInferenceService(
        checkpoint_path=str(checkpoint_path), model_factory=FixtureSNUNet
    )
    captured = {}
    original_infer = inference.infer_probabilities

    def capture_inputs(earlier, later, valid_mask=None):
        captured["earlier"] = earlier.copy()
        captured["later"] = later.copy()
        captured["valid_mask"] = valid_mask.copy() if valid_mask is not None else None
        return original_infer(earlier, later, valid_mask=valid_mask)

    monkeypatch.setattr(inference, "infer_probabilities", capture_inputs)
    monkeypatch.setattr(snunet_module, "snunet_model_service", inference)
    binary_mask, metadata = DeepLearningSegmentationStrategy().detect(
        aligned["historical_aligned"],
        aligned["recent_aligned"],
        {"threshold": 0.5, "valid_data_mask": aligned["valid_mask"]},
    )
    masked_prediction, _ = ChangeDetectionService.apply_valid_data_mask(
        binary_mask, metadata["probability_map"], aligned["valid_mask"]
    )

    np.testing.assert_array_equal(captured["earlier"], aligned["historical_aligned"])
    np.testing.assert_array_equal(captured["later"], aligned["recent_aligned"])
    np.testing.assert_array_equal(captured["valid_mask"], aligned["valid_mask"])
    assert captured["earlier"][1, 1].tolist() == [102, 102, 102]
    assert captured["later"][1, 1].tolist() == [204, 204, 204]
    assert not aligned["valid_mask"][0, 0]
    assert metadata["probability_map"][0, 0] == 0.0
    assert not masked_prediction[0, 0]
    analysis = GISChangeAnalysisService().extract_change_regions(
        masked_prediction,
        ChangeDetectionService.apply_valid_data_mask(
            binary_mask, metadata["probability_map"], aligned["valid_mask"]
        )[1],
        aligned["transform"],
        min_area_sqm=1,
        min_pixels=1,
    )
    assert analysis["total_changed_area_sqm"] == pytest.approx(63 * 100, abs=1.0)


def test_snunet_failure_does_not_substitute_non_model_detections(monkeypatch):
    import app.services.snunet_service as snunet_module

    class FailedInference:
        def infer_probabilities(self, **kwargs):
            raise RuntimeError("checkpoint unavailable")

    monkeypatch.setattr(snunet_module, "snunet_model_service", FailedInference())
    scene = np.zeros((8, 8, 3), dtype=np.uint8)
    with pytest.raises(RuntimeError, match="no substitute detections"):
        DeepLearningSegmentationStrategy().detect(scene, scene, {})


def test_scene_analysis_resolves_geotiff_without_changing_preview_path(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from app.config import settings

    monkeypatch.setattr(settings, "STORAGE_DIR", str(tmp_path))
    scene = SimpleNamespace(
        image_path=str(tmp_path / "preview.png"),
        metadata_json={"raster_url": "/storage/earth_engine/native.tif"},
    )
    resolved = ChangeDetectionService.resolve_scene_raster_path(scene)
    assert resolved == str(tmp_path / "earth_engine" / "native.tif")
    assert scene.image_path.endswith("preview.png")


def test_compare_persists_preview_contract_and_native_raster_metadata(tmp_path, monkeypatch):
    import app.routers.satellite as satellite_router

    request = SatelliteCompareRequest(
        zone_id=3,
        geometry={"type":"Polygon","coordinates":[[[75,13],[75.01,13],[75.01,13.01],[75,13.01],[75,13]]]},
        historical_start_date="2025-01-01", historical_end_date="2025-01-31",
        recent_start_date="2025-02-01", recent_end_date="2025-02-28",
    )

    class Query:
        def filter(self, *args): return self
        def first(self): return None

    class FakeDB:
        def __init__(self): self.added=[]
        def query(self, model): return Query()
        def add(self, item): self.added.append(item)
        def commit(self): pass
        def refresh(self, item): item.id=len(self.added)

    calls=[]
    def acquire(**kwargs):
        calls.append(kwargs)
        number=len(calls)
        return {
            "date": "2025-01-22" if number == 1 else "2025-02-06",
            "cloud_coverage_percentage": 4.0,
            "satellite": "Sentinel-2",
            "image_url": f"/storage/earth_engine/{number}.png",
            "thumbnail_url": f"/storage/earth_engine/{number}.png",
            "raster_url": f"/storage/earth_engine/{number}.tif",
            "geotiff_url": f"/storage/earth_engine/{number}.zip",
            "width": 512, "height": 512,
            "raster_width": 5, "raster_height": 5,
            "resolution_meters": 10, "crs": "EPSG:32643",
            "transform": [10, 0, 500000, 0, -10, 1500040],
            "nodata": -9999.0, "processing_status": "completed",
        }

    monkeypatch.setattr(settings, "STORAGE_DIR", str(tmp_path))
    monkeypatch.setattr(satellite_router.earth_engine_service, "acquire", acquire)
    db=FakeDB()
    response=satellite_router.satellite_compare(request, db=db, current_user=object())

    assert len(calls) == 2 and len(db.added) == 2
    assert all(scene.image_path.endswith(".png") for scene in db.added)
    assert db.added[0].metadata_json["raster_url"].endswith("1.tif")
    assert db.added[1].metadata_json["raster_url"].endswith("2.tif")
    assert response.historical.image_url.endswith("1.png")
    assert response.recent.image_url.endswith("2.png")


class FakeMask:
    def bitwiseAnd(self, value): return self
    def eq(self, value): return self
    def And(self, other): return self


class FakeGeometry:
    def transform(self, projection, max_error): return self
    def bounds(self, max_error, projection): return self
    def coordinates(self): return self
    def getInfo(self):
        return [[
            [500001, 1499999], [500041, 1499999], [500041, 1500039],
            [500001, 1500039], [500001, 1499999],
        ]]


class FakeGeometryFactory:
    def __call__(self, geometry): return FakeGeometry()
    def Rectangle(self, bounds, proj, geodesic): return FakeGeometry()


class FakeImage:
    download_parameters = None
    def select(self, bands): return FakeMask() if isinstance(bands, str) and bands in {"QA60", "SCL"} else self
    def bitwiseAnd(self, value): return self
    def eq(self, value): return self
    def And(self, other): return self
    def neq(self, value): return self
    def divide(self, value): return self
    def clip(self, geometry): return self
    def geometry(self): return FakeGeometry()
    def updateMask(self, mask): return self
    def unmask(self, value, same_footprint): return self
    def getThumbURL(self, params): return "thumb://preview"
    def getDownloadURL(self, params):
        FakeImage.download_parameters = params
        return "download://raster"


class FakeImageCollection:
    def filterBounds(self, geometry): return self
    def filterDate(self, start, end): return self
    def filter(self, expression): return self
    def sort(self, key): return self
    def size(self): return type("Size", (), {"getInfo": lambda self: 1})()
    def first(self):
        return type("Scene", (), {
            "select": lambda self, bands: FakeImage(),
            "geometry": lambda self: FakeGeometry(),
            "toDictionary": lambda self, fields: type(
                "Properties", (), {"getInfo": lambda self: {
                    "system:time_start": 1705276800000,
                    "CLOUDY_PIXEL_PERCENTAGE": 4.0,
                    "SPACECRAFT_NAME": "Sentinel-2A",
                }}
            )(),
        })()


class FakeEarthEngine:
    Geometry = FakeGeometryFactory()
    Filter = type("Filter", (), {"lt": staticmethod(lambda *args: object())})
    Image = staticmethod(lambda image: image)
    ImageCollection = staticmethod(lambda dataset: FakeImageCollection())
    Projection = staticmethod(lambda crs: crs)
    Initialize = staticmethod(lambda **kwargs: None)


class FakeHttpResponse:
    def __init__(self, content): self.content = content
    def raise_for_status(self): pass


class FakeHttpSession:
    def __init__(self, raster_archive): self.raster_archive = raster_archive
    def get(self, url, timeout):
        if url.startswith("thumb://"):
            image = Image.new("RGB", (8, 8), color=(40, 50, 60))
            buffer = io.BytesIO()
            image.save(buffer, format="PNG")
            return FakeHttpResponse(buffer.getvalue())
        return FakeHttpResponse(self.raster_archive)


def test_earth_engine_keeps_png_preview_and_exports_same_crs_affine_geotiff(tmp_path, monkeypatch):
    raster_buffer = io.BytesIO()
    data = np.full((3, 5, 5), 0.2, dtype=np.float32)
    data[:, 2, 2] = -9999.0
    with rasterio.open(
        raster_buffer,
        "w",
        driver="GTiff",
        width=5,
        height=5,
        count=3,
        dtype="float32",
        crs="EPSG:32643",
        transform=from_origin(500000, 1500040, 10, 10),
    ) as dataset:
        dataset.write(data)
    archive_buffer = io.BytesIO()
    with zipfile.ZipFile(archive_buffer, "w") as archive:
        archive.writestr("export.tif", raster_buffer.getvalue())

    monkeypatch.setattr(settings, "GEE_PROJECT_ID", "test-earth-engine-project")
    monkeypatch.setattr(settings, "GEE_SERVICE_ACCOUNT_KEY_FILE", None)
    service = EarthEngineService(
        ee_module=FakeEarthEngine(), storage_dir=str(tmp_path),
        session=FakeHttpSession(archive_buffer.getvalue()),
    )
    result = service.acquire(
        geometry={"type": "Polygon", "coordinates":[[[75.0,13.0],[75.01,13.0],[75.01,13.01],[75.0,13.01],[75.0,13.0]]]},
        start_date="2024-01-01", end_date="2024-01-31",
    )

    preview_path = tmp_path / "earth_engine" / result["image_url"].split("/")[-1]
    raster_path = tmp_path / "earth_engine" / result["raster_url"].split("/")[-1]
    assert preview_path.is_file()
    assert Image.open(preview_path).format == "PNG"
    with rasterio.open(raster_path) as dataset:
        assert dataset.crs.to_string() == "EPSG:32643"
        assert tuple(dataset.transform)[:6] == tuple(FakeImage.download_parameters["crs_transform"])
        assert (dataset.width, dataset.height) == (5, 5)
        assert dataset.nodata == -9999.0
        assert dataset.read_masks(1)[2, 2] == 0
    assert FakeImage.download_parameters["crs"] == "EPSG:32643"
    assert result["width"] == 512 and result["height"] == 512
