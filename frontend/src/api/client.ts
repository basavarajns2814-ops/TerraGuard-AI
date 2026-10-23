import {
  AuthResponse, User, DashboardStats, MonitoringZone,
  LandParcel, RestrictedBoundary, SatelliteScene, DetectionJob,
  DetectedChange, Alert, AlertStatus, NotificationItem, SystemSettings, AuditLog
} from '../types';
import type { LevirPredictionResponse } from '../types';

const API_BASE = '/api';

function getAuthHeaders(): HeadersInit {
  const token = localStorage.getItem('terraguard_token');
  return token ? { 'Authorization': `Bearer ${token}` } : {};
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    if (res.status === 401) {
      localStorage.removeItem('terraguard_token');
      localStorage.removeItem('terraguard_user');
      if (window.location.pathname !== '/login') {
        window.location.href = '/login';
      }
    }
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'An unexpected error occurred');
  }
  return res.json();
}

export const api = {
  // Auth
  async login(email: string, password: string): Promise<AuthResponse> {
    const res = await fetch(`${API_BASE}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password })
    });
    return handleResponse<AuthResponse>(res);
  },

  async getMe(): Promise<User> {
    const res = await fetch(`${API_BASE}/auth/me`, {
      headers: getAuthHeaders()
    });
    return handleResponse<User>(res);
  },

  // Dashboard
  async getDashboardStats(): Promise<DashboardStats> {
    const res = await fetch(`${API_BASE}/dashboard/stats`, {
      headers: getAuthHeaders()
    });
    return handleResponse<DashboardStats>(res);
  },

  async getDashboardTrends(): Promise<any> {
    const res = await fetch(`${API_BASE}/dashboard/trends`, {
      headers: getAuthHeaders()
    });
    return handleResponse<any>(res);
  },

  // Zones & Parcels
  async getZones(): Promise<MonitoringZone[]> {
    const res = await fetch(`${API_BASE}/zones`, {
      headers: getAuthHeaders()
    });
    return handleResponse<MonitoringZone[]>(res);
  },

  async createZone(data: Partial<MonitoringZone>): Promise<MonitoringZone> {
    const res = await fetch(`${API_BASE}/zones`, {
      method: 'POST',
      headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    return handleResponse<MonitoringZone>(res);
  },

  async getParcels(zoneId?: number): Promise<LandParcel[]> {
    const url = zoneId ? `${API_BASE}/zones/parcels/all?zone_id=${zoneId}` : `${API_BASE}/zones/parcels/all`;
    const res = await fetch(url, { headers: getAuthHeaders() });
    return handleResponse<LandParcel[]>(res);
  },

  async getRestrictedBoundaries(zoneId?: number): Promise<RestrictedBoundary[]> {
    const url = zoneId ? `${API_BASE}/zones/boundaries/all?zone_id=${zoneId}` : `${API_BASE}/zones/boundaries/all`;
    const res = await fetch(url, { headers: getAuthHeaders() });
    return handleResponse<RestrictedBoundary[]>(res);
  },

  // Imagery
  async getImagery(zoneId?: number): Promise<SatelliteScene[]> {
    const url = zoneId ? `${API_BASE}/imagery?zone_id=${zoneId}` : `${API_BASE}/imagery`;
    const res = await fetch(url, { headers: getAuthHeaders() });
    return handleResponse<SatelliteScene[]>(res);
  },

  async uploadImagery(formData: FormData): Promise<SatelliteScene> {
    const res = await fetch(`${API_BASE}/imagery/upload`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: formData
    });
    return handleResponse<SatelliteScene>(res);
  },

  async searchCopernicus(zoneId: number, startDate?: string, endDate?: string): Promise<any> {
    const params = new URLSearchParams({ zone_id: String(zoneId) });
    if (startDate) params.append('start_date', startDate);
    if (endDate) params.append('end_date', endDate);
    const res = await fetch(`${API_BASE}/imagery/provider/search?${params.toString()}`, {
      headers: getAuthHeaders()
    });
    return handleResponse<any>(res);
  },

  // Analysis
  async getJobs(): Promise<DetectionJob[]> {
    const res = await fetch(`${API_BASE}/analysis/jobs`, {
      headers: getAuthHeaders()
    });
    return handleResponse<DetectionJob[]>(res);
  },

  async runAnalysis(data: {
    zone_id: number;
    historical_scene_id: number;
    recent_scene_id: number;
    algorithm: string;
    parameters?: any;
  }): Promise<DetectionJob> {
    const res = await fetch(`${API_BASE}/analysis/run`, {
      method: 'POST',
      headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    return handleResponse<DetectionJob>(res);
  },

  async getChanges(filters?: { zone_id?: number; category?: string; risk_level?: string; trend?: string }): Promise<DetectedChange[]> {
    const params = new URLSearchParams();
    if (filters?.zone_id) params.append('zone_id', String(filters.zone_id));
    if (filters?.category) params.append('category', filters.category);
    if (filters?.risk_level) params.append('risk_level', filters.risk_level);
    if (filters?.trend) params.append('trend', filters.trend);

    const res = await fetch(`${API_BASE}/analysis/changes?${params.toString()}`, {
      headers: getAuthHeaders()
    });
    return handleResponse<DetectedChange[]>(res);
  },

  async predictLevirChange(data: {
    earlier_scene_id: number;
    later_scene_id: number;
    threshold?: number;
  }): Promise<LevirPredictionResponse> {
    const res = await fetch(`${API_BASE}/analysis/levir/predict`, {
      method: 'POST',
      headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    return handleResponse<LevirPredictionResponse>(res);
  },

  // Alerts
  async getAlerts(filters?: { zone_id?: number; status?: string; risk_level?: string; category?: string }): Promise<Alert[]> {
    const params = new URLSearchParams();
    if (filters?.zone_id) params.append('zone_id', String(filters.zone_id));
    if (filters?.status) params.append('status', filters.status);
    if (filters?.risk_level) params.append('risk_level', filters.risk_level);
    if (filters?.category) params.append('category', filters.category);

    const res = await fetch(`${API_BASE}/alerts?${params.toString()}`, {
      headers: getAuthHeaders()
    });
    return handleResponse<Alert[]>(res);
  },

  async getAlert(id: number): Promise<Alert> {
    const res = await fetch(`${API_BASE}/alerts/${id}`, {
      headers: getAuthHeaders()
    });
    return handleResponse<Alert>(res);
  },

  async updateAlertStatus(id: number, status: AlertStatus, dismissalReason?: string, resolutionDetails?: string): Promise<Alert> {
    const res = await fetch(`${API_BASE}/alerts/${id}/status`, {
      method: 'POST',
      headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
      body: JSON.stringify({ status, dismissal_reason: dismissalReason, resolution_details: resolutionDetails })
    });
    return handleResponse<Alert>(res);
  },

  async assignAlert(id: number, assignedToId: number): Promise<Alert> {
    const res = await fetch(`${API_BASE}/alerts/${id}/assign`, {
      method: 'POST',
      headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
      body: JSON.stringify({ assigned_to_id: assignedToId })
    });
    return handleResponse<Alert>(res);
  },

  async addAlertNote(id: number, note: string): Promise<any> {
    const res = await fetch(`${API_BASE}/alerts/${id}/notes`, {
      method: 'POST',
      headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
      body: JSON.stringify({ note })
    });
    return handleResponse<any>(res);
  },

  async uploadAlertEvidence(id: number, formData: FormData): Promise<any> {
    const res = await fetch(`${API_BASE}/alerts/${id}/evidence`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: formData
    });
    return handleResponse<any>(res);
  },

  // Reports
  async getReportsSummary(zoneId?: number): Promise<any> {
    const url = zoneId ? `${API_BASE}/reports/summary?zone_id=${zoneId}` : `${API_BASE}/reports/summary`;
    const res = await fetch(url, { headers: getAuthHeaders() });
    return handleResponse<any>(res);
  },

  getExportCsvUrl(zoneId?: number, status?: string): string {
    const params = new URLSearchParams();
    if (zoneId) params.append('zone_id', String(zoneId));
    if (status) params.append('status', status);
    return `${API_BASE}/reports/export-csv?${params.toString()}`;
  },

  getExportPdfUrl(zoneId?: number, status?: string): string {
    const params = new URLSearchParams();
    if (zoneId) params.append('zone_id', String(zoneId));
    if (status) params.append('status', status);
    return `${API_BASE}/reports/export-pdf?${params.toString()}`;
  },

  // Notifications
  async getNotifications(): Promise<NotificationItem[]> {
    const res = await fetch(`${API_BASE}/notifications`, {
      headers: getAuthHeaders()
    });
    return handleResponse<NotificationItem[]>(res);
  },

  async markNotificationRead(id: number): Promise<NotificationItem> {
    const res = await fetch(`${API_BASE}/notifications/${id}/read`, {
      method: 'POST',
      headers: getAuthHeaders()
    });
    return handleResponse<NotificationItem>(res);
  },

  async markAllNotificationsRead(): Promise<any> {
    const res = await fetch(`${API_BASE}/notifications/read-all`, {
      method: 'POST',
      headers: getAuthHeaders()
    });
    return handleResponse<any>(res);
  },

  // Users
  async getUsers(): Promise<User[]> {
    const res = await fetch(`${API_BASE}/users`, {
      headers: getAuthHeaders()
    });
    return handleResponse<User[]>(res);
  },

  async getOfficers(): Promise<User[]> {
    const res = await fetch(`${API_BASE}/users/officers`, {
      headers: getAuthHeaders()
    });
    return handleResponse<User[]>(res);
  },

  async createUser(data: any): Promise<User> {
    const res = await fetch(`${API_BASE}/users`, {
      method: 'POST',
      headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    return handleResponse<User>(res);
  },

  async toggleUserStatus(id: number): Promise<User> {
    const res = await fetch(`${API_BASE}/users/${id}/toggle-status`, {
      method: 'PUT',
      headers: getAuthHeaders()
    });
    return handleResponse<User>(res);
  },

  // Settings
  async getSettings(): Promise<SystemSettings> {
    const res = await fetch(`${API_BASE}/settings`, {
      headers: getAuthHeaders()
    });
    return handleResponse<SystemSettings>(res);
  },

  async updateSettings(data: SystemSettings): Promise<SystemSettings> {
    const res = await fetch(`${API_BASE}/settings`, {
      method: 'PUT',
      headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    return handleResponse<SystemSettings>(res);
  },

  async getAuditLogs(): Promise<AuditLog[]> {
    const res = await fetch(`${API_BASE}/settings/audit-logs`, {
      headers: getAuthHeaders()
    });
    return handleResponse<AuditLog[]>(res);
  }
};
