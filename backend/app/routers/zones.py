from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional, Any, Tuple
from datetime import datetime
from shapely.geometry import shape

from app.database import get_db
from app.models import (
    MonitoringZone, LandParcel, RestrictedBoundary, Alert,
    DetectedChange, DetectionJob, SatelliteScene
)
from app.schemas import (
    MonitoringZoneResponse, MonitoringZoneCreate, MonitoringZoneUpdate,
    LandParcelSchema, RestrictedBoundarySchema
)
from app.core.deps import get_current_user, require_roles, log_audit
from app.services.spatial import calculate_polygon_area_sqm, sqm_to_hectares

router = APIRouter(prefix="/api/zones", tags=["Monitoring Zones & Parcels"])


def validate_and_compute_zone_geometry(geojson: Any) -> Tuple[dict, float]:
    """
    Validates GeoJSON Polygon or MultiPolygon:
    - Must be a valid dictionary with type Polygon or MultiPolygon (or Feature)
    - Valid coordinates, closed ring
    - Non-empty, valid non-self-intersecting shape
    - Computes accurate geodesic area in hectares
    """
    if not geojson:
        raise HTTPException(status_code=422, detail="A valid GeoJSON boundary polygon is required.")

    geom_dict = geojson
    if isinstance(geom_dict, dict) and geom_dict.get("type") == "Feature":
        geom_dict = geom_dict.get("geometry", {})

    if not isinstance(geom_dict, dict) or geom_dict.get("type") not in ("Polygon", "MultiPolygon"):
        raise HTTPException(status_code=422, detail="Geometry must be a GeoJSON Polygon or MultiPolygon.")

    coordinates = geom_dict.get("coordinates")
    if not coordinates or not isinstance(coordinates, list):
        raise HTTPException(status_code=422, detail="Geometry coordinates must be a non-empty list.")

    try:
        s_geom = shape(geom_dict)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Invalid geometry structure: {exc}")

    if s_geom.is_empty:
        raise HTTPException(status_code=422, detail="Geometry cannot be empty.")
    if not s_geom.is_valid:
        raise HTTPException(status_code=422, detail="Geometry is self-intersecting or invalid.")

    # Check coordinate ranges
    min_lng, min_lat, max_lng, max_lat = s_geom.bounds
    if not (-180.0 <= min_lng <= 180.0 and -180.0 <= max_lng <= 180.0 and
            -90.0 <= min_lat <= 90.0 and -90.0 <= max_lat <= 90.0):
        raise HTTPException(status_code=422, detail="Coordinates are outside valid latitude/longitude bounds.")

    # Geodesic area calculation
    area_sqm = calculate_polygon_area_sqm(geom_dict)
    area_ha = sqm_to_hectares(area_sqm)
    return geom_dict, area_ha


@router.get("", response_model=List[MonitoringZoneResponse])
def get_monitoring_zones(db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    zones = db.query(MonitoringZone).order_by(MonitoringZone.created_at.desc()).all()
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
    current_user = Depends(require_roles(["ADMIN", "MONITORING_OFFICER"]))
):
    name = (zone_in.name or "").strip()
    if not name:
        raise HTTPException(status_code=422, detail="Monitoring area name cannot be empty.")

    district = (zone_in.district or "Bengaluru Urban").strip()
    state = (zone_in.state or "Karnataka").strip()

    geom_dict, computed_area_ha = validate_and_compute_zone_geometry(zone_in.geojson)
    final_area = zone_in.area_hectares if zone_in.area_hectares and zone_in.area_hectares > 0 else computed_area_ha

    zone = MonitoringZone(
        name=name,
        district=district,
        state=state,
        description=zone_in.description,
        area_hectares=final_area,
        geojson=geom_dict,
        risk_status="NORMAL",
        created_at=datetime.utcnow()
    )
    db.add(zone)
    db.commit()
    db.refresh(zone)
    log_audit(db, current_user.email, "CREATE_ZONE", "MONITORING_ZONE", str(zone.id), f"Created {zone.name} ({final_area} ha)")
    return MonitoringZoneResponse.model_validate(zone)

@router.put("/{zone_id}", response_model=MonitoringZoneResponse)
def update_monitoring_zone(
    zone_id: int,
    zone_in: MonitoringZoneUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(require_roles(["ADMIN", "MONITORING_OFFICER"]))
):
    zone = db.query(MonitoringZone).filter(MonitoringZone.id == zone_id).first()
    if not zone:
        raise HTTPException(status_code=404, detail="Monitoring zone not found")

    if zone_in.name is not None:
        name = zone_in.name.strip()
        if not name:
            raise HTTPException(status_code=422, detail="Monitoring area name cannot be empty.")
        zone.name = name

    if zone_in.district is not None:
        zone.district = zone_in.district.strip()
    if zone_in.state is not None:
        zone.state = zone_in.state.strip()
    if zone_in.description is not None:
        zone.description = zone_in.description

    if zone_in.geojson is not None:
        geom_dict, computed_area_ha = validate_and_compute_zone_geometry(zone_in.geojson)
        zone.geojson = geom_dict
        zone.area_hectares = zone_in.area_hectares if zone_in.area_hectares and zone_in.area_hectares > 0 else computed_area_ha
    elif zone_in.area_hectares is not None:
        zone.area_hectares = zone_in.area_hectares

    zone.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(zone)

    p_count = db.query(LandParcel).filter(LandParcel.zone_id == zone.id).count()
    a_count = db.query(Alert).filter(Alert.zone_id == zone.id).count()
    res = MonitoringZoneResponse.model_validate(zone)
    res.parcels_count = p_count
    res.alerts_count = a_count

    log_audit(db, current_user.email, "UPDATE_ZONE", "MONITORING_ZONE", str(zone.id), f"Updated {zone.name}")
    return res

@router.delete("/{zone_id}")
def delete_monitoring_zone(
    zone_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(require_roles(["ADMIN", "MONITORING_OFFICER"]))
):
    zone = db.query(MonitoringZone).filter(MonitoringZone.id == zone_id).first()
    if not zone:
        raise HTTPException(status_code=404, detail="Monitoring zone not found")

    zone_name = zone.name

    # Clean up associated alerts, changes, jobs, and scenes
    db.query(Alert).filter(Alert.zone_id == zone_id).delete(synchronize_session=False)
    db.query(DetectedChange).filter(DetectedChange.zone_id == zone_id).delete(synchronize_session=False)
    db.query(DetectionJob).filter(DetectionJob.zone_id == zone_id).delete(synchronize_session=False)
    db.query(SatelliteScene).filter(SatelliteScene.zone_id == zone_id).delete(synchronize_session=False)

    db.delete(zone)
    db.commit()

    log_audit(db, current_user.email, "DELETE_ZONE", "MONITORING_ZONE", str(zone_id), f"Deleted monitoring zone {zone_name}")
    return {"message": f"Monitoring zone '{zone_name}' (ID: {zone_id}) deleted successfully.", "id": zone_id}

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
