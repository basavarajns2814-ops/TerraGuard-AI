import os
import shutil
import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from PIL import Image

from app.config import settings
from app.database import get_db
from app.models import SatelliteScene, MonitoringZone
from app.schemas import SatelliteSceneSchema
from app.core.deps import get_current_user, require_roles, log_audit
from app.services.satellite_provider import get_satellite_provider

router = APIRouter(prefix="/api/imagery", tags=["Satellite Imagery"])

@router.get("", response_model=List[SatelliteSceneSchema])
def list_imagery(
    zone_id: Optional[int] = None,
    provider: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    query = db.query(SatelliteScene)
    if zone_id:
        query = query.filter(SatelliteScene.zone_id == zone_id)
    if provider:
        query = query.filter(SatelliteScene.provider == provider)
    scenes = query.order_by(SatelliteScene.acquisition_date.desc()).all()
    return [SatelliteSceneSchema.model_validate(s) for s in scenes]

@router.get("/{scene_id}", response_model=SatelliteSceneSchema)
def get_scene(scene_id: int, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    scene = db.query(SatelliteScene).filter(SatelliteScene.id == scene_id).first()
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")
    return SatelliteSceneSchema.model_validate(scene)

@router.post("/upload", response_model=SatelliteSceneSchema)
async def upload_imagery(
    file: UploadFile = File(...),
    title: str = Form(...),
    acquisition_date: str = Form(...),
    zone_id: Optional[int] = Form(None),
    provider: str = Form("LOCAL_UPLOAD"),
    cloud_coverage: float = Form(0.0),
    db: Session = Depends(get_db),
    current_user = Depends(require_roles(["ADMIN", "MONITORING_OFFICER"]))
):
    # Validate extension
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in [".jpg", ".jpeg", ".png", ".tif", ".tiff"]:
        raise HTTPException(status_code=400, detail="Unsupported image format. Allowed: JPG, PNG, TIF")

    filename = f"{uuid.uuid4()}{ext}"
    dest_path = os.path.join(settings.STORAGE_DIR, "imagery", filename)

    with open(dest_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    image_url = f"/storage/imagery/{filename}"

    # Generate thumbnail
    thumb_url = image_url
    try:
        thumb_name = f"thumb_{filename}.jpg"
        thumb_path = os.path.join(settings.STORAGE_DIR, "imagery", thumb_name)
        img = Image.open(dest_path).convert('RGB')
        img.thumbnail((256, 256))
        img.save(thumb_path, "JPEG")
        thumb_url = f"/storage/imagery/{thumb_name}"
    except Exception as e:
        print(f"Thumbnail error: {e}")

    scene = SatelliteScene(
        title=title,
        provider=provider,
        acquisition_date=acquisition_date,
        cloud_coverage_percentage=cloud_coverage,
        resolution_meters=10.0,
        image_path=dest_path,
        image_url=image_url,
        thumbnail_url=thumb_url,
        zone_id=zone_id,
        created_at=datetime.utcnow()
    )
    db.add(scene)
    db.commit()
    db.refresh(scene)

    log_audit(db, current_user.email, "UPLOAD_IMAGERY", "SATELLITE_SCENE", str(scene.id), f"Uploaded scene {title}")
    return SatelliteSceneSchema.model_validate(scene)

@router.get("/provider/search")
def search_provider_imagery(
    zone_id: int,
    start_date: str = Query("2026-01-01"),
    end_date: str = Query("2026-10-23"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    provider = get_satellite_provider("COPERNICUS" if settings.COPERNICUS_ENABLED else "LOCAL")
    results = provider.search_scenes(
        bbox=[77.6, 12.9, 77.7, 13.0],
        start_date=start_date,
        end_date=end_date
    )
    return {
        "provider": "Copernicus Sentinel-2 CDSE" if settings.COPERNICUS_ENABLED else "TerraGuard Local Karnataka Demo Repository",
        "results": results
    }
