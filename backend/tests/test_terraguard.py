import os
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database import get_db, SessionLocal
from app.models import User, MonitoringZone, Alert, DetectedChange
from app.core.security import verify_password, get_password_hash, create_access_token
from app.services.spatial import (
    calculate_polygon_area_sqm,
    sqm_to_hectares,
    get_centroid_lat_lng,
    check_intersection_and_buffer
)
from app.services.risk_scoring import evaluate_risk_and_confidence
from app.services.change_detection.service import change_detection_service

client = TestClient(app)

def test_health_check():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

def test_auth_login_admin():
    response = client.post("/api/auth/login", json={
        "email": "admin@terraguard.gov.in",
        "password": "Admin@123"
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["user"]["role"] == "ADMIN"
    assert data["user"]["email"] == "admin@terraguard.gov.in"

def test_auth_invalid_credentials():
    response = client.post("/api/auth/login", json={
        "email": "admin@terraguard.gov.in",
        "password": "WrongPassword"
    })
    assert response.status_code == 401

def test_spatial_area_and_centroid():
    # 0.001 deg box ~ 111m x 111m ~ 12,321 m2
    box_geom = {
        "type": "Polygon",
        "coordinates": [[
            [77.670, 12.930],
            [77.671, 12.930],
            [77.671, 12.931],
            [77.670, 12.931],
            [77.670, 12.930]
        ]]
    }
    area_sqm = calculate_polygon_area_sqm(box_geom)
    assert area_sqm > 5000.0
    ha = sqm_to_hectares(area_sqm)
    assert ha > 0.5
    lat, lng = get_centroid_lat_lng(box_geom)
    assert abs(lat - 12.9305) < 0.001
    assert abs(lng - 77.6705) < 0.001

def test_spatial_intersection_and_buffer():
    poly1 = {
        "type": "Polygon",
        "coordinates": [[
            [77.670, 12.930],
            [77.672, 12.930],
            [77.672, 12.932],
            [77.670, 12.932],
            [77.670, 12.930]
        ]]
    }
    # Intersecting poly
    poly_intersect = {
        "type": "Polygon",
        "coordinates": [[
            [77.671, 12.931],
            [77.673, 12.931],
            [77.673, 12.933],
            [77.671, 12.933],
            [77.671, 12.931]
        ]]
    }
    # Disjoint poly far away
    poly_far = {
        "type": "Polygon",
        "coordinates": [[
            [77.700, 12.960],
            [77.702, 12.960],
            [77.702, 12.962],
            [77.700, 12.962],
            [77.700, 12.960]
        ]]
    }
    res_int = check_intersection_and_buffer(poly1, poly_intersect, buffer_meters=30.0)
    assert res_int["intersects"] is True
    assert res_int["violation_type"] == "DIRECT_INTERSECTION"

    res_far = check_intersection_and_buffer(poly1, poly_far, buffer_meters=30.0)
    assert res_far["intersects"] is False
    assert res_far["in_buffer"] is False
    assert res_far["violation_type"] == "CLEAR"

def test_risk_scoring_engine():
    # Critical risk case: water body buffer intersection + large area + expanding
    score, level, conf, reasons = evaluate_risk_and_confidence(
        category="WATER_BODY_ENCROACHMENT",
        affected_area_sqm=2000.0,
        intersects_restricted=True,
        restricted_zone_name="Lake Buffer Zone",
        proximity_meters=0.0,
        observation_count=3,
        trend="EXPANDING",
        cloud_coverage_percentage=2.0
    )
    assert score >= 80.0
    assert level == "CRITICAL"
    assert conf >= 0.85
    assert len(reasons) >= 3
    assert any("water body" in r.lower() for r in reasons)
    assert any("restricted boundary" in r.lower() for r in reasons)

def test_dashboard_api():
    # Login to get token
    login_res = client.post("/api/auth/login", json={
        "email": "officer@terraguard.gov.in",
        "password": "Officer@123"
    })
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    res = client.get("/api/dashboard/stats", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["monitored_parcels"] > 0
    assert data["total_area_hectares"] > 0
    assert data["is_demo_mode"] is True

    trends_res = client.get("/api/dashboard/trends", headers=headers)
    assert trends_res.status_code == 200
    trends = trends_res.json()
    assert "categories" in trends
    assert "risks" in trends
    assert "timeline" in trends

def test_alerts_workflow():
    login_res = client.post("/api/auth/login", json={
        "email": "officer@terraguard.gov.in",
        "password": "Officer@123"
    })
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # List alerts
    alerts_res = client.get("/api/alerts", headers=headers)
    assert alerts_res.status_code == 200
    alerts = alerts_res.json()
    assert len(alerts) > 0
    alert_id = alerts[0]["id"]

    # Get single alert detail
    detail_res = client.get(f"/api/alerts/{alert_id}", headers=headers)
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert detail["alert_code"].startswith("TG-2026-")
    assert "notes" in detail
    assert "evidence" in detail

    # Add note
    note_res = client.post(f"/api/alerts/{alert_id}/notes", json={
        "note": "Automated verification test note."
    }, headers=headers)
    assert note_res.status_code == 200
    assert note_res.json()["note"] == "Automated verification test note."

    # Update status
    status_res = client.post(f"/api/alerts/{alert_id}/status", json={
        "status": "UNDER_REVIEW",
        "resolution_details": "Reviewing satellite temporal profile"
    }, headers=headers)
    assert status_res.status_code == 200
    assert status_res.json()["status"] == "UNDER_REVIEW"

def test_reports_export():
    login_res = client.post("/api/auth/login", json={
        "email": "admin@terraguard.gov.in",
        "password": "Admin@123"
    })
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    csv_res = client.get("/api/reports/export-csv", headers=headers)
    assert csv_res.status_code == 200
    assert "Alert Code" in csv_res.text

    pdf_res = client.get("/api/reports/export-pdf", headers=headers)
    assert pdf_res.status_code == 200
    assert pdf_res.headers["content-type"] == "application/pdf"
    assert len(pdf_res.content) > 500
