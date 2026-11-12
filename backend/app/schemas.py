from pydantic import BaseModel, EmailStr, Field, model_validator
from typing import Optional, List, Any
from datetime import datetime

# --- Auth & User Schemas ---
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserBase(BaseModel):
    email: EmailStr
    full_name: str
    role: str = "MONITORING_OFFICER"
    department: Optional[str] = None
    badge_number: Optional[str] = None
    is_active: bool = True

class UserCreate(UserBase):
    password: str

class UserResponse(UserBase):
    id: int
    created_at: datetime
    class Config:
        from_attributes = True

class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


# --- Spatial & Zone Schemas ---
class LandParcelSchema(BaseModel):
    id: int
    zone_id: int
    parcel_number: str
    owner_type: str
    authorized_use: str
    area_sqm: float
    area_hectares: float
    geojson: Optional[Any] = None
    class Config:
        from_attributes = True

class RestrictedBoundarySchema(BaseModel):
    id: int
    name: str
    zone_id: Optional[int] = None
    boundary_type: str
    buffer_distance_meters: float
    geojson: Optional[Any] = None
    description: Optional[str] = None
    class Config:
        from_attributes = True

class MonitoringZoneCreate(BaseModel):
    name: str
    district: str
    state: str = "Karnataka"
    description: Optional[str] = None
    area_hectares: float = 0.0
    geojson: Optional[Any] = None

class MonitoringZoneUpdate(BaseModel):
    name: Optional[str] = None
    district: Optional[str] = None
    state: Optional[str] = None
    description: Optional[str] = None
    area_hectares: Optional[float] = None
    geojson: Optional[Any] = None

class MonitoringZoneResponse(BaseModel):
    id: int
    name: str
    district: str
    state: str
    description: Optional[str] = None
    area_hectares: float
    geojson: Optional[Any] = None
    risk_status: str
    parcels_count: Optional[int] = 0
    alerts_count: Optional[int] = 0
    created_at: datetime
    class Config:
        from_attributes = True


# --- Satellite Imagery Schemas ---
class SatelliteSceneSchema(BaseModel):
    id: int
    title: str
    provider: str
    acquisition_date: str
    cloud_coverage_percentage: float
    resolution_meters: float
    image_url: str
    thumbnail_url: Optional[str] = None
    zone_id: Optional[int] = None
    metadata_json: Optional[Any] = None
    created_at: datetime
    class Config:
        from_attributes = True


class SatelliteImageMetadata(BaseModel):
    date: Optional[str] = None
    cloud_coverage_percentage: Optional[float] = None
    satellite: str = "Sentinel-2"
    dataset: str = "COPERNICUS/S2_SR_HARMONIZED"
    image_url: Optional[str] = None
    geotiff_url: Optional[str] = None
    raster_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    width: int
    height: int
    resolution_meters: int
    crs: str = "EPSG:4326"
    transform: Optional[List[float]] = None
    raster_width: Optional[int] = None
    raster_height: Optional[int] = None
    nodata: Optional[float] = None
    valid_pixel_count: Optional[int] = None
    zone_pixel_count: Optional[int] = None
    valid_pixel_coverage_percentage: Optional[float] = None
    extent: Optional[Any] = None
    available: bool = False
    cached: bool = False
    processing_status: str


class SatellitePreviewRequest(BaseModel):
    zone_id: Optional[int] = None
    geometry: Optional[Any] = None
    start_date: str
    end_date: str
    max_cloud_coverage: float = 30.0
    width: int = 512
    height: int = 512
    resolution_meters: int = 10


class SatellitePreviewResponse(BaseModel):
    status: str
    source: str = "Google Earth Engine"
    dataset: str = "COPERNICUS/S2_SR_HARMONIZED"
    imagery: SatelliteImageMetadata
    disclaimer: str = "Acquired through Google Earth Engine. Visual change does not establish encroachment."


class SatelliteCompareRequest(BaseModel):
    zone_id: Optional[int] = None
    geometry: Optional[Any] = None
    historical_start_date: str
    historical_end_date: str
    recent_start_date: str
    recent_end_date: str
    max_cloud_coverage: float = 30.0
    width: int = 512
    height: int = 512
    resolution_meters: int = 10

    @model_validator(mode="after")
    def validate_temporal_order(self):
        try:
            historical_start = datetime.strptime(self.historical_start_date, "%Y-%m-%d").date()
            historical_end = datetime.strptime(self.historical_end_date, "%Y-%m-%d").date()
            recent_start = datetime.strptime(self.recent_start_date, "%Y-%m-%d").date()
            recent_end = datetime.strptime(self.recent_end_date, "%Y-%m-%d").date()
        except (TypeError, ValueError) as exc:
            raise ValueError("All acquisition dates must use ISO YYYY-MM-DD format.") from exc
        if historical_start > historical_end:
            raise ValueError("Historical start date must be on or before its end date.")
        if recent_start > recent_end:
            raise ValueError("Recent start date must be on or before its end date.")
        if recent_start <= historical_end:
            raise ValueError("Recent acquisition range must start after the historical range ends.")
        return self


class SatelliteCompareResponse(BaseModel):
    status: str
    source: str = "Google Earth Engine"
    dataset: str = "COPERNICUS/S2_SR_HARMONIZED"
    historical: SatelliteImageMetadata
    recent: SatelliteImageMetadata
    historical_scene_id: Optional[int] = None
    recent_scene_id: Optional[int] = None
    zone_id: Optional[int] = None
    disclaimer: str = "Acquired through Google Earth Engine. Visual change does not establish encroachment."


# --- Detection & Changes Schemas ---
class DetectionJobCreate(BaseModel):
    zone_id: int
    historical_scene_id: int
    recent_scene_id: int
    algorithm: str = "SPECTRAL_NDVI_NDBI_DIFFERENCING"
    parameters: Optional[Any] = None

class TemporalObservationSchema(BaseModel):
    id: int
    change_id: int
    observation_date: str
    area_sqm: float
    risk_score: float
    confidence_score: float
    image_url: Optional[str] = None
    scene_id: Optional[int] = None
    class Config:
        from_attributes = True

class DetectedChangeSchema(BaseModel):
    id: int
    job_id: Optional[int] = None
    zone_id: int
    parcel_id: Optional[int] = None
    category: str
    confidence_score: float
    model_mean_probability: Optional[float] = None
    model_max_probability: Optional[float] = None
    risk_score: float
    risk_level: str
    affected_area_sqm: float
    affected_area_hectares: float
    centroid_lat: float
    centroid_lng: float
    geojson: Optional[Any] = None
    intersects_restricted: bool
    restricted_zone_name: Optional[str] = None
    risk_reasons: Optional[List[str]] = None
    first_observed_date: str
    latest_observed_date: str
    observation_count: int
    trend: str
    created_at: datetime
    class Config:
        from_attributes = True

class DetectionJobResponse(BaseModel):
    id: int
    job_code: str
    zone_id: int
    historical_scene_id: int
    recent_scene_id: int
    algorithm: str
    status: str
    progress: int
    parameters: Optional[Any] = None
    error_message: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    changes_count: Optional[int] = 0
    class Config:
        from_attributes = True

# --- LEVIR-CD+ Building Prediction Schemas ---
class LevirPredictionRequest(BaseModel):
    earlier_scene_id: Optional[int] = None
    later_scene_id: Optional[int] = None
    earlier_image_path: Optional[str] = None
    later_image_path: Optional[str] = None
    threshold: Optional[float] = Field(default=0.7, ge=0.0, le=1.0)
    zone_id: Optional[int] = None
    parcel_id: Optional[int] = None
    generate_alert: Optional[bool] = False

class LevirPredictionResponse(BaseModel):
    model_name: str
    model_type: str
    feature_schema: str
    threshold: float
    dimensions: Any
    total_pixels: int
    changed_pixels: int
    changed_pixel_percentage: float
    mean_probability: float
    max_probability: float
    min_probability: float
    mask_url: str
    overlay_url: str
    earlier_image_url: Optional[str] = None
    later_image_url: Optional[str] = None
    candidate_alert_id: Optional[int] = None
    candidate_alert_code: Optional[str] = None
    disclaimer: str

# --- EXP-02 SNUNet-CD Prediction Schemas ---
class SNUNetPredictionResponse(BaseModel):
    model_name: str
    model_type: str
    architecture: str
    checkpoint_path: str
    epoch: Optional[int] = None
    threshold: float
    normalization: dict
    patch_size: int
    dimensions: dict
    total_pixels: int
    changed_pixels: int
    changed_pixel_percentage: float
    mean_probability: float
    max_probability: float
    min_probability: float
    probability_url: str
    mask_url: str
    overlay_url: str
    earlier_image_url: str
    later_image_url: str
    disclaimer: str

# --- Alert Schemas ---
class AlertNoteCreate(BaseModel):
    note: str

class AlertNoteResponse(BaseModel):
    id: int
    alert_id: int
    user_id: int
    user_name: str
    user_role: str
    note: str
    created_at: datetime
    class Config:
        from_attributes = True

class AlertEvidenceResponse(BaseModel):
    id: int
    alert_id: int
    file_url: str
    file_type: str
    caption: Optional[str] = None
    uploaded_by_name: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    created_at: datetime
    class Config:
        from_attributes = True

class AlertStatusUpdate(BaseModel):
    status: str
    dismissal_reason: Optional[str] = None
    resolution_details: Optional[str] = None

class AlertAssignRequest(BaseModel):
    assigned_to_id: int

class AlertResponse(BaseModel):
    id: int
    alert_code: str
    change_id: int
    zone_id: int
    zone_name: Optional[str] = None
    district: Optional[str] = None
    parcel_id: Optional[int] = None
    parcel_number: Optional[str] = None
    category: str
    risk_level: str
    risk_score: float
    confidence_score: float
    affected_area_sqm: float
    affected_area_hectares: float
    centroid_lat: float
    centroid_lng: float
    geojson: Optional[Any] = None
    historical_image_url: Optional[str] = None
    recent_image_url: Optional[str] = None
    change_mask_url: Optional[str] = None
    status: str
    first_observed_date: str
    latest_observed_date: str
    assigned_to_id: Optional[int] = None
    assigned_to_name: Optional[str] = None
    dismissal_reason: Optional[str] = None
    resolution_details: Optional[str] = None
    risk_reasons: Optional[List[str]] = None
    notes: Optional[List[AlertNoteResponse]] = []
    evidence: Optional[List[AlertEvidenceResponse]] = []
    temporal_history: Optional[List[TemporalObservationSchema]] = []
    created_at: datetime
    updated_at: datetime
    class Config:
        from_attributes = True


# --- Dashboard Stats Schemas ---
class DashboardStats(BaseModel):
    monitored_parcels: int
    monitored_zones: Optional[int] = 0
    total_area_hectares: float
    new_changes_detected: int
    actual_changed_area_ha: Optional[float] = 0.0
    actual_changed_area_sqm: Optional[float] = 0.0
    pending_alerts: int
    high_risk_alerts: int
    awaiting_inspection: int
    confirmed_encroachments: int
    changes_last_30_days: int
    is_demo_mode: bool
    latest_imagery_date: str
    last_analysis_timestamp: str
    data_source: str


# --- Notification Schemas ---
class NotificationResponse(BaseModel):
    id: int
    title: str
    message: str
    type: str
    alert_id: Optional[int] = None
    is_read: bool
    created_at: datetime
    class Config:
        from_attributes = True


# --- Audit & System Schemas ---
class AuditLogResponse(BaseModel):
    id: int
    user_email: str
    action: str
    resource_type: str
    resource_id: Optional[str] = None
    details: Optional[str] = None
    timestamp: datetime
    class Config:
        from_attributes = True

class SystemSettingsSchema(BaseModel):
    detection_threshold_ndvi: float = 0.25
    detection_threshold_ndbi: float = 0.20
    min_change_area_sqm: float = 150.0
    risk_weight_boundary: float = 40.0
    risk_weight_area: float = 30.0
    risk_weight_persistence: float = 30.0
    auto_alert_high_risk: bool = True
    copernicus_enabled: bool = False
    demo_mode: bool = True
