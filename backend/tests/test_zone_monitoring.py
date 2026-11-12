import pytest
from app.database import SessionLocal
from app.models import MonitoringZone, User
from app.routers.zones import validate_and_compute_zone_geometry
from fastapi import HTTPException


def test_validate_and_compute_zone_geometry_valid_polygon():
    # Valid polygon around Bellandur lake
    valid_geojson = {
        "type": "Polygon",
        "coordinates": [[
            [77.6600, 12.9300],
            [77.6750, 12.9300],
            [77.6750, 12.9450],
            [77.6600, 12.9450],
            [77.6600, 12.9300]
        ]]
    }
    geom, area_ha = validate_and_compute_zone_geometry(valid_geojson)
    assert geom["type"] == "Polygon"
    assert area_ha > 0
    # ~1.6km x ~1.6km ~ 256 ha
    assert 200 < area_ha < 350


def test_validate_and_compute_zone_geometry_self_intersecting_rejected():
    # Bowtie polygon (self-intersecting)
    invalid_bowtie = {
        "type": "Polygon",
        "coordinates": [[
            [77.6600, 12.9300],
            [77.6750, 12.9450],
            [77.6600, 12.9450],
            [77.6750, 12.9300],
            [77.6600, 12.9300]
        ]]
    }
    with pytest.raises(HTTPException) as exc_info:
        validate_and_compute_zone_geometry(invalid_bowtie)
    assert exc_info.value.status_code == 422
    assert "invalid" in exc_info.value.detail.lower() or "self-intersecting" in exc_info.value.detail.lower()


def test_validate_and_compute_zone_geometry_out_of_bounds_rejected():
    out_of_bounds = {
        "type": "Polygon",
        "coordinates": [[
            [200.0, 12.9300],
            [201.0, 12.9300],
            [201.0, 12.9450],
            [200.0, 12.9450],
            [200.0, 12.9300]
        ]]
    }
    with pytest.raises(HTTPException) as exc_info:
        validate_and_compute_zone_geometry(out_of_bounds)
    assert exc_info.value.status_code == 422
    assert "bounds" in exc_info.value.detail.lower()


def test_zone_crud_in_database():
    db = SessionLocal()
    test_zone_name = "Automated Test Karnataka Zone"
    try:
        # 1. Create
        geojson = {
            "type": "Polygon",
            "coordinates": [[
                [77.6600, 12.9300],
                [77.6700, 12.9300],
                [77.6700, 12.9400],
                [77.6600, 12.9400],
                [77.6600, 12.9300]
            ]]
        }
        geom, area_ha = validate_and_compute_zone_geometry(geojson)
        zone = MonitoringZone(
            name=test_zone_name,
            district="Bengaluru Urban",
            state="Karnataka",
            description="Created by automated Phase 2 verification",
            area_hectares=area_ha,
            geojson=geom,
            risk_status="NORMAL"
        )
        db.add(zone)
        db.commit()
        db.refresh(zone)

        zone_id = zone.id
        assert zone_id is not None
        assert zone.name == test_zone_name
        assert zone.area_hectares > 0

        # 2. Read
        fetched = db.query(MonitoringZone).filter(MonitoringZone.id == zone_id).first()
        assert fetched is not None
        assert fetched.district == "Bengaluru Urban"

        # 3. Update
        fetched.name = "Automated Test Karnataka Zone Updated"
        db.commit()
        db.refresh(fetched)
        assert fetched.name == "Automated Test Karnataka Zone Updated"

        # 4. Delete
        db.delete(fetched)
        db.commit()
        deleted = db.query(MonitoringZone).filter(MonitoringZone.id == zone_id).first()
        assert deleted is None

    finally:
        db.close()
