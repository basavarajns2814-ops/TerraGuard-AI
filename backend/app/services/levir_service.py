import sys
import os
import uuid
from pathlib import Path
from typing import Dict, Any, Tuple, Optional, List
import numpy as np
from PIL import Image
from sqlalchemy.orm import Session
from datetime import datetime

# Ensure backend root is in sys.path
backend_root = Path(__file__).resolve().parent.parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from app.config import settings
from app.models import (
    Alert, DetectedChange, MonitoringZone, LandParcel,
    RestrictedBoundary, SatelliteScene, TemporalObservation
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
from app.services.change_detection.morphological import (
    morphological_clean,
    extract_connected_components,
    component_to_geojson_polygon
)

from ml.levir_model import load_classifier, predict_probability, FEATURE_SCHEMA
from src.change_detection import make_overlay

class LevirModelService:
    def __init__(self, model_path: Optional[str] = None):
        if model_path is None:
            model_path = os.path.join(str(backend_root), "models", "levir_change_model.joblib")
        self.model_path = model_path
        self._artifact: Optional[Dict[str, Any]] = None

    @property
    def artifact(self) -> Dict[str, Any]:
        if self._artifact is None:
            if not os.path.exists(self.model_path):
                raise FileNotFoundError(f"Trained LEVIR-CD+ model artifact not found at {self.model_path}")
            self._artifact = load_classifier(self.model_path)
        return self._artifact

    def validate_image_pair(
        self,
        earlier_path: str,
        later_path: str
    ) -> Tuple[np.ndarray, np.ndarray, int, int]:
        """
        Validates that both images exist, can be decoded, have 3 color channels,
        and share identical spatial dimensions.
        """
        if not os.path.exists(earlier_path):
            raise FileNotFoundError(f"Earlier satellite image not found at: {earlier_path}")
        if not os.path.exists(later_path):
            raise FileNotFoundError(f"Later satellite image not found at: {later_path}")

        try:
            earlier_pil = Image.open(earlier_path).convert('RGB')
        except Exception as e:
            raise ValueError(f"Unable to decode earlier image: {e}")

        try:
            later_pil = Image.open(later_path).convert('RGB')
        except Exception as e:
            raise ValueError(f"Unable to decode later image: {e}")

        # Check dimension compatibility
        w1, h1 = earlier_pil.size
        w2, h2 = later_pil.size

        if (w1, h1) != (w2, h2):
            raise ValueError(
                f"Image dimension mismatch: earlier image is {w1}x{h1}, later image is {w2}x{h2}. "
                f"Registered images of identical dimensions are required for LEVIR-CD+ pixel classification."
            )

        earlier_np = np.array(earlier_pil, dtype=np.uint8)
        later_np = np.array(later_pil, dtype=np.uint8)

        return earlier_np, later_np, w1, h1

    def run_prediction(
        self,
        earlier_path: str,
        later_path: str,
        threshold: float = 0.7
    ) -> Dict[str, Any]:
        """
        Executes LEVIR-CD+ HistGradientBoosting prediction and saves change mask and visualization overlay.
        """
        if not 0.0 <= float(threshold) <= 1.0:
            raise ValueError("Prediction threshold must be between 0 and 1.")
        earlier_np, later_np, width, height = self.validate_image_pair(earlier_path, later_path)

        # Predict probability map using original feature extraction
        probabilities = predict_probability(self.artifact, earlier_np, later_np)
        mask_bool = probabilities >= float(threshold)
        mask_uint8 = (mask_bool.astype(np.uint8)) * 255

        total_pixels = width * height
        changed_pixels = int(np.count_nonzero(mask_bool))
        changed_pixel_percentage = round((changed_pixels / total_pixels) * 100.0, 3) if total_pixels else 0.0

        # Create red-tinted overlay visualization on the later image
        overlay_np = make_overlay(later_np, mask_bool)

        # Save artifacts to storage
        mask_dir = os.path.join(settings.STORAGE_DIR, "masks")
        os.makedirs(mask_dir, exist_ok=True)

        token = uuid.uuid4().hex[:10]
        mask_filename = f"levir_mask_{token}.png"
        overlay_filename = f"levir_overlay_{token}.png"

        mask_file_path = os.path.join(mask_dir, mask_filename)
        overlay_file_path = os.path.join(mask_dir, overlay_filename)

        Image.fromarray(mask_uint8).save(mask_file_path)
        Image.fromarray(overlay_np).save(overlay_file_path)

        mask_url = f"/storage/masks/{mask_filename}"
        overlay_url = f"/storage/masks/{overlay_filename}"

        return {
            "model_name": "LEVIR-CD+ HistGradientBoosting Building Classifier",
            "model_type": "HistGradientBoostingClassifier",
            "feature_schema": FEATURE_SCHEMA,
            "threshold": float(threshold),
            "dimensions": {
                "width": width,
                "height": height,
                "channels": 3
            },
            "total_pixels": total_pixels,
            "changed_pixels": changed_pixels,
            "changed_pixel_percentage": changed_pixel_percentage,
            "mean_probability": round(float(probabilities.mean()), 4),
            "max_probability": round(float(probabilities.max()), 4),
            "min_probability": round(float(probabilities.min()), 4),
            "mask_url": mask_url,
            "overlay_url": overlay_url,
            "mask_uint8": mask_uint8,
            "mask_bool": mask_bool,
            "probabilities": probabilities,
            "disclaimer": "Potential building changes detected using LEVIR-CD+ model. Requires human field verification; does not constitute legal proof of encroachment."
        }

    def generate_potential_change_alert(
        self,
        db: Session,
        prediction_result: Dict[str, Any],
        zone_id: int,
        historical_scene: SatelliteScene,
        recent_scene: SatelliteScene,
        parcel_id: Optional[int] = None
    ) -> Optional[Alert]:
        """
        Generates or updates a potential-change alert from the LEVIR-CD+ prediction results.
        Deduplicates against existing active alerts.
        """
        zone = db.query(MonitoringZone).filter(MonitoringZone.id == zone_id).first()
        if not zone:
            return None

        clean_mask = morphological_clean(prediction_result["mask_uint8"])
        components = extract_connected_components(clean_mask, min_pixels=20)
        if not components:
            return None

        # Determine bounding box
        bbox_geo = (77.6600, 12.9200, 77.6850, 12.9450)
        if zone.geojson and "coordinates" in zone.geojson:
            try:
                coords = zone.geojson["coordinates"][0]
                lngs = [c[0] for c in coords]
                lats = [c[1] for c in coords]
                bbox_geo = (min(lngs), min(lats), max(lngs), max(lats))
            except Exception:
                pass

        parcels = db.query(LandParcel).filter(LandParcel.zone_id == zone.id).all()
        restricted_boundaries = db.query(RestrictedBoundary).filter(
            (RestrictedBoundary.zone_id == zone.id) | (RestrictedBoundary.zone_id == None)
        ).all()

        # Extract top component
        top_comp = components[0]
        geojson_poly = component_to_geojson_polygon(
            top_comp,
            prediction_result["dimensions"]["width"],
            prediction_result["dimensions"]["height"],
            bbox_geo
        )
        area_sqm = calculate_polygon_area_sqm(geojson_poly)
        area_ha = sqm_to_hectares(area_sqm)
        centroid_lat, centroid_lng = get_centroid_lat_lng(geojson_poly)

        # Match parcel
        matched_parcel = find_containing_parcel(geojson_poly, parcels)
        matched_parcel_id = matched_parcel.id if matched_parcel else parcel_id
        owner_type = matched_parcel.owner_type if matched_parcel else "GOVERNMENT"

        # Check restricted boundaries
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

        risk_score, risk_level, confidence, reasons = evaluate_risk_and_confidence(
            category="NEW_CONSTRUCTION",
            affected_area_sqm=area_sqm,
            intersects_restricted=intersects_restricted,
            restricted_zone_name=restricted_name,
            proximity_meters=proximity_m,
            observation_count=1,
            trend="NEW",
            cloud_coverage_percentage=recent_scene.cloud_coverage_percentage if recent_scene else 0.0,
            parcel_owner_type=owner_type
        )

        # Prefix reason with model provenance
        reasons.insert(0, f"LEVIR-CD+ model identified {prediction_result['changed_pixel_percentage']}% building-change pixels (threshold: {prediction_result['threshold']})")
        reasons.append("Status: Potential building change requiring human field verification.")

        # Check for existing alert in proximity/same parcel to avoid duplicates
        existing_alert = None
        if matched_parcel_id:
            existing_alert = db.query(Alert).filter(
                Alert.zone_id == zone.id,
                Alert.parcel_id == matched_parcel_id,
                Alert.category == "NEW_CONSTRUCTION"
            ).first()

        if existing_alert:
            existing_alert.latest_observed_date = recent_scene.acquisition_date if recent_scene else datetime.utcnow().strftime("%Y-%m-%d")
            existing_alert.risk_score = risk_score
            existing_alert.risk_level = risk_level
            existing_alert.affected_area_sqm = round(area_sqm, 2)
            existing_alert.affected_area_hectares = area_ha
            existing_alert.risk_reasons = reasons
            existing_alert.change_mask_url = prediction_result["mask_url"]
            existing_alert.recent_image_url = recent_scene.image_url if recent_scene else existing_alert.recent_image_url
            existing_alert.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(existing_alert)
            return existing_alert

        change = DetectedChange(
            zone_id=zone.id,
            parcel_id=matched_parcel_id,
            category="NEW_CONSTRUCTION",
            confidence_score=prediction_result["max_probability"],
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
            first_observed_date=historical_scene.acquisition_date if historical_scene else "2025-10-15",
            latest_observed_date=recent_scene.acquisition_date if recent_scene else "2026-10-01",
            observation_count=1,
            trend="NEW",
            created_at=datetime.utcnow()
        )
        db.add(change)
        db.flush()

        alert = generate_or_update_alert(
            db=db,
            change=change,
            zone=zone,
            historical_image_url=historical_scene.image_url if historical_scene else None,
            recent_image_url=recent_scene.image_url if recent_scene else None,
            change_mask_url=prediction_result["mask_url"]
        )

        return alert

levir_model_service = LevirModelService()
