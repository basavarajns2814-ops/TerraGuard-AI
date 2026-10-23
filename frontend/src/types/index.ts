export type UserRole = 'ADMIN' | 'MONITORING_OFFICER' | 'FIELD_INSPECTOR';

export interface User {
  id: number;
  email: string;
  full_name: string;
  role: UserRole;
  is_active: boolean;
  department?: string;
  badge_number?: string;
  created_at: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface MonitoringZone {
  id: number;
  name: string;
  district: string;
  state: string;
  description?: string;
  area_hectares: number;
  geojson?: any;
  risk_status: 'NORMAL' | 'ELEVATED' | 'CRITICAL';
  parcels_count?: number;
  alerts_count?: number;
  created_at: string;
}

export interface LandParcel {
  id: number;
  zone_id: number;
  parcel_number: string;
  owner_type: 'GOVERNMENT' | 'PUBLIC_RESERVE' | 'PRIVATE' | 'WATER_BODY' | 'FOREST';
  authorized_use: string;
  area_sqm: number;
  area_hectares: number;
  geojson?: any;
}

export interface RestrictedBoundary {
  id: number;
  name: string;
  zone_id?: number;
  boundary_type: 'LAKE_BUFFER' | 'FOREST_RESERVE' | 'HIGHWAY_ROW' | 'GOVERNMENT_LAYOUT';
  buffer_distance_meters: number;
  geojson?: any;
  description?: string;
}

export interface SatelliteScene {
  id: number;
  title: string;
  provider: 'SENTINEL_2' | 'SENTINEL_1' | 'LANDSAT_8' | 'LOCAL_UPLOAD';
  acquisition_date: string;
  cloud_coverage_percentage: number;
  resolution_meters: number;
  image_url: string;
  thumbnail_url?: string;
  zone_id?: number;
  metadata_json?: any;
  created_at: string;
}

export interface DetectionJob {
  id: number;
  job_code: string;
  zone_id: number;
  historical_scene_id: number;
  recent_scene_id: number;
  algorithm: string;
  status: 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED';
  progress: number;
  parameters?: any;
  error_message?: string;
  changes_count?: number;
  created_at: string;
  completed_at?: string;
}

export type ChangeCategory =
  | 'NEW_CONSTRUCTION'
  | 'EXPANSION'
  | 'VEGETATION_LOSS'
  | 'WATER_BODY_ENCROACHMENT'
  | 'ROAD_BUFFER_VIOLATION'
  | 'AGRICULTURE_CONVERSION';

export type RiskLevel = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';

export interface DetectedChange {
  id: number;
  job_id: number;
  zone_id: number;
  parcel_id?: number;
  category: ChangeCategory;
  confidence_score: number; // 0.0 - 1.0
  risk_score: number; // 0 - 100
  risk_level: RiskLevel;
  affected_area_sqm: number;
  affected_area_hectares: number;
  centroid_lat: number;
  centroid_lng: number;
  geojson?: any;
  intersects_restricted: boolean;
  restricted_zone_name?: string;
  risk_reasons?: string[];
  first_observed_date: string;
  latest_observed_date: string;
  observation_count: number;
  trend: 'EXPANDING' | 'STABLE' | 'DISAPPEARING' | 'NEW';
}

export interface TemporalObservation {
  id: number;
  change_id: number;
  observation_date: string;
  area_sqm: number;
  risk_score: number;
  confidence_score: number;
  image_url?: string;
  scene_id?: number;
}

export type AlertStatus =
  | 'NEW'
  | 'UNDER_REVIEW'
  | 'FIELD_INSPECTION_REQUIRED'
  | 'CONFIRMED'
  | 'DISMISSED'
  | 'RESOLVED';

export interface AlertNote {
  id: number;
  alert_id: number;
  user_name: string;
  user_role: UserRole;
  note: string;
  created_at: string;
}

export interface AlertEvidence {
  id: number;
  alert_id: number;
  file_url: string;
  file_type: string;
  caption?: string;
  uploaded_by_name: string;
  latitude?: number;
  longitude?: number;
  created_at: string;
}

export interface Alert {
  id: number;
  alert_code: string; // e.g. TG-2026-0042
  change_id: number;
  zone_id: number;
  zone_name: string;
  district: string;
  parcel_id?: number;
  parcel_number?: string;
  category: ChangeCategory;
  risk_level: RiskLevel;
  risk_score: number;
  confidence_score: number;
  affected_area_sqm: number;
  affected_area_hectares: number;
  centroid_lat: number;
  centroid_lng: number;
  geojson?: any;
  historical_image_url?: string;
  recent_image_url?: string;
  change_mask_url?: string;
  status: AlertStatus;
  first_observed_date: string;
  latest_observed_date: string;
  assigned_to_id?: number;
  assigned_to_name?: string;
  dismissal_reason?: string;
  resolution_details?: string;
  risk_reasons?: string[];
  notes?: AlertNote[];
  evidence?: AlertEvidence[];
  temporal_history?: TemporalObservation[];
  created_at: string;
  updated_at: string;
}

export interface NotificationItem {
  id: number;
  title: string;
  message: string;
  type: 'ALERT_HIGH' | 'STATUS_CHANGE' | 'SYSTEM' | 'INSPECTION';
  alert_id?: number;
  is_read: boolean;
  created_at: string;
}

export interface DashboardStats {
  monitored_parcels: number;
  total_area_hectares: number;
  new_changes_detected: number;
  pending_alerts: number;
  high_risk_alerts: number;
  awaiting_inspection: number;
  confirmed_encroachments: number;
  changes_last_30_days: number;
  is_demo_mode: boolean;
  latest_imagery_date: string;
  last_analysis_timestamp: string;
  data_source: string;
}

export interface AuditLog {
  id: number;
  user_email: string;
  action: string;
  resource_type: string;
  resource_id?: string;
  details?: string;
  timestamp: string;
}

export interface SystemSettings {
  detection_threshold_ndvi: number;
  detection_threshold_ndbi: number;
  min_change_area_sqm: number;
  risk_weight_boundary: number;
  risk_weight_area: number;
  risk_weight_persistence: number;
  auto_alert_high_risk: boolean;
  copernicus_enabled: boolean;
  demo_mode: boolean;
}

export interface LevirPredictionRequest {
  earlier_scene_id?: number;
  later_scene_id?: number;
  earlier_image_path?: string;
  later_image_path?: string;
  threshold?: number;
  zone_id?: number;
  parcel_id?: number;
  generate_alert?: boolean;
}

export interface LevirPredictionResponse {
  model_name: string;
  model_type: string;
  feature_schema: string;
  threshold: number;
  dimensions: {
    width: number;
    height: number;
    channels: number;
  };
  total_pixels: number;
  changed_pixels: number;
  changed_pixel_percentage: number;
  mean_probability: number;
  max_probability: number;
  min_probability: number;
  mask_url: string;
  overlay_url: string;
  earlier_image_url?: string;
  later_image_url?: string;
  candidate_alert_id?: number;
  candidate_alert_code?: string;
  disclaimer: string;
}
