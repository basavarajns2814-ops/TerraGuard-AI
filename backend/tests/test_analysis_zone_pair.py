from datetime import datetime
from types import SimpleNamespace

import pytest
from fastapi import BackgroundTasks, HTTPException

from app.database import SessionLocal
from app.models import DetectionJob, DetectedChange, SatelliteScene
from app.routers.analysis import list_changes, run_analysis
from app.schemas import DetectionJobCreate


def make_scene(db, *, zone_id, acquisition_date):
    scene = SatelliteScene(
        title=f"Test scene {acquisition_date}",
        provider="SENTINEL_2",
        acquisition_date=acquisition_date,
        cloud_coverage_percentage=5.0,
        resolution_meters=10.0,
        image_path="/tmp/unused.png",
        image_url=f"/storage/test-{acquisition_date}.png",
        zone_id=zone_id,
        metadata_json={"raster_url": f"/storage/test-{acquisition_date}.tif"},
        created_at=datetime.utcnow(),
    )
    db.add(scene)
    db.commit()
    db.refresh(scene)
    return scene


def test_analysis_rejects_cross_zone_or_nonchronological_scene_pairs():
    db = SessionLocal()
    hist = make_scene(db, zone_id=1, acquisition_date="2025-01-10")
    recent_other_zone = make_scene(db, zone_id=2, acquisition_date="2025-02-10")
    recent_earlier = make_scene(db, zone_id=1, acquisition_date="2024-12-10")
    user = SimpleNamespace(email="reviewer@example.test")
    try:
        with pytest.raises(HTTPException) as cross_zone:
            run_analysis(
                DetectionJobCreate(
                    zone_id=1,
                    historical_scene_id=hist.id,
                    recent_scene_id=recent_other_zone.id,
                ),
                BackgroundTasks(),
                db,
                user,
            )
        assert cross_zone.value.status_code == 422
        assert "belong to the selected" in cross_zone.value.detail

        with pytest.raises(HTTPException) as date_order:
            run_analysis(
                DetectionJobCreate(
                    zone_id=1,
                    historical_scene_id=hist.id,
                    recent_scene_id=recent_earlier.id,
                ),
                BackgroundTasks(),
                db,
                user,
            )
        assert date_order.value.status_code == 422
        assert "earlier" in date_order.value.detail
    finally:
        db.query(DetectionJob).filter(DetectionJob.historical_scene_id.in_([hist.id])).delete(synchronize_session=False)
        for scene in (hist, recent_other_zone, recent_earlier):
            db.delete(scene)
        db.commit()
        db.close()


def test_analysis_accepts_ordered_scenes_from_same_saved_zone():
    db = SessionLocal()
    hist = make_scene(db, zone_id=1, acquisition_date="2025-01-10")
    recent = make_scene(db, zone_id=1, acquisition_date="2025-02-10")
    user = SimpleNamespace(email="reviewer@example.test")
    try:
        job = run_analysis(
            DetectionJobCreate(
                zone_id=1,
                historical_scene_id=hist.id,
                recent_scene_id=recent.id,
                algorithm="SNUNET_CD",
            ),
            BackgroundTasks(),
            db,
            user,
        )
        assert job.status == "PENDING"
        assert job.zone_id == 1
        assert job.historical_scene_id == hist.id
        assert job.recent_scene_id == recent.id
        stored_job = db.query(DetectionJob).filter(DetectionJob.id == job.id).first()
        change = DetectedChange(
            job_id=job.id,
            zone_id=1,
            category="VEGETATION_LOSS",
            confidence_score=0.71,
            risk_score=20,
            risk_level="LOW",
            affected_area_sqm=100,
            affected_area_hectares=0.01,
            centroid_lat=12.9,
            centroid_lng=77.6,
            geojson={"type": "Polygon", "coordinates": []},
            intersects_restricted=False,
            first_observed_date="2025-01-10",
            latest_observed_date="2025-02-10",
            observation_count=1,
            trend="NEW",
        )
        db.add(change)
        db.flush()
        stored_job.parameters = {
            "candidate_model_scores": [{
                "change_id": change.id,
                "mean_probability": 0.63,
                "max_probability": 0.91,
            }]
        }
        db.commit()
        api_changes = list_changes(None, None, None, None, db, user)
        persisted_change = next(item for item in api_changes if item.id == change.id)
        assert persisted_change.model_mean_probability == 0.63
        assert persisted_change.model_max_probability == 0.91
    finally:
        db.query(DetectedChange).filter(DetectedChange.job_id == job.id).delete(synchronize_session=False)
        db.query(DetectionJob).filter(DetectionJob.historical_scene_id == hist.id).delete(synchronize_session=False)
        db.delete(hist)
        db.delete(recent)
        db.commit()
        db.close()
