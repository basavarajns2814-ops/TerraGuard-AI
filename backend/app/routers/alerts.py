import os
import shutil
import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from app.config import settings
from app.database import get_db
from app.models import Alert, AlertNote, AlertEvidence, User, TemporalObservation
from app.schemas import (
    AlertResponse, AlertStatusUpdate, AlertAssignRequest,
    AlertNoteCreate, AlertNoteResponse, AlertEvidenceResponse
)
from app.core.deps import get_current_user, require_roles, log_audit

router = APIRouter(prefix="/api/alerts", tags=["Alerts & Evidence Management"])

def enrich_alert_response(alert: Alert) -> AlertResponse:
    res = AlertResponse.model_validate(alert)
    res.zone_name = alert.zone.name if alert.zone else "Default Zone"
    res.district = alert.zone.district if alert.zone else "Bengaluru"
    res.parcel_number = alert.parcel.parcel_number if alert.parcel else "N/A"
    res.assigned_to_name = alert.assigned_to.full_name if alert.assigned_to else "Unassigned"
    res.notes = [AlertNoteResponse.model_validate(n) for n in alert.notes]
    res.evidence = [AlertEvidenceResponse.model_validate(e) for e in alert.evidence]

    if alert.change and alert.change.observations:
        from app.schemas import TemporalObservationSchema
        res.temporal_history = [
            TemporalObservationSchema.model_validate(o)
            for o in alert.change.observations
        ]
    return res

@router.get("", response_model=List[AlertResponse])
def list_alerts(
    zone_id: Optional[int] = None,
    status: Optional[str] = None,
    risk_level: Optional[str] = None,
    category: Optional[str] = None,
    assigned_to_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    query = db.query(Alert)
    if zone_id:
        query = query.filter(Alert.zone_id == zone_id)
    if status:
        query = query.filter(Alert.status == status)
    if risk_level:
        query = query.filter(Alert.risk_level == risk_level)
    if category:
        query = query.filter(Alert.category == category)
    if assigned_to_id:
        query = query.filter(Alert.assigned_to_id == assigned_to_id)

    alerts = query.order_by(Alert.risk_score.desc(), Alert.created_at.desc()).all()
    return [enrich_alert_response(a) for a in alerts]

@router.get("/{alert_id}", response_model=AlertResponse)
def get_alert_detail(alert_id: int, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return enrich_alert_response(alert)

@router.post("/{alert_id}/status", response_model=AlertResponse)
def update_alert_status(
    alert_id: int,
    req: AlertStatusUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    old_status = alert.status
    alert.status = req.status
    if req.dismissal_reason:
        alert.dismissal_reason = req.dismissal_reason
    if req.resolution_details:
        alert.resolution_details = req.resolution_details
    alert.updated_at = datetime.utcnow()

    # Add audit log and automatic note
    note = AlertNote(
        alert_id=alert.id,
        user_id=current_user.id,
        user_name=current_user.full_name,
        user_role=current_user.role,
        note=f"Status changed from {old_status} to {req.status}." + (f" Note: {req.dismissal_reason or req.resolution_details}" if (req.dismissal_reason or req.resolution_details) else ""),
        created_at=datetime.utcnow()
    )
    db.add(note)
    db.commit()
    db.refresh(alert)

    log_audit(db, current_user.email, "UPDATE_ALERT_STATUS", "ALERT", str(alert.id), f"Changed status to {req.status}")
    return enrich_alert_response(alert)

@router.post("/{alert_id}/assign", response_model=AlertResponse)
def assign_officer(
    alert_id: int,
    req: AlertAssignRequest,
    db: Session = Depends(get_db),
    current_user = Depends(require_roles(["ADMIN", "MONITORING_OFFICER"]))
):
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    assignee = db.query(User).filter(User.id == req.assigned_to_id).first()
    if not assignee:
        raise HTTPException(status_code=404, detail="Assigned officer not found")

    alert.assigned_to_id = assignee.id
    if alert.status == "NEW":
        alert.status = "UNDER_REVIEW"
    alert.updated_at = datetime.utcnow()

    note = AlertNote(
        alert_id=alert.id,
        user_id=current_user.id,
        user_name=current_user.full_name,
        user_role=current_user.role,
        note=f"Assigned to {assignee.full_name} ({assignee.role})",
        created_at=datetime.utcnow()
    )
    db.add(note)
    db.commit()
    db.refresh(alert)

    log_audit(db, current_user.email, "ASSIGN_ALERT", "ALERT", str(alert.id), f"Assigned to {assignee.email}")
    return enrich_alert_response(alert)

@router.post("/{alert_id}/notes", response_model=AlertNoteResponse)
def add_note(
    alert_id: int,
    req: AlertNoteCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    note = AlertNote(
        alert_id=alert.id,
        user_id=current_user.id,
        user_name=current_user.full_name,
        user_role=current_user.role,
        note=req.note,
        created_at=datetime.utcnow()
    )
    db.add(note)
    db.commit()
    db.refresh(note)

    log_audit(db, current_user.email, "ADD_ALERT_NOTE", "ALERT_NOTE", str(note.id), "Added investigation note")
    return AlertNoteResponse.model_validate(note)

@router.post("/{alert_id}/evidence", response_model=AlertEvidenceResponse)
async def upload_evidence(
    alert_id: int,
    file: UploadFile = File(...),
    caption: Optional[str] = Form(None),
    latitude: Optional[float] = Form(None),
    longitude: Optional[float] = Form(None),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    ext = os.path.splitext(file.filename)[1].lower()
    filename = f"evid_{uuid.uuid4()}{ext}"
    dest_path = os.path.join(settings.STORAGE_DIR, "evidence", filename)

    with open(dest_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    file_url = f"/storage/evidence/{filename}"

    evidence = AlertEvidence(
        alert_id=alert.id,
        user_id=current_user.id,
        file_path=dest_path,
        file_url=file_url,
        file_type=file.content_type or "image/jpeg",
        caption=caption,
        uploaded_by_name=current_user.full_name,
        latitude=latitude,
        longitude=longitude,
        created_at=datetime.utcnow()
    )
    db.add(evidence)
    db.commit()
    db.refresh(evidence)

    log_audit(db, current_user.email, "UPLOAD_EVIDENCE", "ALERT_EVIDENCE", str(evidence.id), f"Attached evidence {filename}")
    return AlertEvidenceResponse.model_validate(evidence)
