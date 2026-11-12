import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.earth_engine_service import (
    EarthEngineCollectionEmptyError,
    EarthEngineService,
)
from app.config import settings
from app.schemas import SatelliteCompareRequest


client = TestClient(app)


def login():
    response = client.post(
        "/api/auth/login",
        json={"email": "officer@terraguard.gov.in", "password": "Officer@123"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def valid_geometry():
    return {
        "type": "Polygon",
        "coordinates": [[
            [77.6550, 12.9250],
            [77.6950, 12.9250],
            [77.6950, 12.9550],
            [77.6550, 12.9550],
            [77.6550, 12.9250],
        ]],
    }


def test_earth_engine_health_requires_authentication():
    response = client.get("/api/satellite/health")
    assert response.status_code == 401


def test_earth_engine_health_response_is_structured_without_credentials():
    headers = login()
    response = client.get("/api/satellite/health", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["dataset"] == "COPERNICUS/S2_SR_HARMONIZED"
    assert data["status"] in {"configured", "unavailable"}


def test_date_validation():
    EarthEngineService.validate_date_range("2024-01-01", "2024-01-31")
    with pytest.raises(ValueError):
        EarthEngineService.validate_date_range("2024-02-01", "2024-01-31")
    with pytest.raises(ValueError):
        EarthEngineService.validate_date_range("not-a-date", "2024-01-31")


def test_geometry_validation_accepts_polygon_and_rejects_invalid_geometry():
    geometry = EarthEngineService.validate_geometry(valid_geometry())
    assert geometry["type"] == "Polygon"
    with pytest.raises(ValueError):
        EarthEngineService.validate_geometry({"type": "Point", "coordinates": [77, 12]})
    with pytest.raises(ValueError):
        EarthEngineService.validate_geometry({"type": "Polygon", "coordinates": []})


def test_request_validation_bounds():
    service = EarthEngineService()
    with pytest.raises(ValueError):
        service.validate_request("2024-01-01", "2024-01-31", 101, 512, 512, 10)
    with pytest.raises(ValueError):
        service.validate_request("2024-01-01", "2024-01-31", 30, 128, 512, 10)
    with pytest.raises(ValueError):
        service.validate_request("2024-01-01", "2024-01-31", 30, 512, 512, 5)


def test_compare_request_requires_ordered_non_overlapping_date_windows():
    base = {
        "historical_start_date": "2024-01-01",
        "historical_end_date": "2024-01-31",
        "recent_start_date": "2024-02-01",
        "recent_end_date": "2024-02-29",
    }
    SatelliteCompareRequest(**base)
    with pytest.raises(ValueError, match="must start after"):
        SatelliteCompareRequest(**{**base, "recent_start_date": "2024-01-31"})
    with pytest.raises(ValueError, match="Historical start date"):
        SatelliteCompareRequest(**{**base, "historical_start_date": "2024-02-01"})


def test_preview_authentication_and_validation():
    unauthenticated = client.post(
        "/api/satellite/preview",
        json={
            "geometry": valid_geometry(),
            "start_date": "2024-01-01",
            "end_date": "2024-01-31",
        },
    )
    assert unauthenticated.status_code == 401

    headers = login()
    invalid = client.post(
        "/api/satellite/preview",
        headers=headers,
        json={
            "geometry": {"type": "Point", "coordinates": [77, 12]},
            "start_date": "2024-01-01",
            "end_date": "2024-01-31",
        },
    )
    assert invalid.status_code == 422


def test_mocked_initialization_uses_configured_project(monkeypatch):
    calls = {}

    class FakeEE:
        def Initialize(self, **kwargs):
            calls.update(kwargs)

    monkeypatch.setattr(settings, "GEE_PROJECT_ID", "test-cloud-project")
    monkeypatch.setattr(settings, "GEE_SERVICE_ACCOUNT_KEY_FILE", None)
    service = EarthEngineService(ee_module=FakeEE())
    result = service.initialize()
    assert result["initialized"] is True
    assert calls["project"] == "test-cloud-project"


def test_mocked_empty_collection_is_not_synthetic(monkeypatch):
    monkeypatch.setattr(settings, "GEE_PROJECT_ID", "test-cloud-project")
    monkeypatch.setattr(settings, "GEE_SERVICE_ACCOUNT_KEY_FILE", None)

    class EmptySize:
        def getInfo(self):
            return 0

    class EmptyCollection:
        def size(self):
            return EmptySize()

    class Filter:
        def lt(self, *args):
            return object()

    fake_filter = Filter()

    class FakeImageCollection:
        def filterBounds(self, *args):
            return self

        def filterDate(self, *args):
            return self

        def filter(self, *args):
            return self

        def sort(self, *args):
            return EmptyCollection()

    class FakeEE:
        Filter = fake_filter

        def Initialize(self, **kwargs):
            pass

        def Geometry(self, geometry):
            return geometry

        def ImageCollection(self, name):
            return FakeImageCollection()

    service = EarthEngineService(ee_module=FakeEE())
    with pytest.raises(EarthEngineCollectionEmptyError):
        service.acquire(
            geometry=valid_geometry(),
            start_date="2024-01-01",
            end_date="2024-01-31",
        )
