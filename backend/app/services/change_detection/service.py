import os
import uuid
import numpy as np
from PIL import Image
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from datetime import datetime

from app.config import settings
from app.models import (
    DetectionJob, DetectedChange, SatelliteScene, MonitoringZone,
    LandParcel, RestrictedBoundary
)
from app.services.change_detection.spectral import SpectralChangeDetection
from app.services.change_detection.deep_learning import DeepLearningSegmentationStrategy
from app.services.change_detection.levir_strategy import LevirCdChangeDetectionStrategy
from app.services.change_detection.morphological import morphological_clean
from app.services.geospatial_preprocessing import (
    align_geotiff_pair,
    geospatial_preprocessor,
)
from app.services.gis_change_analysis import gis_change_analysis_service
from app.services.temporal import track_temporal_evolution
from app.services.alert_service import generate_or_update_alert


class ChangeDetectionService:
    def __init__(self):
        dl_strategy = DeepLearningSegmentationStrategy()
        spectral_strategy = SpectralChangeDetection()
        levir_strategy = LevirCdChangeDetectionStrategy()

        self.strategies = {
            "SNUNET_CD": dl_strategy,
            "DEEP_LEARNING_SEGMENTATION": dl_strategy,
            "SPECTRAL_NDVI_NDBI_DIFFERENCING": spectral_strategy,
            "OPTICAL_DIFFERENCE": spectral_strategy,
            "LEVIR_CD_HIST_GRADIENT_BOOSTING": levir_strategy
        }

    @staticmethod
    def apply_valid_data_mask(binary_mask, probability_map, valid_mask):
        """Exclude pixels unsupported by both dates from vectorized change results."""
        valid_mask = np.asarray(valid_mask, dtype=bool)
        if binary_mask.shape[:2] != valid_mask.shape:
            raise ValueError("Valid-data mask dimensions must match the prediction mask.")
        masked_binary = np.where(valid_mask, binary_mask, 0).astype(binary_mask.dtype, copy=False)
        if probability_map is None:
            return masked_binary, None
        if probability_map.shape[:2] != valid_mask.shape:
            raise ValueError("Valid-data mask dimensions must match the probability map.")
        masked_probabilities = np.where(valid_mask, probability_map, 0).astype(
            probability_map.dtype, copy=False
        )
        return masked_binary, masked_probabilities

    @staticmethod
    def resolve_scene_raster_path(scene):
        """Resolve the private analysis GeoTIFF while retaining legacy image paths."""
        metadata = scene.metadata_json if isinstance(scene.metadata_json, dict) else {}
        raster_url = metadata.get("raster_url")
        if not raster_url:
            return scene.image_path
        relative = raster_url.removeprefix("/storage/").replace("/", os.sep)
        storage_root = os.path.abspath(settings.STORAGE_DIR)
        raster_path = os.path.abspath(os.path.join(storage_root, relative))
        if os.path.commonpath((storage_root, raster_path)) != storage_root:
            raise ValueError("Scene GeoTIFF path must remain inside configured storage.")
        return raster_path

    def run_detection_pipeline(
        self,
        db: Session,
        job_id: int
    ) -> List[DetectedChange]:
        """
        Executes end-to-end geospatial change detection pipeline for a given job:
        1. Loads multi-temporal satellite scenes.
        2. Applies geospatial alignment, extents checking, and reflectance scaling.
        3. Executes selected change detection algorithm (default: SNUNet-CD / Deep Learning).
        4. Extracts real vector change polygons and computes metric area in square meters and hectares.
        5. Performs spatial intersection against cadastral parcels and restricted buffers.
        6. Generates explainable potential encroachment alerts.
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

            # 1. Load satellite rasters
            job.progress = 25
            db.commit()

            # 2. Geospatial Preprocessing & Raster Grid Alignment
            job.progress = 35
            db.commit()

            hist_path = self.resolve_scene_raster_path(hist_scene)
            recent_path = self.resolve_scene_raster_path(recent_scene)
            hist_suffix = os.path.splitext(hist_path)[1].lower()
            recent_suffix = os.path.splitext(recent_path)[1].lower()
            if hist_suffix in {".tif", ".tiff"} and recent_suffix in {".tif", ".tiff"}:
                aligned = align_geotiff_pair(hist_path, recent_path)
            elif hist_suffix in {".tif", ".tiff"} or recent_suffix in {".tif", ".tiff"}:
                raise ValueError(
                    "Historical and recent scenes must both be GeoTIFFs or both be legacy image scenes."
                )
            else:
                # Existing uploaded/demo scenes remain supported. Newly acquired
                # Earth Engine scenes point image_path at the native GeoTIFF.
                hist_raw = np.asarray(Image.open(hist_path).convert("RGB"))
                recent_raw = np.asarray(Image.open(recent_path).convert("RGB"))
                aligned = geospatial_preprocessor.align_and_preprocess_pair(
                    historical_img=hist_raw,
                    recent_img=recent_raw,
                    geometry=zone.geojson if zone else None,
                    target_dimensions=(512, 512),
                )

            hist_np = aligned["historical_aligned"]
            recent_np = aligned["recent_aligned"]
            transform_info = aligned["transform"]
            valid_mask = aligned["valid_mask"]
            if zone and hist_suffix in {".tif", ".tiff"}:
                from affine import Affine
                from rasterio.features import geometry_mask
                from rasterio.warp import transform_geom

                projected_zone = transform_geom(
                    "EPSG:4326", aligned["crs"], zone.geojson, precision=9
                )
                inside_zone = geometry_mask(
                    [projected_zone],
                    out_shape=valid_mask.shape,
                    transform=Affine(*transform_info["affine"]),
                    invert=True,
                    all_touched=False,
                )
            else:
                inside_zone = np.ones(valid_mask.shape, dtype=bool)
            zone_pixel_count = int(np.count_nonzero(inside_zone))
            valid_pixel_count = int(np.count_nonzero(valid_mask & inside_zone))
            valid_pixel_coverage = round(
                100.0 * valid_pixel_count / zone_pixel_count, 2
            ) if zone_pixel_count else 0.0

            # 3. Model Inference (SNUNet-CD / Deep Learning)
            job.progress = 55
            db.commit()

            strategy_name = job.algorithm or "SNUNET_CD"
            strategy = self.strategies.get(strategy_name, self.strategies["SNUNET_CD"])

            params = job.parameters or {}
            inference_params = (
                {**params, "valid_data_mask": valid_mask}
                if hist_suffix in {".tif", ".tiff"}
                else params
            )
            raw_mask, metadata = strategy.detect(hist_np, recent_np, inference_params)
            probability_map = metadata.get("probability_map")
            raw_mask, probability_map = self.apply_valid_data_mask(
                raw_mask, probability_map, valid_mask
            )

            # 4. Morphological Cleaning & Artifact Generation
            job.progress = 70
            db.commit()

            clean_mask = morphological_clean(raw_mask)
            # Morphological dilation can grow candidates into masked/no-data pixels.
            clean_mask, probability_map = self.apply_valid_data_mask(
                clean_mask, probability_map, valid_mask
            )

            mask_dir = os.path.join(settings.STORAGE_DIR, "masks")
            os.makedirs(mask_dir, exist_ok=True)
            mask_filename = f"mask_{job.job_code}.png"
            mask_path = os.path.join(mask_dir, mask_filename)
            Image.fromarray(clean_mask).save(mask_path)
            mask_url = f"/storage/masks/{mask_filename}"

            # 5. Rigorous GIS Vector Extraction & Spatial Overlay
            job.progress = 85
            db.commit()

            parcels = db.query(LandParcel).filter(LandParcel.zone_id == zone.id).all() if zone else []
            restricted_boundaries = db.query(RestrictedBoundary).filter(
                (RestrictedBoundary.zone_id == zone.id) | (RestrictedBoundary.zone_id == None)
            ).all() if zone else []

            analysis_result = gis_change_analysis_service.extract_change_regions(
                binary_mask=clean_mask,
                probability_map=probability_map,
                transform_info=transform_info,
                zone_geojson=zone.geojson if zone else None,
                min_area_sqm=params.get("min_area_sqm", 40.0),
                min_pixels=params.get("min_pixels", params.get("min_area_pixels", 15)),
                parcels=parcels,
                restricted_boundaries=restricted_boundaries,
                cloud_coverage_percentage=recent_scene.cloud_coverage_percentage or 0.0
            )

            detected_changes = []
            candidate_model_scores = []

            for reg in analysis_result["regions"]:
                change = DetectedChange(
                    job_id=job.id,
                    zone_id=zone.id if zone else 1,
                    parcel_id=reg["parcel_id"],
                    category=reg["category"],
                    confidence_score=reg["confidence_score"],
                    risk_score=reg["risk_score"],
                    risk_level=reg["risk_level"],
                    affected_area_sqm=reg["area_sqm"],
                    affected_area_hectares=reg["area_hectares"],
                    centroid_lat=reg["centroid_lat"],
                    centroid_lng=reg["centroid_lng"],
                    geojson=reg["geojson"],
                    intersects_restricted=reg["intersects_restricted"],
                    restricted_zone_name=reg["restricted_zone_name"],
                    risk_reasons=reg["risk_reasons"],
                    first_observed_date=hist_scene.acquisition_date,
                    latest_observed_date=recent_scene.acquisition_date,
                    observation_count=1,
                    trend="NEW",
                    created_at=datetime.utcnow()
                )
                db.add(change)
                db.flush()
                if probability_map is not None:
                    candidate_model_scores.append({
                        "change_id": change.id,
                        "mean_probability": reg.get("mean_probability"),
                        "max_probability": reg.get("max_probability"),
                    })

                # Temporal tracking
                track_temporal_evolution(
                    db=db,
                    change=change,
                    new_area_sqm=reg["area_sqm"],
                    observation_date=recent_scene.acquisition_date,
                    risk_score=reg["risk_score"],
                    confidence_score=reg["confidence_score"],
                    image_url=recent_scene.image_url,
                    scene_id=recent_scene.id
                )

                # Generate or update transparent investigation alert
                generate_or_update_alert(
                    db=db,
                    change=change,
                    zone=zone,
                    historical_image_url=hist_scene.image_url,
                    recent_image_url=recent_scene.image_url,
                    change_mask_url=mask_url
                )

                detected_changes.append(change)

            # Update job parameters with metadata
            job.parameters = {
                **(job.parameters or {}),
                "model_name": metadata.get("algorithm", "SNUNet-CD"),
                "architecture": metadata.get("model_architecture", "SNUNetCD"),
                "threshold": metadata.get("threshold", 0.3),
                "total_changed_sqm": analysis_result["total_changed_area_sqm"],
                "total_changed_hectares": analysis_result["total_changed_area_hectares"],
                "change_percentage": analysis_result["change_percentage_of_monitored_area"],
                "regions_detected": analysis_result["region_count"],
                "candidate_model_scores": candidate_model_scores,
                "imagery_source": "native_geotiff" if hist_suffix in {".tif", ".tiff"} else "legacy_image",
                "analysis_crs": aligned.get("crs", "EPSG:4326"),
                "analysis_dimensions": aligned.get("dimensions"),
                "valid_pixel_count": valid_pixel_count,
                "zone_pixel_count": zone_pixel_count,
                "valid_pixel_coverage_percentage": valid_pixel_coverage,
                "historical_acquisition_date": hist_scene.acquisition_date,
                "recent_acquisition_date": recent_scene.acquisition_date,
                "historical_image_url": hist_scene.image_url,
                "recent_image_url": recent_scene.image_url,
                "candidate_mask_url": mask_url,
                "model_confidence_summary": {
                    "mean_probability": round(float(probability_map[valid_mask].mean()), 4)
                    if probability_map is not None and valid_pixel_count else None,
                    "max_probability": round(float(probability_map[valid_mask].max()), 4)
                    if probability_map is not None and valid_pixel_count else None,
                },
            }

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
            print(f"Pipeline error for job {job_id}: {e}")
            raise e


change_detection_service = ChangeDetectionService()
