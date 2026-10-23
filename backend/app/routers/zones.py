from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from app.database import get_db
from app.models import MonitoringZone, LandParcel, RestrictedBoundary, Alert
from app.schemas import (
    MonitoringZoneResponse, MonitoringZoneCreate,
    LandParcelSchema, RestrictedBoundarySchema
)
from app.core.deps import get_current_user, require_roles, log_audit

router = APIRouter(prefix="/api/zones", tags=["Monitoring Zones & Parcels"])

@router.get("", response_model=List[MonitoringZoneResponse])
def get_monitoring_zones(db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    zones = db.query(MonitoringZone).all()
    results = []
    for z in zones:
        p_count = db.query(LandParcel).filter(LandParcel.zone_id == z.id).count()
        a_count = db.query(Alert).filter(Alert.zone_id == z.id).count()
        res = MonitoringZoneResponse.model_validate(z)
        res.parcels_count = p_count
        res.alerts_count = a_count
        results.append(res)
    return results

@router.get("/{zone_id}", response_model=MonitoringZoneResponse)
def get_zone_by_id(zone_id: int, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    zone = db.query(MonitoringZone).filter(MonitoringZone.id == zone_id).first()
    if not zone:
        raise HTTPException(status_code=404, detail="Zone not found")
    res = MonitoringZoneResponse.model_validate(zone)
    res.parcels_count = db.query(LandParcel).filter(LandParcel.zone_id == zone.id).count()
    res.alerts_count = db.query(Alert).filter(Alert.zone_id == zone.id).count()
    return res

@router.post("", response_model=MonitoringZoneResponse)
def create_monitoring_zone(
    zone_in: MonitoringZoneCreate,
    db: Session = Depends(get_db),
    current_user = Depends(require_roles(["ADMIN"]))
):
    zone = MonitoringZone(
        name=zone_in.name,
        district=zone_in.district,
        state=zone_in.state,
        description=zone_in.description,
        area_hectares=zone_in.area_hectares,
        geojson=zone_in.geojson,
        risk_status="NORMAL",
        created_at=datetime.utcnow()
    )
    db.add(zone)
    db.commit()
    db.refresh(zone)
    log_audit(db, current_user.email, "CREATE_ZONE", "MONITORING_ZONE", str(zone.id), f"Created {zone.name}")
    return MonitoringZoneResponse.model_validate(zone)

@router.get("/parcels/all", response_model=List[LandParcelSchema])
def get_all_parcels(
    zone_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    query = db.query(LandParcel)
    if zone_id:
        query = query.filter(LandParcel.zone_id == zone_id)
    return [LandParcelSchema.model_validate(p) for p in query.all()]

@router.get("/boundaries/all", response_model=List[RestrictedBoundarySchema])
def get_restricted_boundaries(
    zone_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    query = db.query(RestrictedBoundary)
    if zone_id:
        query = query.filter((RestrictedBoundary.zone_id == zone_id) | (RestrictedBoundary.zone_id == None))
    return [RestrictedBoundarySchema.model_validate(b) for b in query.all()]
