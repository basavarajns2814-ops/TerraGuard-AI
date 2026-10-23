from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False, default="MONITORING_OFFICER") # ADMIN, MONITORING_OFFICER, FIELD_INSPECTOR
    department = Column(String(255), nullable=True)
    badge_number = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    assigned_alerts = relationship("Alert", back_populates="assigned_to")
    notes = relationship("AlertNote", back_populates="user")
    notifications = relationship("Notification", back_populates="user")


class MonitoringZone(Base):
    __tablename__ = "monitoring_zones"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    district = Column(String(255), nullable=False, index=True)
    state = Column(String(255), nullable=False, default="Karnataka")
    description = Column(Text, nullable=True)
    area_hectares = Column(Float, default=0.0)
    geojson = Column(JSON, nullable=True)
    risk_status = Column(String(50), default="NORMAL") # NORMAL, ELEVATED, CRITICAL
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    parcels = relationship("LandParcel", back_populates="zone", cascade="all, delete-orphan")
    restricted_boundaries = relationship("RestrictedBoundary", back_populates="zone", cascade="all, delete-orphan")
    scenes = relationship("SatelliteScene", back_populates="zone")
    changes = relationship("DetectedChange", back_populates="zone")
    alerts = relationship("Alert", back_populates="zone")


class LandParcel(Base):
    __tablename__ = "land_parcels"

    id = Column(Integer, primary_key=True, index=True)
    zone_id = Column(Integer, ForeignKey("monitoring_zones.id"), nullable=False, index=True)
    parcel_number = Column(String(100), nullable=False, index=True)
    owner_type = Column(String(50), nullable=False, default="GOVERNMENT") # GOVERNMENT, PUBLIC_RESERVE, PRIVATE, WATER_BODY, FOREST
    authorized_use = Column(String(255), nullable=False, default="Protected Catchment / Reserve")
    area_sqm = Column(Float, default=0.0)
    area_hectares = Column(Float, default=0.0)
    geojson = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    zone = relationship("MonitoringZone", back_populates="parcels")
    changes = relationship("DetectedChange", back_populates="parcel")
    alerts = relationship("Alert", back_populates="parcel")


class RestrictedBoundary(Base):
    __tablename__ = "restricted_boundaries"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    zone_id = Column(Integer, ForeignKey("monitoring_zones.id"), nullable=True, index=True)
    boundary_type = Column(String(50), nullable=False, default="LAKE_BUFFER") # LAKE_BUFFER, FOREST_RESERVE, HIGHWAY_ROW, GOVERNMENT_LAYOUT
    buffer_distance_meters = Column(Float, default=30.0)
    geojson = Column(JSON, nullable=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    zone = relationship("MonitoringZone", back_populates="restricted_boundaries")


class SatelliteScene(Base):
    __tablename__ = "satellite_scenes"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    provider = Column(String(50), nullable=False, default="SENTINEL_2") # SENTINEL_2, SENTINEL_1, LANDSAT_8, LOCAL_UPLOAD
    acquisition_date = Column(String(50), nullable=False, index=True)
    cloud_coverage_percentage = Column(Float, default=0.0)
    resolution_meters = Column(Float, default=10.0)
    image_path = Column(String(500), nullable=False)
    image_url = Column(String(500), nullable=False)
    thumbnail_url = Column(String(500), nullable=True)
    zone_id = Column(Integer, ForeignKey("monitoring_zones.id"), nullable=True, index=True)
    metadata_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    zone = relationship("MonitoringZone", back_populates="scenes")


class DetectionJob(Base):
    __tablename__ = "detection_jobs"

    id = Column(Integer, primary_key=True, index=True)
    job_code = Column(String(100), unique=True, index=True, nullable=False)
    zone_id = Column(Integer, ForeignKey("monitoring_zones.id"), nullable=False)
    historical_scene_id = Column(Integer, ForeignKey("satellite_scenes.id"), nullable=False)
    recent_scene_id = Column(Integer, ForeignKey("satellite_scenes.id"), nullable=False)
    algorithm = Column(String(100), default="SPECTRAL_NDVI_NDBI_DIFFERENCING")
    status = Column(String(50), default="PENDING") # PENDING, RUNNING, COMPLETED, FAILED
    progress = Column(Integer, default=0) # 0 - 100
    parameters = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    changes = relationship("DetectedChange", back_populates="job")


class DetectedChange(Base):
    __tablename__ = "detected_changes"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("detection_jobs.id"), nullable=True, index=True)
    zone_id = Column(Integer, ForeignKey("monitoring_zones.id"), nullable=False, index=True)
    parcel_id = Column(Integer, ForeignKey("land_parcels.id"), nullable=True, index=True)
    category = Column(String(50), nullable=False, default="NEW_CONSTRUCTION")
    confidence_score = Column(Float, default=0.85) # 0.0 - 1.0
    risk_score = Column(Float, default=75.0) # 0 - 100
    risk_level = Column(String(20), default="HIGH") # LOW, MEDIUM, HIGH, CRITICAL
    affected_area_sqm = Column(Float, default=0.0)
    affected_area_hectares = Column(Float, default=0.0)
    centroid_lat = Column(Float, nullable=False)
    centroid_lng = Column(Float, nullable=False)
    geojson = Column(JSON, nullable=True)
    intersects_restricted = Column(Boolean, default=False)
    restricted_zone_name = Column(String(255), nullable=True)
    risk_reasons = Column(JSON, nullable=True) # list of reasons
    first_observed_date = Column(String(50), nullable=False)
    latest_observed_date = Column(String(50), nullable=False)
    observation_count = Column(Integer, default=1)
    trend = Column(String(50), default="NEW") # NEW, EXPANDING, STABLE, DISAPPEARING
    created_at = Column(DateTime, default=datetime.utcnow)

    job = relationship("DetectionJob", back_populates="changes")
    zone = relationship("MonitoringZone", back_populates="changes")
    parcel = relationship("LandParcel", back_populates="changes")
    alert = relationship("Alert", back_populates="change", uselist=False)
    observations = relationship("TemporalObservation", back_populates="change", cascade="all, delete-orphan")


class TemporalObservation(Base):
    __tablename__ = "temporal_observations"

    id = Column(Integer, primary_key=True, index=True)
    change_id = Column(Integer, ForeignKey("detected_changes.id"), nullable=False, index=True)
    observation_date = Column(String(50), nullable=False)
    area_sqm = Column(Float, default=0.0)
    risk_score = Column(Float, default=0.0)
    confidence_score = Column(Float, default=0.0)
    image_url = Column(String(500), nullable=True)
    scene_id = Column(Integer, ForeignKey("satellite_scenes.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    change = relationship("DetectedChange", back_populates="observations")


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    alert_code = Column(String(100), unique=True, index=True, nullable=False)
    change_id = Column(Integer, ForeignKey("detected_changes.id"), nullable=False, unique=True, index=True)
    zone_id = Column(Integer, ForeignKey("monitoring_zones.id"), nullable=False, index=True)
    parcel_id = Column(Integer, ForeignKey("land_parcels.id"), nullable=True, index=True)
    category = Column(String(50), nullable=False, default="NEW_CONSTRUCTION")
    risk_level = Column(String(20), default="HIGH") # LOW, MEDIUM, HIGH, CRITICAL
    risk_score = Column(Float, default=75.0)
    confidence_score = Column(Float, default=0.85)
    affected_area_sqm = Column(Float, default=0.0)
    affected_area_hectares = Column(Float, default=0.0)
    centroid_lat = Column(Float, nullable=False)
    centroid_lng = Column(Float, nullable=False)
    geojson = Column(JSON, nullable=True)
    historical_image_url = Column(String(500), nullable=True)
    recent_image_url = Column(String(500), nullable=True)
    change_mask_url = Column(String(500), nullable=True)
    status = Column(String(50), default="NEW") # NEW, UNDER_REVIEW, FIELD_INSPECTION_REQUIRED, CONFIRMED, DISMISSED, RESOLVED
    first_observed_date = Column(String(50), nullable=False)
    latest_observed_date = Column(String(50), nullable=False)
    assigned_to_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    dismissal_reason = Column(Text, nullable=True)
    resolution_details = Column(Text, nullable=True)
    risk_reasons = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    change = relationship("DetectedChange", back_populates="alert")
    zone = relationship("MonitoringZone", back_populates="alerts")
    parcel = relationship("LandParcel", back_populates="alerts")
    assigned_to = relationship("User", back_populates="assigned_alerts")
    notes = relationship("AlertNote", back_populates="alert", cascade="all, delete-orphan", order_by="AlertNote.created_at.desc()")
    evidence = relationship("AlertEvidence", back_populates="alert", cascade="all, delete-orphan", order_by="AlertEvidence.created_at.desc()")


class AlertNote(Base):
    __tablename__ = "alert_notes"

    id = Column(Integer, primary_key=True, index=True)
    alert_id = Column(Integer, ForeignKey("alerts.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user_name = Column(String(255), nullable=False)
    user_role = Column(String(50), nullable=False)
    note = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    alert = relationship("Alert", back_populates="notes")
    user = relationship("User", back_populates="notes")


class AlertEvidence(Base):
    __tablename__ = "alert_evidence"

    id = Column(Integer, primary_key=True, index=True)
    alert_id = Column(Integer, ForeignKey("alerts.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    file_path = Column(String(500), nullable=False)
    file_url = Column(String(500), nullable=False)
    file_type = Column(String(50), nullable=False, default="image/jpeg")
    caption = Column(String(500), nullable=True)
    uploaded_by_name = Column(String(255), nullable=False)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    alert = relationship("Alert", back_populates="evidence")


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    type = Column(String(50), default="ALERT_HIGH") # ALERT_HIGH, STATUS_CHANGE, SYSTEM, INSPECTION
    alert_id = Column(Integer, nullable=True)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="notifications")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_email = Column(String(255), nullable=False, index=True)
    action = Column(String(100), nullable=False)
    resource_type = Column(String(100), nullable=False)
    resource_id = Column(String(100), nullable=True)
    details = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)


class SystemSetting(Base):
    __tablename__ = "system_settings"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), unique=True, index=True, nullable=False)
    value = Column(String(500), nullable=False)
    description = Column(String(500), nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
