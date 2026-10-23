import os
import shutil
import uuid
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from app.config import settings
from app.database import get_db, SessionLocal
from app.models import DetectionJob, DetectedChange, SatelliteScene, MonitoringZone
from app.schemas import (
    DetectionJobCreate, DetectionJobResponse, DetectedChangeSchema,
    LevirPredictionRequest, LevirPredictionResponse
)
from app.core.deps import get_current_user, require_roles, log_audit
from app.services.change_detection.service import change_detection_service
from app.services.levir_service import levir_model_service

router = APIRouter(prefix="/api/analysis", tags=["AI Change Detection Analysis"])

def execute_detection_background(job_id: int):
    """Background worker for long-running change detection pipeline"""
    db = SessionLocal()
    try:
        change_detection_service.run_detection_pipeline(db, job_id)
    except Exception as e:
        print(f"Background execution error for job {job_id}: {e}")
    finally:
        db.close()

@router.get("/jobs", response_model=List[DetectionJobResponse])
def list_jobs(db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    jobs = db.query(DetectionJob).order_by(DetectionJob.created_at.desc()).all()
    results = []
    for j in jobs:
        count = db.query(DetectedChange).filter(DetectedChange.job_id == j.id).count()
        res = DetectionJobResponse.model_validate(j)
        res.changes_count = count
        results.append(res)
    return results

@router.get("/jobs/{job_id}", response_model=DetectionJobResponse)
def get_job(job_id: int, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    job = db.query(DetectionJob).filter(DetectionJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    count = db.query(DetectedChange).filter(DetectedChange.job_id == job.id).count()
    res = DetectionJobResponse.model_validate(job)
    res.changes_count = count
    return res

@router.post("/run", response_model=DetectionJobResponse)
def run_analysis(
    req: DetectionJobCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user = Depends(require_roles(["ADMIN", "MONITORING_OFFICER"]))
):
    job_code = f"JOB-{uuid.uuid4().hex[:8].upper()}"
    job = DetectionJob(
        job_code=job_code,
        zone_id=req.zone_id,
        historical_scene_id=req.historical_scene_id,
        recent_scene_id=req.recent_scene_id,
        algorithm=req.algorithm,
        status="PENDING",
        progress=0,
        parameters=req.parameters,
        created_at=datetime.utcnow()
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    # Launch in background so API remains fast & non-blocking
    background_tasks.add_task(execute_detection_background, job.id)

    log_audit(db, current_user.email, "LAUNCH_DETECTION", "DETECTION_JOB", str(job.id), f"Launched {job.job_code}")

    res = DetectionJobResponse.model_validate(job)
    res.changes_count = 0
    return res

@router.get("/changes", response_model=List[DetectedChangeSchema])
def list_changes(
    zone_id: Optional[int] = None,
    category: Optional[str] = None,
    risk_level: Optional[str] = None,
    trend: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    query = db.query(DetectedChange)
    if zone_id:
        query = query.filter(DetectedChange.zone_id == zone_id)
    if category:
        query = query.filter(DetectedChange.category == category)
    if risk_level:
        query = query.filter(DetectedChange.risk_level == risk_level)
    if trend:
        query = query.filter(DetectedChange.trend == trend)
    changes = query.order_by(DetectedChange.created_at.desc()).all()
    return [DetectedChangeSchema.model_validate(c) for c in changes]

@router.post("/levir/predict", response_model=LevirPredictionResponse)
def predict_levir_change(
    req: LevirPredictionRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Executes trained LEVIR-CD+ HistGradientBoosting building change detection on registered images.
    Validates dimensional and spectral compatibility, returns pixel change mask, overlay, and metrics.
    Optionally generates a potential building change alert for human verification.
    """
    hist_scene = None
    recent_scene = None

    if req.earlier_scene_id:
        hist_scene = db.query(SatelliteScene).filter(SatelliteScene.id == req.earlier_scene_id).first()
        if not hist_scene:
            raise HTTPException(status_code=404, detail=f"Earlier satellite scene {req.earlier_scene_id} not found")
        earlier_path = hist_scene.image_path
        earlier_url = hist_scene.image_url
    elif req.earlier_image_path:
        earlier_path = req.earlier_image_path
        earlier_url = f"/storage/{os.path.basename(earlier_path)}"
    else:
        raise HTTPException(status_code=400, detail="Must provide earlier_scene_id or earlier_image_path")

    if req.later_scene_id:
        recent_scene = db.query(SatelliteScene).filter(SatelliteScene.id == req.later_scene_id).first()
        if not recent_scene:
            raise HTTPException(status_code=404, detail=f"Later satellite scene {req.later_scene_id} not found")
        later_path = recent_scene.image_path
        later_url = recent_scene.image_url
    elif req.later_image_path:
        later_path = req.later_image_path
        later_url = f"/storage/{os.path.basename(later_path)}"
    else:
        raise HTTPException(status_code=400, detail="Must provide later_scene_id or later_image_path")

    try:
        prediction = levir_model_service.run_prediction(
            earlier_path=earlier_path,
            later_path=later_path,
            threshold=req.threshold if req.threshold is not None else 0.7
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Model prediction error: {str(e)}")

    candidate_alert_id = None
    candidate_alert_code = None

    if req.generate_alert:
        target_zone_id = req.zone_id or (recent_scene.zone_id if recent_scene else None) or (hist_scene.zone_id if hist_scene else None)
        if target_zone_id:
            alert = levir_model_service.generate_potential_change_alert(
                db=db,
                prediction_result=prediction,
                zone_id=target_zone_id,
                historical_scene=hist_scene,
                recent_scene=recent_scene,
                parcel_id=req.parcel_id
            )
            if alert:
                candidate_alert_id = alert.id
                candidate_alert_code = alert.alert_code
                log_audit(
                    db,
                    current_user.email,
                    "GENERATE_LEVIR_ALERT",
                    "ALERT",
                    str(alert.id),
                    f"Generated alert {alert.alert_code} via LEVIR-CD+ model"
                )

    return LevirPredictionResponse(
        model_name=prediction["model_name"],
        model_type=prediction["model_type"],
        feature_schema=prediction["feature_schema"],
        threshold=prediction["threshold"],
        dimensions=prediction["dimensions"],
        total_pixels=prediction["total_pixels"],
        changed_pixels=prediction["changed_pixels"],
        changed_pixel_percentage=prediction["changed_pixel_percentage"],
        mean_probability=prediction["mean_probability"],
        max_probability=prediction["max_probability"],
        min_probability=prediction["min_probability"],
        mask_url=prediction["mask_url"],
        overlay_url=prediction["overlay_url"],
        earlier_image_url=earlier_url,
        later_image_url=later_url,
        candidate_alert_id=candidate_alert_id,
        candidate_alert_code=candidate_alert_code,
        disclaimer=prediction["disclaimer"]
    )

@router.post("/levir/predict-upload", response_model=LevirPredictionResponse)
async def predict_levir_upload(
    earlier_file: UploadFile = File(...),
    later_file: UploadFile = File(...),
    threshold: float = Form(0.7),
    zone_id: Optional[int] = Form(None),
    generate_alert: bool = Form(False),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Accepts uploaded pair of satellite/aerial images, validates dimensions,
    and runs LEVIR-CD+ building change detection model.
    """
    upload_dir = os.path.join(settings.STORAGE_DIR, "imagery")
    os.makedirs(upload_dir, exist_ok=True)

    token = uuid.uuid4().hex[:8]
    ext_earlier = os.path.splitext(earlier_file.filename)[1].lower() or ".png"
    ext_later = os.path.splitext(later_file.filename)[1].lower() or ".png"

    earlier_path = os.path.join(upload_dir, f"upload_earlier_{token}{ext_earlier}")
    later_path = os.path.join(upload_dir, f"upload_later_{token}{ext_later}")

    with open(earlier_path, "wb") as f_out:
        shutil.copyfileobj(earlier_file.file, f_out)
    with open(later_path, "wb") as f_out:
        shutil.copyfileobj(later_file.file, f_out)

    earlier_url = f"/storage/imagery/{os.path.basename(earlier_path)}"
    later_url = f"/storage/imagery/{os.path.basename(later_path)}"

    try:
        prediction = levir_model_service.run_prediction(
            earlier_path=earlier_path,
            later_path=later_path,
            threshold=threshold
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Model execution error: {str(e)}")

    candidate_alert_id = None
    candidate_alert_code = None

    if generate_alert and zone_id:
        alert = levir_model_service.generate_potential_change_alert(
            db=db,
            prediction_result=prediction,
            zone_id=zone_id,
            historical_scene=None,
            recent_scene=None
        )
        if alert:
            candidate_alert_id = alert.id
            candidate_alert_code = alert.alert_code

    return LevirPredictionResponse(
        model_name=prediction["model_name"],
        model_type=prediction["model_type"],
        feature_schema=prediction["feature_schema"],
        threshold=prediction["threshold"],
        dimensions=prediction["dimensions"],
        total_pixels=prediction["total_pixels"],
        changed_pixels=prediction["changed_pixels"],
        changed_pixel_percentage=prediction["changed_pixel_percentage"],
        mean_probability=prediction["mean_probability"],
        max_probability=prediction["max_probability"],
        min_probability=prediction["min_probability"],
        mask_url=prediction["mask_url"],
        overlay_url=prediction["overlay_url"],
        earlier_image_url=earlier_url,
        later_image_url=later_url,
        candidate_alert_id=candidate_alert_id,
        candidate_alert_code=candidate_alert_code,
        disclaimer=prediction["disclaimer"]
    )
