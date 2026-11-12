from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.database import get_db
from app.models import MonitoringZone
from app.schemas import (
    SatellitePreviewRequest,
    SatellitePreviewResponse,
    SatelliteCompareRequest,
    SatelliteCompareResponse,
)
from app.services.earth_engine_service import (
    EarthEngineCollectionEmptyError,
    EarthEngineConfigurationError,
    EarthEngineRequestError,
    earth_engine_service,
)

router = APIRouter(prefix="/api/satellite", tags=["Google Earth Engine Satellite Imagery"])


def resolve_geometry(db: Session, zone_id, geometry):
    if geometry is not None:
        return geometry
    if zone_id is None:
        raise HTTPException(
            status_code=422,
            detail="Provide zone_id or monitoring polygon geometry.",
        )
    zone = db.query(MonitoringZone).filter(MonitoringZone.id == zone_id).first()
    if not zone:
        raise HTTPException(status_code=404, detail="Monitoring zone not found.")
    if not zone.geojson:
        raise HTTPException(
            status_code=422,
            detail="The selected monitoring zone has no stored GeoJSON geometry.",
        )
    return zone.geojson


@router.get("/health")
def satellite_health(current_user=Depends(get_current_user)):
    return earth_engine_service.health()


@router.post("/preview", response_model=SatellitePreviewResponse)
def satellite_preview(
    request: SatellitePreviewRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    geometry = resolve_geometry(db, request.zone_id, request.geometry)
    try:
        imagery = earth_engine_service.acquire(
            geometry=geometry,
            start_date=request.start_date,
            end_date=request.end_date,
            max_cloud_coverage=request.max_cloud_coverage,
            width=request.width,
            height=request.height,
            resolution_meters=request.resolution_meters,
        )
        return SatellitePreviewResponse(status="completed", imagery=imagery)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except EarthEngineCollectionEmptyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except EarthEngineConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except EarthEngineRequestError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.post("/compare", response_model=SatelliteCompareResponse)
def satellite_compare(
    request: SatelliteCompareRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    geometry = resolve_geometry(db, request.zone_id, request.geometry)
    try:
        historical = earth_engine_service.acquire(
            geometry=geometry,
            start_date=request.historical_start_date,
            end_date=request.historical_end_date,
            max_cloud_coverage=request.max_cloud_coverage,
            width=request.width,
            height=request.height,
            resolution_meters=request.resolution_meters,
        )
        recent = earth_engine_service.acquire(
            geometry=geometry,
            start_date=request.recent_start_date,
            end_date=request.recent_end_date,
            max_cloud_coverage=request.max_cloud_coverage,
            width=request.width,
            height=request.height,
            resolution_meters=request.resolution_meters,
        )
        hist_scene_id = None
        recent_scene_id = None
        if request.zone_id:
            import os
            from datetime import datetime
            from app.models import SatelliteScene
            from app.config import settings

            # Keep image_path/image_url as the established preview-image contract.
            # The raster_url in metadata_json is the private native analysis input.
            hist_img_path = os.path.join(settings.STORAGE_DIR, historical["image_url"].removeprefix("/storage/"))
            recent_img_path = os.path.join(settings.STORAGE_DIR, recent["image_url"].removeprefix("/storage/"))

            hist_scene = db.query(SatelliteScene).filter(
                SatelliteScene.zone_id == request.zone_id,
                SatelliteScene.image_url == historical["image_url"]
            ).first()
            if not hist_scene:
                hist_scene = SatelliteScene(
                    title=f"Sentinel-2 Historical ({historical.get('date') or request.historical_end_date}) - Zone #{request.zone_id}",
                    provider="SENTINEL_2",
                    acquisition_date=historical.get("date") or request.historical_end_date,
                    cloud_coverage_percentage=historical.get("cloud_coverage_percentage") or 0.0,
                    resolution_meters=float(historical.get("resolution_meters", 10.0)),
                    image_path=hist_img_path,
                    image_url=historical["image_url"],
                    thumbnail_url=historical["thumbnail_url"],
                    zone_id=request.zone_id,
                    metadata_json=historical,
                    created_at=datetime.utcnow()
                )
                db.add(hist_scene)
                db.commit()
                db.refresh(hist_scene)
            hist_scene_id = hist_scene.id

            recent_scene = db.query(SatelliteScene).filter(
                SatelliteScene.zone_id == request.zone_id,
                SatelliteScene.image_url == recent["image_url"]
            ).first()
            if not recent_scene:
                recent_scene = SatelliteScene(
                    title=f"Sentinel-2 Recent ({recent.get('date') or request.recent_end_date}) - Zone #{request.zone_id}",
                    provider="SENTINEL_2",
                    acquisition_date=recent.get("date") or request.recent_end_date,
                    cloud_coverage_percentage=recent.get("cloud_coverage_percentage") or 0.0,
                    resolution_meters=float(recent.get("resolution_meters", 10.0)),
                    image_path=recent_img_path,
                    image_url=recent["image_url"],
                    thumbnail_url=recent["thumbnail_url"],
                    zone_id=request.zone_id,
                    metadata_json=recent,
                    created_at=datetime.utcnow()
                )
                db.add(recent_scene)
                db.commit()
                db.refresh(recent_scene)
            recent_scene_id = recent_scene.id

        return SatelliteCompareResponse(
            status="completed",
            historical=historical,
            recent=recent,
            historical_scene_id=hist_scene_id,
            recent_scene_id=recent_scene_id,
            zone_id=request.zone_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except EarthEngineCollectionEmptyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except EarthEngineConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except EarthEngineRequestError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
