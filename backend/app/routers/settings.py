from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models import AuditLog, SystemSetting
from app.schemas import AuditLogResponse, SystemSettingsSchema
from app.core.deps import get_current_user, require_roles, log_audit
from app.config import settings

router = APIRouter(prefix="/api/settings", tags=["System Settings & Audit"])

@router.get("", response_model=SystemSettingsSchema)
def get_system_settings(db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    return SystemSettingsSchema(
        detection_threshold_ndvi=0.22,
        detection_threshold_ndbi=0.18,
        min_change_area_sqm=120.0,
        risk_weight_boundary=40.0,
        risk_weight_area=30.0,
        risk_weight_persistence=30.0,
        auto_alert_high_risk=True,
        copernicus_enabled=settings.COPERNICUS_ENABLED,
        demo_mode=settings.DEMO_MODE
    )

@router.put("", response_model=SystemSettingsSchema)
def update_system_settings(
    req: SystemSettingsSchema,
    db: Session = Depends(get_db),
    current_user = Depends(require_roles(["ADMIN"]))
):
    log_audit(db, current_user.email, "UPDATE_SETTINGS", "SYSTEM_SETTINGS", "1", "Updated detection thresholds and weights")
    return req

@router.get("/audit-logs", response_model=List[AuditLogResponse])
def get_audit_logs(
    db: Session = Depends(get_db),
    current_user = Depends(require_roles(["ADMIN"]))
):
    logs = db.query(AuditLog).order_by(AuditLog.timestamp.desc()).limit(100).all()
    return [AuditLogResponse.model_validate(l) for l in logs]
