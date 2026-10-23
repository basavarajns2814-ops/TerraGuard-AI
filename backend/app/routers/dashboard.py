from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta
from app.database import get_db
from app.models import MonitoringZone, LandParcel, DetectedChange, Alert, SatelliteScene, DetectionJob
from app.schemas import DashboardStats
from app.core.deps import get_current_user
from app.config import settings

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])

@router.get("/stats", response_model=DashboardStats)
def get_dashboard_stats(db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    parcels_count = db.query(LandParcel).count()
    total_area_ha = db.query(func.sum(MonitoringZone.area_hectares)).scalar() or 0.0

    new_changes = db.query(DetectedChange).count()
    pending_alerts = db.query(Alert).filter(Alert.status.in_(["NEW", "UNDER_REVIEW"])).count()
    high_risk_alerts = db.query(Alert).filter(Alert.risk_level.in_(["HIGH", "CRITICAL"])).count()
    awaiting_inspection = db.query(Alert).filter(Alert.status == "FIELD_INSPECTION_REQUIRED").count()
    confirmed_encroachments = db.query(Alert).filter(Alert.status == "CONFIRMED").count()

    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    changes_last_30_days = db.query(DetectedChange).filter(DetectedChange.created_at >= thirty_days_ago).count()

    # Latest imagery
    latest_scene = db.query(SatelliteScene).order_by(SatelliteScene.acquisition_date.desc()).first()
    latest_imagery_date = latest_scene.acquisition_date if latest_scene else "2026-10-01"

    # Latest analysis
    last_job = db.query(DetectionJob).filter(DetectionJob.status == "COMPLETED").order_by(DetectionJob.completed_at.desc()).first()
    last_analysis_timestamp = last_job.completed_at.strftime("%Y-%m-%d %H:%M:%S") if last_job and last_job.completed_at else datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    data_source = "Sentinel-2 L2A (Copernicus CDSE / Karnataka Demo Repository)"

    return DashboardStats(
        monitored_parcels=parcels_count,
        total_area_hectares=round(float(total_area_ha), 2),
        new_changes_detected=new_changes,
        pending_alerts=pending_alerts,
        high_risk_alerts=high_risk_alerts,
        awaiting_inspection=awaiting_inspection,
        confirmed_encroachments=confirmed_encroachments,
        changes_last_30_days=changes_last_30_days,
        is_demo_mode=settings.DEMO_MODE,
        latest_imagery_date=latest_imagery_date,
        last_analysis_timestamp=last_analysis_timestamp,
        data_source=data_source
    )

@router.get("/trends")
def get_dashboard_trends(db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    # Category distribution
    categories = db.query(
        DetectedChange.category,
        func.count(DetectedChange.id)
    ).group_by(DetectedChange.category).all()

    category_data = [
        {"name": cat.replace('_', ' ').title(), "count": count, "category": cat}
        for cat, count in categories
    ]

    # Risk distribution
    risks = db.query(
        Alert.risk_level,
        func.count(Alert.id)
    ).group_by(Alert.risk_level).all()

    risk_data = [
        {"name": r, "count": count}
        for r, count in risks
    ]

    # Time series (by month or acquisition)
    timeline_changes = db.query(
        DetectedChange.latest_observed_date,
        func.count(DetectedChange.id),
        func.sum(DetectedChange.affected_area_sqm)
    ).group_by(DetectedChange.latest_observed_date).order_by(DetectedChange.latest_observed_date.asc()).all()

    timeline_data = [
        {
            "date": row[0],
            "count": row[1],
            "area_sqm": round(float(row[2] or 0), 1)
        }
        for row in timeline_changes
    ]

    return {
        "categories": category_data,
        "risks": risk_data,
        "timeline": timeline_data
    }
