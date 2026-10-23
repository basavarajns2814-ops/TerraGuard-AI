from typing import Optional, List
from sqlalchemy.orm import Session
from datetime import datetime
from app.models import Alert, DetectedChange, Notification, User, MonitoringZone

def generate_or_update_alert(
    db: Session,
    change: DetectedChange,
    zone: MonitoringZone,
    historical_image_url: Optional[str] = None,
    recent_image_url: Optional[str] = None,
    change_mask_url: Optional[str] = None
) -> Alert:
    """
    Creates an alert for a detected change or updates an existing alert.
    Ensures deduplication across repeated observation dates.
    """
    existing_alert = db.query(Alert).filter(Alert.change_id == change.id).first()

    if existing_alert:
        # Update existing alert with latest metrics
        existing_alert.latest_observed_date = change.latest_observed_date
        existing_alert.risk_score = change.risk_score
        existing_alert.risk_level = change.risk_level
        existing_alert.confidence_score = change.confidence_score
        existing_alert.affected_area_sqm = change.affected_area_sqm
        existing_alert.affected_area_hectares = change.affected_area_hectares
        existing_alert.risk_reasons = change.risk_reasons
        if change_mask_url:
            existing_alert.change_mask_url = change_mask_url
        if recent_image_url:
            existing_alert.recent_image_url = recent_image_url
        existing_alert.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(existing_alert)
        return existing_alert

    # Generate unique alert code e.g. TG-2026-0042
    count = db.query(Alert).count() + 1
    alert_code = f"TG-2026-{count:04d}"

    alert = Alert(
        alert_code=alert_code,
        change_id=change.id,
        zone_id=zone.id,
        parcel_id=change.parcel_id,
        category=change.category,
        risk_level=change.risk_level,
        risk_score=change.risk_score,
        confidence_score=change.confidence_score,
        affected_area_sqm=change.affected_area_sqm,
        affected_area_hectares=change.affected_area_hectares,
        centroid_lat=change.centroid_lat,
        centroid_lng=change.centroid_lng,
        geojson=change.geojson,
        historical_image_url=historical_image_url,
        recent_image_url=recent_image_url,
        change_mask_url=change_mask_url,
        status="NEW",
        first_observed_date=change.first_observed_date,
        latest_observed_date=change.latest_observed_date,
        risk_reasons=change.risk_reasons,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)

    # If HIGH or CRITICAL, send in-app notification to monitoring officers and admins
    if alert.risk_level in ["HIGH", "CRITICAL"]:
        create_alert_notifications(db, alert)

    return alert

def create_alert_notifications(db: Session, alert: Alert):
    try:
        users = db.query(User).filter(User.role.in_(["ADMIN", "MONITORING_OFFICER"])).all()
        for u in users:
            notification = Notification(
                user_id=u.id,
                title=f"High Risk Alert {alert.alert_code}: {alert.category.replace('_', ' ').title()}",
                message=f"Change of {alert.affected_area_sqm:.1f} m² detected in {alert.zone.name if alert.zone else 'Zone'} with risk score {alert.risk_score}.",
                type="ALERT_HIGH",
                alert_id=alert.id,
                is_read=False,
                created_at=datetime.utcnow()
            )
            db.add(notification)
        db.commit()
    except Exception as e:
        print(f"Error creating notification: {e}")
