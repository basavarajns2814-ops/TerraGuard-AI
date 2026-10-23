import os
import uuid
import numpy as np
from PIL import Image
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from datetime import datetime

from app.config import settings
from app.models import DetectionJob, DetectedChange, SatelliteScene, MonitoringZone, LandParcel, RestrictedBoundary
from app.services.change_detection.spectral import SpectralChangeDetection
from app.services.change_detection.deep_learning import DeepLearningSegmentationStrategy
from app.services.change_detection.levir_strategy import LevirCdChangeDetectionStrategy
from app.services.change_detection.morphological import (
    morphological_clean,
    extract_connected_components,
    component_to_geojson_polygon
)
from app.services.spatial import (
    calculate_polygon_area_sqm,
    sqm_to_hectares,
    get_centroid_lat_lng,
    check_intersection_and_buffer,
    find_containing_parcel
)
from app.services.risk_scoring import evaluate_risk_and_confidence
from app.services.temporal import track_temporal_evolution
from app.services.alert_service import generate_or_update_alert

class ChangeDetectionService:
    def __init__(self):
        self.strategies = {
            "SPECTRAL_NDVI_NDBI_DIFFERENCING": SpectralChangeDetection(),
            "DEEP_LEARNING_SEGMENTATION": DeepLearningSegmentationStrategy(),
            "OPTICAL_DIFFERENCE": SpectralChangeDetection(),
            "LEVIR_CD_HIST_GRADIENT_BOOSTING": LevirCdChangeDetectionStrategy()
        }

    def run_detection_pipeline(
        self,
        db: Session,
        job_id: int
    ) -> List[DetectedChange]:
        """
        Executes end-to-end change detection pipeline for a given job.
        """
        job = db.query(DetectionJob).filter(DetectionJob.id == job_id).first()
        if not job:
            raise ValueError(f"Detection job {job_id} not found")

        try:
            job.status = "RUNNING"
            job.progress = 10
            db.commit()

            zone = db.query(MonitoringZone).filter(MonitoringZone.id == job.zone_id).first()
            hist_scene = db.query(SatelliteScene).filter(SatelliteScene.id == job.historical_scene_id).first()
            recent_scene = db.query(SatelliteScene).filter(SatelliteScene.id == job.recent_scene_id).first()

            if not hist_scene or not recent_scene:
                raise ValueError("Historical or recent satellite scene not found")

            # 1. Load images
            job.progress = 25
            db.commit()

            hist_img_pil = Image.open(hist_scene.image_path).convert('RGB')
            recent_img_pil = Image.open(recent_scene.image_path).convert('RGB')

            # Ensure matching dimensions
            if hist_img_pil.size != recent_img_pil.size:
                recent_img_pil = recent_img_pil.resize(hist_img_pil.size)

            w, h = hist_img_pil.size
            hist_np = np.array(hist_img_pil)
            recent_np = np.array(recent_img_pil)

            # 2. Select and run strategy
            job.progress = 45
            db.commit()

            strategy_name = job.algorithm or "SPECTRAL_NDVI_NDBI_DIFFERENCING"
            strategy = self.strategies.get(strategy_name, self.strategies["SPECTRAL_NDVI_NDBI_DIFFERENCING"])

            params = job.parameters or {}
            raw_mask, metadata = strategy.detect(hist_np, recent_np, params)

            # 3. Morphological cleaning & candidate isolation
            job.progress = 65
            db.commit()

            clean_mask = morphological_clean(raw_mask)

            # Save change mask artifact
            mask_filename = f"mask_{job.job_code}.png"
            mask_path = os.path.join(settings.STORAGE_DIR, "masks", mask_filename)
            mask_pil = Image.fromarray(clean_mask)
            mask_pil.save(mask_path)
            mask_url = f"/storage/masks/{mask_filename}"

            # 4. Extract spatial candidate blobs
            components = extract_connected_components(clean_mask, min_pixels=25)

            # Default bounding box if zone geojson not provided: Bellandur Lake & Sarjapur area, Karnataka
            # min_lng, min_lat, max_lng, max_lat
            bbox_geo = (77.6600, 12.9200, 77.6850, 12.9450)
            if zone and zone.geojson and "coordinates" in zone.geojson:
                try:
                    coords = zone.geojson["coordinates"][0]
                    lngs = [c[0] for c in coords]
                    lats = [c[1] for c in coords]
                    bbox_geo = (min(lngs), min(lats), max(lngs), max(lats))
                except Exception:
                    pass

            parcels = db.query(LandParcel).filter(LandParcel.zone_id == zone.id).all() if zone else []
            restricted_boundaries = db.query(RestrictedBoundary).filter(
                (RestrictedBoundary.zone_id == zone.id) | (RestrictedBoundary.zone_id == None)
            ).all() if zone else []

            job.progress = 80
            db.commit()

            detected_changes = []

            for comp in components[:10]: # Process top candidate clusters
                geojson_poly = component_to_geojson_polygon(comp, w, h, bbox_geo)
                area_sqm = calculate_polygon_area_sqm(geojson_poly)
                area_ha = sqm_to_hectares(area_sqm)
                centroid_lat, centroid_lng = get_centroid_lat_lng(geojson_poly)

                # Check containment in parcel
                matched_parcel = find_containing_parcel(geojson_poly, parcels)
                parcel_id = matched_parcel.id if matched_parcel else None
                owner_type = matched_parcel.owner_type if matched_parcel else "GOVERNMENT"

                # Check intersection with restricted boundaries (e.g. lake buffer)
                intersects_restricted = False
                restricted_name = None
                proximity_m = 9999.0

                for rb in restricted_boundaries:
                    if rb.geojson:
                        res = check_intersection_and_buffer(geojson_poly, rb.geojson, rb.buffer_distance_meters)
                        if res["intersects"]:
                            intersects_restricted = True
                            restricted_name = rb.name
                            proximity_m = 0.0
                            break
                        elif res["in_buffer"] and res["distance_meters"] < proximity_m:
                            proximity_m = res["distance_meters"]
                            restricted_name = rb.name

                # Determine category
                if intersects_restricted and "Lake" in (restricted_name or ""):
                    category = "WATER_BODY_ENCROACHMENT"
                elif area_sqm > 800.0:
                    category = "NEW_CONSTRUCTION"
                elif area_sqm > 300.0:
                    category = "EXPANSION"
                else:
                    category = "VEGETATION_LOSS"

                # Explainable risk assessment
                risk_score, risk_level, confidence, reasons = evaluate_risk_and_confidence(
                    category=category,
                    affected_area_sqm=area_sqm,
                    intersects_restricted=intersects_restricted,
                    restricted_zone_name=restricted_name,
                    proximity_meters=proximity_m,
                    observation_count=1,
                    trend="NEW",
                    cloud_coverage_percentage=recent_scene.cloud_coverage_percentage,
                    parcel_owner_type=owner_type
                )

                change = DetectedChange(
                    job_id=job.id,
                    zone_id=zone.id,
                    parcel_id=parcel_id,
                    category=category,
                    confidence_score=confidence,
                    risk_score=risk_score,
                    risk_level=risk_level,
                    affected_area_sqm=round(area_sqm, 2),
                    affected_area_hectares=area_ha,
                    centroid_lat=centroid_lat,
                    centroid_lng=centroid_lng,
                    geojson=geojson_poly,
                    intersects_restricted=intersects_restricted,
                    restricted_zone_name=restricted_name,
                    risk_reasons=reasons,
                    first_observed_date=hist_scene.acquisition_date,
                    latest_observed_date=recent_scene.acquisition_date,
                    observation_count=1,
                    trend="NEW",
                    created_at=datetime.utcnow()
                )
                db.add(change)
                db.flush()

                # Record temporal observation
                track_temporal_evolution(
                    db=db,
                    change=change,
                    new_area_sqm=area_sqm,
                    observation_date=recent_scene.acquisition_date,
                    risk_score=risk_score,
                    confidence_score=confidence,
                    image_url=recent_scene.image_url,
                    scene_id=recent_scene.id
                )

                # Generate or deduplicate alert
                generate_or_update_alert(
                    db=db,
                    change=change,
                    zone=zone,
                    historical_image_url=hist_scene.image_url,
                    recent_image_url=recent_scene.image_url,
                    change_mask_url=mask_url
                )

                detected_changes.append(change)

            job.progress = 100
            job.status = "COMPLETED"
            job.completed_at = datetime.utcnow()
            db.commit()

            return detected_changes

        except Exception as e:
            db.rollback()
            job.status = "FAILED"
            job.error_message = str(e)
            db.commit()
            print(f"Pipeline error: {e}")
            raise e

change_detection_service = ChangeDetectionService()
