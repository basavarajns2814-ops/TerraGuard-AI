import os
import numpy as np
from PIL import Image, ImageDraw
from datetime import datetime, timedelta
from app.config import settings
from app.database import SessionLocal
from app.models import (
    User, MonitoringZone, LandParcel, RestrictedBoundary,
    SatelliteScene, DetectionJob, DetectedChange,
    TemporalObservation, Alert, AlertNote, AlertEvidence, Notification
)
from app.core.security import get_password_hash

def generate_sample_satellite_images():
    """Generates synthetic satellite scenes and saves them to storage"""
    img_dir = os.path.join(settings.STORAGE_DIR, "imagery")
    os.makedirs(img_dir, exist_ok=True)

    hist_path = os.path.join(img_dir, "sentinel2_hist_20251015.png")
    recent_path = os.path.join(img_dir, "sentinel2_recent_20261001.png")
    inter_path = os.path.join(img_dir, "sentinel2_inter_20260320.png")

    w, h = 512, 512

    # Historical image: lush vegetation (green) with blue water body
    if not os.path.exists(hist_path):
        hist_img = Image.new("RGB", (w, h), (40, 95, 45))
        draw = ImageDraw.Draw(hist_img)
        # Lake body
        draw.ellipse([50, 80, 220, 280], fill=(28, 65, 115), outline=(20, 50, 90))
        # Agricultural plots
        draw.rectangle([280, 60, 480, 220], fill=(65, 120, 55), outline=(50, 90, 40))
        draw.rectangle([300, 260, 460, 440], fill=(55, 110, 50), outline=(45, 85, 38))
        hist_img.save(hist_path)

    # Intermediate image: vegetation cleared for construction site
    if not os.path.exists(inter_path):
        inter_img = Image.new("RGB", (w, h), (40, 95, 45))
        draw = ImageDraw.Draw(inter_img)
        draw.ellipse([50, 80, 220, 280], fill=(28, 65, 115), outline=(20, 50, 90))
        draw.rectangle([280, 60, 480, 220], fill=(65, 120, 55), outline=(50, 90, 40))
        draw.rectangle([300, 260, 460, 440], fill=(55, 110, 50), outline=(45, 85, 38))
        # Excavation cleared patch encroaching towards lake edge
        draw.rectangle([180, 160, 240, 220], fill=(160, 140, 110), outline=(130, 110, 85))
        inter_img.save(inter_path)

    # Recent image: concrete buildings constructed encroaching on lake buffer
    if not os.path.exists(recent_path):
        recent_img = Image.new("RGB", (w, h), (38, 90, 42))
        draw = ImageDraw.Draw(recent_img)
        draw.ellipse([50, 80, 220, 280], fill=(25, 60, 110), outline=(18, 48, 85))
        draw.rectangle([280, 60, 480, 220], fill=(60, 115, 50), outline=(48, 88, 38))
        draw.rectangle([300, 260, 460, 440], fill=(55, 110, 50), outline=(45, 85, 38))
        # Encroaching building 1 (concrete gray/white)
        draw.rectangle([175, 150, 250, 230], fill=(215, 215, 220), outline=(160, 160, 165))
        # Additional structure
        draw.rectangle([320, 310, 410, 390], fill=(205, 205, 210), outline=(150, 150, 155))
        recent_img.save(recent_path)

    # Generate sample mask
    mask_path = os.path.join(settings.STORAGE_DIR, "masks", "mask_demo.png")
    if not os.path.exists(mask_path):
        mask_img = Image.new("L", (w, h), 0)
        draw = ImageDraw.Draw(mask_img)
        draw.rectangle([175, 150, 250, 230], fill=255)
        draw.rectangle([320, 310, 410, 390], fill=255)
        mask_img.save(mask_path)

    # Generate sample evidence field image
    evid_path = os.path.join(settings.STORAGE_DIR, "evidence", "field_photo_bellandur.jpg")
    if not os.path.exists(evid_path):
        evid_img = Image.new("RGB", (640, 480), (120, 140, 130))
        draw = ImageDraw.Draw(evid_img)
        draw.rectangle([100, 200, 540, 440], fill=(180, 180, 185), outline=(100, 100, 105))
        draw.rectangle([180, 250, 260, 350], fill=(80, 120, 160)) # window
        draw.rectangle([380, 250, 460, 350], fill=(80, 120, 160)) # window
        draw.rectangle([290, 320, 350, 440], fill=(90, 60, 40)) # door
        draw.text((20, 20), "TERRAGUARD EVIDENCE INSPECTION - LAT: 12.9352 LNG: 77.6741", fill=(255, 255, 255))
        evid_img.save(evid_path, "JPEG")

    return {
        "hist": hist_path,
        "inter": inter_path,
        "recent": recent_path,
        "mask": mask_path,
        "evidence": evid_path
    }

def seed_database_if_empty():
    from app.database import engine, Base
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        user_count = db.query(User).count()
        if user_count > 0:
            print("Database already contains data, skipping seed.")
            return

        print("Seeding TerraGuard AI demonstration dataset (Karnataka, India)...")
        sample_files = generate_sample_satellite_images()

        # 1. Create standard demo users for all 3 roles
        admin_user = User(
            email="admin@terraguard.gov.in",
            hashed_password=get_password_hash("Admin@123"),
            full_name="Rajesh Kumar, IAS",
            role="ADMIN",
            department="Karnataka State Land Administration & Revenue Dept",
            badge_number="KAS-9901",
            is_active=True,
            created_at=datetime.utcnow()
        )
        officer_user = User(
            email="officer@terraguard.gov.in",
            hashed_password=get_password_hash("Officer@123"),
            full_name="Ananya Sharma",
            role="MONITORING_OFFICER",
            department="Geospatial Remote Sensing Cell, Bengaluru",
            badge_number="GSC-4421",
            is_active=True,
            created_at=datetime.utcnow()
        )
        inspector_user = User(
            email="inspector@terraguard.gov.in",
            hashed_password=get_password_hash("Inspector@123"),
            full_name="Vikram Gowda",
            role="FIELD_INSPECTOR",
            department="BBMP & KSPCB Lake Enforcement Task Force",
            badge_number="ETF-8812",
            is_active=True,
            created_at=datetime.utcnow()
        )
        db.add_all([admin_user, officer_user, inspector_user])
        db.commit()

        # 2. Create Monitoring Zones in Bengaluru / Karnataka
        zone_bellandur = MonitoringZone(
            name="Bellandur-Varthur Wetland & Catchment Zone",
            district="Bengaluru Urban",
            state="Karnataka",
            description="High-sensitivity peri-urban lake catchment area with protected 30-meter buffer zones and government revenue lands.",
            area_hectares=468.5,
            risk_status="CRITICAL",
            geojson={
                "type": "Polygon",
                "coordinates": [[
                    [77.6550, 12.9250],
                    [77.6950, 12.9250],
                    [77.6950, 12.9550],
                    [77.6550, 12.9550],
                    [77.6550, 12.9250]
                ]]
            },
            created_at=datetime.utcnow()
        )

        zone_forest = MonitoringZone(
            name="Bannerghatta Reserve Forest Fringe Corridor",
            district="Bengaluru Rural",
            state="Karnataka",
            description="Ecologically sensitive buffer boundary prone to illegal clearing and layout boundary creep.",
            area_hectares=624.0,
            risk_status="ELEVATED",
            geojson={
                "type": "Polygon",
                "coordinates": [[
                    [77.5600, 12.7800],
                    [77.6000, 12.7800],
                    [77.6000, 12.8200],
                    [77.5600, 12.8200],
                    [77.5600, 12.7800]
                ]]
            },
            created_at=datetime.utcnow()
        )
        db.add_all([zone_bellandur, zone_forest])
        db.commit()

        # 3. Create Land Parcels
        p1 = LandParcel(
            zone_id=zone_bellandur.id,
            parcel_number="KA-BLR-SY-104/1",
            owner_type="WATER_BODY",
            authorized_use="Designated Lake Bed & Wetland Buffer (NGT Mandated 30m)",
            area_sqm=42000.0,
            area_hectares=4.20,
            geojson={
                "type": "Polygon",
                "coordinates": [[
                    [77.6650, 12.9320],
                    [77.6750, 12.9320],
                    [77.6750, 12.9400],
                    [77.6650, 12.9400],
                    [77.6650, 12.9320]
                ]]
            }
        )
        p2 = LandParcel(
            zone_id=zone_bellandur.id,
            parcel_number="KA-BLR-SY-108/4",
            owner_type="GOVERNMENT",
            authorized_use="State Revenue / Public Civic Amenity",
            area_sqm=28500.0,
            area_hectares=2.85,
            geojson={
                "type": "Polygon",
                "coordinates": [[
                    [77.6760, 12.9320],
                    [77.6850, 12.9320],
                    [77.6850, 12.9420],
                    [77.6760, 12.9420],
                    [77.6760, 12.9320]
                ]]
            }
        )
        p3 = LandParcel(
            zone_id=zone_forest.id,
            parcel_number="KA-BNG-SY-45/2",
            owner_type="FOREST",
            authorized_use="Reserved Forest Boundary Buffer Zone",
            area_sqm=65000.0,
            area_hectares=6.50,
            geojson={
                "type": "Polygon",
                "coordinates": [[
                    [77.5700, 12.7900],
                    [77.5850, 12.7900],
                    [77.5850, 12.8050],
                    [77.5700, 12.8050],
                    [77.5700, 12.7900]
                ]]
            }
        )
        db.add_all([p1, p2, p3])
        db.commit()

        # 4. Create Restricted Boundaries
        rb1 = RestrictedBoundary(
            name="Bellandur Lake 30m NGT Statutory Buffer",
            zone_id=zone_bellandur.id,
            boundary_type="LAKE_BUFFER",
            buffer_distance_meters=30.0,
            description="Strict non-construction zone mandated under National Green Tribunal & Karnataka High Court orders.",
            geojson={
                "type": "Polygon",
                "coordinates": [[
                    [77.6640, 12.9310],
                    [77.6760, 12.9310],
                    [77.6760, 12.9410],
                    [77.6640, 12.9410],
                    [77.6640, 12.9310]
                ]]
            }
        )
        rb2 = RestrictedBoundary(
            name="Bannerghatta Eco-Sensitive Sanctuary Perimeter",
            zone_id=zone_forest.id,
            boundary_type="FOREST_RESERVE",
            buffer_distance_meters=100.0,
            description="Protected eco-zone around national park perimeter prohibiting commercial activity.",
            geojson={
                "type": "Polygon",
                "coordinates": [[
                    [77.5680, 12.7880],
                    [77.5870, 12.7880],
                    [77.5870, 12.8080],
                    [77.5680, 12.8080],
                    [77.5680, 12.7880]
                ]]
            }
        )
        db.add_all([rb1, rb2])
        db.commit()

        # 5. Satellite Scenes
        s_hist = SatelliteScene(
            title="Sentinel-2 L2A Post-Monsoon Baseline (Zone 1)",
            provider="SENTINEL_2",
            acquisition_date="2025-10-15",
            cloud_coverage_percentage=1.2,
            resolution_meters=10.0,
            image_path=sample_files["hist"],
            image_url="/storage/imagery/sentinel2_hist_20251015.png",
            thumbnail_url="/storage/imagery/sentinel2_hist_20251015.png",
            zone_id=zone_bellandur.id,
            created_at=datetime.utcnow() - timedelta(days=360)
        )
        s_inter = SatelliteScene(
            title="Sentinel-2 L2A Mid-Season Observation (Zone 1)",
            provider="SENTINEL_2",
            acquisition_date="2026-03-20",
            cloud_coverage_percentage=2.8,
            resolution_meters=10.0,
            image_path=sample_files["inter"],
            image_url="/storage/imagery/sentinel2_inter_20260320.png",
            thumbnail_url="/storage/imagery/sentinel2_inter_20260320.png",
            zone_id=zone_bellandur.id,
            created_at=datetime.utcnow() - timedelta(days=210)
        )
        s_recent = SatelliteScene(
            title="Sentinel-2 L2A Latest Acquisition Pass (Zone 1)",
            provider="SENTINEL_2",
            acquisition_date="2026-10-01",
            cloud_coverage_percentage=3.5,
            resolution_meters=10.0,
            image_path=sample_files["recent"],
            image_url="/storage/imagery/sentinel2_recent_20261001.png",
            thumbnail_url="/storage/imagery/sentinel2_recent_20261001.png",
            zone_id=zone_bellandur.id,
            created_at=datetime.utcnow() - timedelta(days=22)
        )
        db.add_all([s_hist, s_inter, s_recent])
        db.commit()

        # 6. Detection Job
        job = DetectionJob(
            job_code="JOB-BLR-202610-01",
            zone_id=zone_bellandur.id,
            historical_scene_id=s_hist.id,
            recent_scene_id=s_recent.id,
            algorithm="SPECTRAL_NDVI_NDBI_DIFFERENCING",
            status="COMPLETED",
            progress=100,
            parameters={"threshold": 0.18, "min_area_pixels": 25},
            created_at=datetime.utcnow() - timedelta(days=2),
            completed_at=datetime.utcnow() - timedelta(days=2)
        )
        db.add(job)
        db.commit()

        # 7. Detected Changes
        ch1 = DetectedChange(
            job_id=job.id,
            zone_id=zone_bellandur.id,
            parcel_id=p1.id,
            category="WATER_BODY_ENCROACHMENT",
            confidence_score=0.92,
            risk_score=94.0,
            risk_level="CRITICAL",
            affected_area_sqm=1850.0,
            affected_area_hectares=0.185,
            centroid_lat=12.9352,
            centroid_lng=77.6741,
            geojson={
                "type": "Polygon",
                "coordinates": [[
                    [77.6720, 12.9340],
                    [77.6760, 12.9340],
                    [77.6760, 12.9370],
                    [77.6720, 12.9370],
                    [77.6720, 12.9340]
                ]]
            },
            intersects_restricted=True,
            restricted_zone_name=rb1.name,
            risk_reasons=[
                "Critical category: Detected alteration inside designated water body buffer",
                "Direct spatial intersection with legally protected restricted boundary (Bellandur Lake 30m NGT Statutory Buffer)",
                "High temporal persistence: Confirmed across 3 distinct satellite acquisition dates",
                "Active growth trend: Spatial footprint progressively enlarging (+48% since March 2026)"
            ],
            first_observed_date="2025-10-15",
            latest_observed_date="2026-10-01",
            observation_count=3,
            trend="EXPANDING",
            created_at=datetime.utcnow() - timedelta(days=20)
        )

        ch2 = DetectedChange(
            job_id=job.id,
            zone_id=zone_bellandur.id,
            parcel_id=p2.id,
            category="NEW_CONSTRUCTION",
            confidence_score=0.88,
            risk_score=78.0,
            risk_level="HIGH",
            affected_area_sqm=1220.0,
            affected_area_hectares=0.122,
            centroid_lat=12.9385,
            centroid_lng=77.6810,
            geojson={
                "type": "Polygon",
                "coordinates": [[
                    [77.6795, 12.9370],
                    [77.6825, 12.9370],
                    [77.6825, 12.9400],
                    [77.6795, 12.9400],
                    [77.6795, 12.9370]
                ]]
            },
            intersects_restricted=False,
            restricted_zone_name=None,
            risk_reasons=[
                "Detected new structural building footprint candidate",
                "Land tenure check: Parcel registered as Government Revenue Land",
                "Extensive affected area (1220.0 m² / 0.12 ha)"
            ],
            first_observed_date="2026-03-20",
            latest_observed_date="2026-10-01",
            observation_count=2,
            trend="STABLE",
            created_at=datetime.utcnow() - timedelta(days=15)
        )

        ch3 = DetectedChange(
            job_id=job.id,
            zone_id=zone_forest.id,
            parcel_id=p3.id,
            category="VEGETATION_LOSS",
            confidence_score=0.85,
            risk_score=72.0,
            risk_level="HIGH",
            affected_area_sqm=940.0,
            affected_area_hectares=0.094,
            centroid_lat=12.7950,
            centroid_lng=77.5780,
            geojson={
                "type": "Polygon",
                "coordinates": [[
                    [77.5760, 12.7930],
                    [77.5800, 12.7930],
                    [77.5800, 12.7970],
                    [77.5760, 12.7970],
                    [77.5760, 12.7930]
                ]]
            },
            intersects_restricted=True,
            restricted_zone_name=rb2.name,
            risk_reasons=[
                "Significant green canopy reduction / land clearing detected in reserve boundary",
                "Land tenure check: Parcel registered as Forest",
                "Direct spatial intersection with Bannerghatta Eco-Sensitive Sanctuary Perimeter"
            ],
            first_observed_date="2026-03-20",
            latest_observed_date="2026-10-01",
            observation_count=2,
            trend="EXPANDING",
            created_at=datetime.utcnow() - timedelta(days=10)
        )
        db.add_all([ch1, ch2, ch3])
        db.commit()

        # 8. Temporal Observations for ch1
        t1 = TemporalObservation(
            change_id=ch1.id,
            observation_date="2025-10-15",
            area_sqm=650.0,
            risk_score=68.0,
            confidence_score=0.86,
            image_url=s_hist.image_url,
            scene_id=s_hist.id,
            created_at=datetime.utcnow() - timedelta(days=360)
        )
        t2 = TemporalObservation(
            change_id=ch1.id,
            observation_date="2026-03-20",
            area_sqm=1250.0,
            risk_score=82.0,
            confidence_score=0.89,
            image_url=s_inter.image_url,
            scene_id=s_inter.id,
            created_at=datetime.utcnow() - timedelta(days=210)
        )
        t3 = TemporalObservation(
            change_id=ch1.id,
            observation_date="2026-10-01",
            area_sqm=1850.0,
            risk_score=94.0,
            confidence_score=0.92,
            image_url=s_recent.image_url,
            scene_id=s_recent.id,
            created_at=datetime.utcnow() - timedelta(days=20)
        )
        db.add_all([t1, t2, t3])
        db.commit()

        # 9. Alerts
        a1 = Alert(
            alert_code="TG-2026-0001",
            change_id=ch1.id,
            zone_id=zone_bellandur.id,
            parcel_id=p1.id,
            category=ch1.category,
            risk_level=ch1.risk_level,
            risk_score=ch1.risk_score,
            confidence_score=ch1.confidence_score,
            affected_area_sqm=ch1.affected_area_sqm,
            affected_area_hectares=ch1.affected_area_hectares,
            centroid_lat=ch1.centroid_lat,
            centroid_lng=ch1.centroid_lng,
            geojson=ch1.geojson,
            historical_image_url=s_hist.image_url,
            recent_image_url=s_recent.image_url,
            change_mask_url="/storage/masks/mask_demo.png",
            status="FIELD_INSPECTION_REQUIRED",
            first_observed_date=ch1.first_observed_date,
            latest_observed_date=ch1.latest_observed_date,
            assigned_to_id=inspector_user.id,
            risk_reasons=ch1.risk_reasons,
            created_at=datetime.utcnow() - timedelta(days=18),
            updated_at=datetime.utcnow() - timedelta(days=2)
        )

        a2 = Alert(
            alert_code="TG-2026-0002",
            change_id=ch2.id,
            zone_id=zone_bellandur.id,
            parcel_id=p2.id,
            category=ch2.category,
            risk_level=ch2.risk_level,
            risk_score=ch2.risk_score,
            confidence_score=ch2.confidence_score,
            affected_area_sqm=ch2.affected_area_sqm,
            affected_area_hectares=ch2.affected_area_hectares,
            centroid_lat=ch2.centroid_lat,
            centroid_lng=ch2.centroid_lng,
            geojson=ch2.geojson,
            historical_image_url=s_hist.image_url,
            recent_image_url=s_recent.image_url,
            change_mask_url="/storage/masks/mask_demo.png",
            status="UNDER_REVIEW",
            first_observed_date=ch2.first_observed_date,
            latest_observed_date=ch2.latest_observed_date,
            assigned_to_id=officer_user.id,
            risk_reasons=ch2.risk_reasons,
            created_at=datetime.utcnow() - timedelta(days=14),
            updated_at=datetime.utcnow() - timedelta(days=5)
        )

        a3 = Alert(
            alert_code="TG-2026-0003",
            change_id=ch3.id,
            zone_id=zone_forest.id,
            parcel_id=p3.id,
            category=ch3.category,
            risk_level=ch3.risk_level,
            risk_score=ch3.risk_score,
            confidence_score=ch3.confidence_score,
            affected_area_sqm=ch3.affected_area_sqm,
            affected_area_hectares=ch3.affected_area_hectares,
            centroid_lat=ch3.centroid_lat,
            centroid_lng=ch3.centroid_lng,
            geojson=ch3.geojson,
            historical_image_url=s_hist.image_url,
            recent_image_url=s_recent.image_url,
            change_mask_url="/storage/masks/mask_demo.png",
            status="NEW",
            first_observed_date=ch3.first_observed_date,
            latest_observed_date=ch3.latest_observed_date,
            assigned_to_id=None,
            risk_reasons=ch3.risk_reasons,
            created_at=datetime.utcnow() - timedelta(days=8),
            updated_at=datetime.utcnow() - timedelta(days=8)
        )
        db.add_all([a1, a2, a3])
        db.commit()

        # 10. Notes & Evidence for Alert 1
        note1 = AlertNote(
            alert_id=a1.id,
            user_id=officer_user.id,
            user_name=officer_user.full_name,
            user_role=officer_user.role,
            note="Reviewed Sentinel-2 temporal differencing. Significant 1850 m² expansion directly intersects 30m NGT lake buffer. Marked for urgent physical survey.",
            created_at=datetime.utcnow() - timedelta(days=12)
        )
        note2 = AlertNote(
            alert_id=a1.id,
            user_id=inspector_user.id,
            user_name=inspector_user.full_name,
            user_role=inspector_user.role,
            note="Physical inspection conducted on site. Unauthorised prefabricated warehouse structure with earthwork boundary encroachment confirmed. Geo-tagged evidence photo attached.",
            created_at=datetime.utcnow() - timedelta(days=2)
        )
        db.add_all([note1, note2])

        evid1 = AlertEvidence(
            alert_id=a1.id,
            user_id=inspector_user.id,
            file_path=sample_files["evidence"],
            file_url="/storage/evidence/field_photo_bellandur.jpg",
            file_type="image/jpeg",
            caption="On-site inspection evidence: Illegal structure erection inside 30m lake catchment boundary",
            uploaded_by_name=inspector_user.full_name,
            latitude=12.9352,
            longitude=77.6741,
            created_at=datetime.utcnow() - timedelta(days=2)
        )
        db.add(evid1)

        # 11. Initial Notifications
        n1 = Notification(
            user_id=officer_user.id,
            title="CRITICAL Alert TG-2026-0001 Generated",
            message="Active expansion of 1850 m² detected inside Bellandur Lake Buffer zone.",
            type="ALERT_HIGH",
            alert_id=a1.id,
            is_read=False,
            created_at=datetime.utcnow() - timedelta(days=18)
        )
        n2 = Notification(
            user_id=inspector_user.id,
            title="Field Inspection Assigned: TG-2026-0001",
            message="You have been assigned to verify unauthorized structure in Bellandur-Varthur Wetland Zone.",
            type="INSPECTION",
            alert_id=a1.id,
            is_read=False,
            created_at=datetime.utcnow() - timedelta(days=10)
        )
        db.add_all([n1, n2])
        db.commit()

        print("Demonstration data seeded successfully!")

    except Exception as e:
        db.rollback()
        print(f"Error seeding database: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    seed_database_if_empty()
