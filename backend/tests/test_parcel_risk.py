from types import SimpleNamespace

import pytest

import app.services.levir_service as levir_module
from app.services.levir_service import (
    LevirModelService,
    resolve_detected_parcel_association,
)
from app.models import Alert, DetectedChange, LandParcel, MonitoringZone, RestrictedBoundary
from app.services.risk_scoring import evaluate_risk_and_confidence
from app.services.spatial import find_containing_parcel


BASE_ARGS = {
    "category": "VEGETATION_LOSS",
    "affected_area_sqm": 600.0,
    "intersects_restricted": False,
    "restricted_zone_name": None,
    "proximity_meters": 9999.0,
    "observation_count": 1,
    "trend": "NEW",
    "cloud_coverage_percentage": 0.0,
}


def risk_score(owner_type):
    score, level, confidence, reasons = evaluate_risk_and_confidence(
        **BASE_ARGS,
        parcel_owner_type=owner_type,
    )
    return score, level, confidence, reasons


def test_government_parcel_receives_existing_ownership_risk():
    government_score, _, _, government_reasons = risk_score("GOVERNMENT")
    unknown_score, _, _, unknown_reasons = risk_score("UNKNOWN")

    assert government_score - unknown_score == 10.0
    assert any("government" in reason.lower() for reason in government_reasons)
    assert not any("tenure" in reason.lower() for reason in unknown_reasons)


@pytest.mark.parametrize("owner_type", ["PUBLIC_RESERVE", "FOREST"])
def test_government_related_owner_types_retain_existing_contribution(owner_type):
    owner_score, _, _, owner_reasons = risk_score(owner_type)
    unknown_score, _, _, unknown_reasons = risk_score("UNKNOWN")

    assert owner_score - unknown_score == 10.0
    assert any("tenure" in reason.lower() for reason in owner_reasons)
    assert not any("tenure" in reason.lower() for reason in unknown_reasons)


def test_private_parcel_receives_no_ownership_risk():
    private_score, _, _, private_reasons = risk_score("PRIVATE")
    unknown_score, _, _, unknown_reasons = risk_score("UNKNOWN")

    assert private_score == unknown_score
    assert private_reasons == unknown_reasons


@pytest.mark.parametrize(
    "owner_type",
    ["", None, "NONE", "UNKNOWN", "COMMUNITY", "WATER_BODY"],
)
def test_unknown_and_unsupported_owner_types_receive_no_tenure_risk(owner_type):
    score, _, _, reasons = risk_score(owner_type)
    unknown_score, _, _, unknown_reasons = risk_score("UNKNOWN")

    assert score == unknown_score
    assert reasons == unknown_reasons
    assert not any("tenure" in reason.lower() for reason in reasons)


def test_unmatched_parcel_is_unknown_and_receives_no_tenure_risk():
    candidate = {
        "type": "Polygon",
        "coordinates": [[[77.670, 12.930], [77.671, 12.930],
                         [77.671, 12.931], [77.670, 12.931],
                         [77.670, 12.930]]],
    }
    unmatched_parcel = SimpleNamespace(
        id=10,
        parcel_number="NONE-001",
        owner_type="UNKNOWN",
        geojson={
            "type": "Polygon",
            "coordinates": [[[77.700, 12.960], [77.701, 12.960],
                             [77.701, 12.961], [77.700, 12.961],
                             [77.700, 12.960]]],
        },
    )

    assert find_containing_parcel(candidate, [unmatched_parcel]) is None
    score, _, _, reasons = risk_score("UNKNOWN")
    assert score == risk_score(None)[0]
    assert not any("tenure" in reason.lower() for reason in reasons)


def test_invalid_parcel_geometry_does_not_create_match():
    candidate = {
        "type": "Polygon",
        "coordinates": [[[77.670, 12.930], [77.671, 12.930],
                         [77.671, 12.931], [77.670, 12.931],
                         [77.670, 12.930]]],
    }
    invalid_parcel = SimpleNamespace(
        id=20,
        parcel_number="INVALID-001",
        owner_type="GOVERNMENT",
        geojson={
            "type": "Polygon",
            "coordinates": [[[77.670, 12.930], [77.671, 12.931],
                             [77.670, 12.931], [77.671, 12.930],
                             [77.670, 12.930]]],
        },
    )

    assert find_containing_parcel(candidate, [invalid_parcel]) is None
    unknown_score, _, _, _ = risk_score("UNKNOWN")
    assert unknown_score == risk_score(None)[0]


@pytest.mark.parametrize(
    "parcel_geometry",
    [
        None,
        {"type": "Polygon", "coordinates": []},
        {
            "type": "Polygon",
            "coordinates": [[[77.670, float("nan")], [77.671, 12.930],
                             [77.671, 12.931], [77.670, 12.931],
                             [77.670, float("nan")]]],
        },
        {
            "type": "Polygon",
            "coordinates": [[[77.670, 12.930], [77.671, 12.931],
                             [77.670, 12.931], [77.671, 12.930],
                             [77.670, 12.930]]],
        },
        {
            "type": "GeometryCollection",
            "geometries": [
                {"type": "Point", "coordinates": [77.6705, 12.9305]}
            ],
        },
    ],
)
def test_unusable_parcel_geometries_cannot_create_match(parcel_geometry):
    candidate = {
        "type": "Polygon",
        "coordinates": [[[77.670, 12.930], [77.671, 12.930],
                         [77.671, 12.931], [77.670, 12.931],
                         [77.670, 12.930]]],
    }
    parcel = SimpleNamespace(
        id=30,
        parcel_number="UNUSABLE-001",
        owner_type="GOVERNMENT",
        geojson=parcel_geometry,
    )

    assert find_containing_parcel(candidate, [parcel]) is None


def test_levir_unmatched_candidate_ignores_supplied_parcel_id():
    supplied_parcel_id = 77

    matched_parcel_id = resolve_detected_parcel_association(
        matched_parcel=None,
        supplied_parcel_id=supplied_parcel_id,
    )
    owner_type = "UNKNOWN"

    assert matched_parcel_id is None
    assert owner_type == "UNKNOWN"
    assert risk_score(owner_type)[0] == risk_score(None)[0]


def test_levir_spatial_match_preserves_verified_parcel_id():
    matched_parcel = SimpleNamespace(id=31, owner_type="GOVERNMENT")

    assert resolve_detected_parcel_association(
        matched_parcel=matched_parcel,
        supplied_parcel_id=77,
    ) == 31


class ParcelRiskFakeQuery:
    def __init__(self, db, model):
        self.db = db
        self.model = model

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        if self.model is MonitoringZone:
            return self.db.zone
        if self.model is Alert:
            self.db.alert_queries.append("alert")
            return None
        return None

    def all(self):
        if self.model is LandParcel:
            return self.db.parcels
        if self.model is RestrictedBoundary:
            return []
        return []

    def count(self):
        return 0


class ParcelRiskFakeDB:
    def __init__(self, zone, parcels=None):
        self.zone = zone
        self.parcels = parcels or []
        self.added = []
        self.alert_queries = []
        self.commits = 0

    def query(self, model):
        return ParcelRiskFakeQuery(self, model)

    def add(self, value):
        self.added.append(value)

    def flush(self):
        for value in self.added:
            if getattr(value, "id", None) is None and isinstance(value, DetectedChange):
                value.id = 101

    def commit(self):
        self.commits += 1

    def refresh(self, value):
        return None


def run_levir_caller_test(monkeypatch, matched_parcel):
    zone = SimpleNamespace(
        id=1,
        geojson={
            "type": "Polygon",
            "coordinates": [[[77.660, 12.920], [77.685, 12.920],
                             [77.685, 12.945], [77.660, 12.945],
                             [77.660, 12.920]]],
        },
    )
    db = ParcelRiskFakeDB(zone)
    prediction_result = {
        "mask_uint8": object(),
        "dimensions": {"width": 100, "height": 100},
        "changed_pixel_percentage": 12.5,
        "threshold": 0.7,
        "max_probability": 0.91,
        "mask_url": "/synthetic/change-mask.png",
    }
    recent_scene = SimpleNamespace(
        acquisition_date="2026-10-01",
        image_url="/synthetic/recent.png",
        cloud_coverage_percentage=2.0,
    )
    historical_scene = SimpleNamespace(
        acquisition_date="2025-10-15",
        image_url="/synthetic/historical.png",
    )
    captured_risk = {}

    monkeypatch.setattr(levir_module, "morphological_clean", lambda mask: mask)
    monkeypatch.setattr(
        levir_module,
        "extract_connected_components",
        lambda mask, min_pixels=20: [object()],
    )
    monkeypatch.setattr(
        levir_module,
        "component_to_geojson_polygon",
        lambda component, width, height, bbox: {
            "type": "Polygon",
            "coordinates": [[[77.670, 12.930], [77.671, 12.930],
                             [77.671, 12.931], [77.670, 12.931],
                             [77.670, 12.930]]],
        },
    )
    monkeypatch.setattr(levir_module, "calculate_polygon_area_sqm", lambda geojson: 600.0)
    monkeypatch.setattr(levir_module, "sqm_to_hectares", lambda sqm: 0.06)
    monkeypatch.setattr(
        levir_module,
        "get_centroid_lat_lng",
        lambda geojson: (12.9305, 77.6705),
    )
    monkeypatch.setattr(levir_module, "find_containing_parcel", lambda geojson, parcels: matched_parcel)
    monkeypatch.setattr(
        levir_module,
        "evaluate_risk_and_confidence",
        lambda **kwargs: (
            captured_risk.update(kwargs) or
            (75.0, "HIGH", 0.88, ["Synthetic risk reason"])
        ),
    )
    monkeypatch.setattr(
        levir_module,
        "generate_or_update_alert",
        lambda db, change, zone, **kwargs: SimpleNamespace(id=501, parcel_id=change.parcel_id),
    )

    alert = LevirModelService().generate_potential_change_alert(
        db=db,
        prediction_result=prediction_result,
        zone_id=zone.id,
        historical_scene=historical_scene,
        recent_scene=recent_scene,
        parcel_id=77,
    )

    detections = [
        value for value in db.added
        if isinstance(value, DetectedChange)
    ]
    assert len(detections) == 1
    return db, detections[0], captured_risk, alert


def test_levir_caller_unmatched_candidate_has_no_parcel_association(monkeypatch):
    db, detection, captured_risk, _ = run_levir_caller_test(monkeypatch, None)

    assert detection.parcel_id is None
    assert captured_risk["parcel_owner_type"] == "UNKNOWN"
    assert db.alert_queries == []


def test_levir_caller_verified_spatial_match_preserves_parcel_association(monkeypatch):
    matched_parcel = SimpleNamespace(id=31, owner_type="GOVERNMENT")

    db, detection, captured_risk, _ = run_levir_caller_test(
        monkeypatch,
        matched_parcel,
    )

    assert detection.parcel_id == 31
    assert captured_risk["parcel_owner_type"] == "GOVERNMENT"
    assert db.alert_queries == ["alert"]


def test_other_risk_components_remain_unchanged_for_unknown_owner():
    common_args = {
        **BASE_ARGS,
        "category": "NEW_CONSTRUCTION",
        "affected_area_sqm": 1600.0,
        "intersects_restricted": True,
        "restricted_zone_name": "Lake Buffer Zone",
        "proximity_meters": 0.0,
        "observation_count": 3,
        "trend": "EXPANDING",
        "cloud_coverage_percentage": 2.0,
    }

    unknown_score, unknown_level, unknown_confidence, unknown_reasons = (
        evaluate_risk_and_confidence(**common_args, parcel_owner_type=None)
    )
    private_score, private_level, private_confidence, private_reasons = (
        evaluate_risk_and_confidence(**common_args, parcel_owner_type="PRIVATE")
    )

    assert unknown_score == private_score
    assert unknown_level == private_level
    assert unknown_confidence == private_confidence
    assert unknown_reasons == private_reasons
    assert any("direct spatial intersection" in reason.lower() for reason in unknown_reasons)
    assert any("extensive affected area" in reason.lower() for reason in unknown_reasons)
    assert any("temporal persistence" in reason.lower() for reason in unknown_reasons)
