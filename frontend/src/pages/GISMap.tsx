import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import { MonitoringZone, LandParcel, RestrictedBoundary, Alert } from '../types';
import { GISMapViewer } from '../components/GISMapViewer';
import { RiskBadge } from '../components/RiskBadge';
import { StatusBadge } from '../components/StatusBadge';
import {
  MapPin, ShieldAlert, Layers, Search, Filter,
  ArrowRight, X, Calendar, Crosshair, Eye
} from 'lucide-react';

export const GISMap: React.FC = () => {
  const navigate = useNavigate();
  const [zones, setZones] = useState<MonitoringZone[]>([]);
  const [parcels, setParcels] = useState<LandParcel[]>([]);
  const [restrictedBoundaries, setRestrictedBoundaries] = useState<RestrictedBoundary[]>([]);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [selectedAlert, setSelectedAlert] = useState<Alert | null>(null);

  const [selectedZoneId, setSelectedZoneId] = useState<string>('ALL');
  const [selectedRisk, setSelectedRisk] = useState<string>('ALL');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [focusedCoords, setFocusedCoords] = useState<[number, number] | undefined>(undefined);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    const loadGISData = async () => {
      try {
        const [z, p, rb, a] = await Promise.all([
          api.getZones(),
          api.getParcels(),
          api.getRestrictedBoundaries(),
          api.getAlerts()
        ]);
        setZones(z);
        setParcels(p);
        setRestrictedBoundaries(rb);
        setAlerts(a);
        if (a.length > 0) {
          setSelectedAlert(a[0]);
        }
      } catch (e) {
        console.error("GIS map data loading failed:", e);
      } finally {
        setLoading(false);
      }
    };
    loadGISData();
  }, []);

  const filteredAlerts = alerts.filter(a => {
    if (selectedZoneId !== 'ALL' && String(a.zone_id) !== selectedZoneId) return false;
    if (selectedRisk !== 'ALL' && a.risk_level !== selectedRisk) return false;
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      return (
        a.alert_code.toLowerCase().includes(q) ||
        (a.zone_name && a.zone_name.toLowerCase().includes(q)) ||
        (a.parcel_number && a.parcel_number.toLowerCase().includes(q)) ||
        a.category.toLowerCase().includes(q)
      );
    }
    return true;
  });

  const handleSearchCoordinate = (e: React.FormEvent) => {
    e.preventDefault();
    const parts = searchQuery.split(',').map(s => parseFloat(s.trim()));
    if (parts.length === 2 && !isNaN(parts[0]) && !isNaN(parts[1])) {
      setFocusedCoords([parts[0], parts[1]]);
    }
  };

  const handleSelectAlertOnMap = (alert: Alert) => {
    setSelectedAlert(alert);
    setFocusedCoords([alert.centroid_lat, alert.centroid_lng]);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full text-slate-400 gap-3 py-32">
        <div className="w-6 h-6 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin" />
        <span>Loading Interactive GIS Layers & Cadastral Meshes...</span>
      </div>
    );
  }

  return (
    <div className="h-[calc(100vh-6.5rem)] flex flex-col space-y-3">
      {/* Search & Spatial Filters Bar */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-3 flex flex-wrap items-center justify-between gap-3 shadow-md">
        <form onSubmit={handleSearchCoordinate} className="flex items-center gap-2 flex-1 min-w-[280px]">
          <div className="relative flex-1">
            <Search className="w-4 h-4 text-slate-500 absolute left-3 top-2.5" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search alert code, parcel, or lat, lng (e.g. 12.9352, 77.6741)..."
              className="w-full bg-slate-950 border border-slate-800 rounded-lg pl-9 pr-3 py-1.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-emerald-500 transition"
            />
          </div>
          <button
            type="submit"
            className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium rounded-lg transition"
          >
            Locate
          </button>
        </form>

        <div className="flex items-center gap-3 text-xs">
          {/* Zone Filter */}
          <div className="flex items-center gap-1.5 text-slate-400">
            <Filter className="w-3.5 h-3.5" />
            <select
              value={selectedZoneId}
              onChange={(e) => setSelectedZoneId(e.target.value)}
              className="bg-slate-950 border border-slate-800 rounded-lg px-2.5 py-1.5 text-slate-200 text-xs focus:outline-none focus:border-emerald-500"
            >
              <option value="ALL">All Monitoring Zones</option>
              {zones.map(z => (
                <option key={z.id} value={z.id}>{z.name}</option>
              ))}
            </select>
          </div>

          {/* Risk Level Filter */}
          <select
            value={selectedRisk}
            onChange={(e) => setSelectedRisk(e.target.value)}
            className="bg-slate-950 border border-slate-800 rounded-lg px-2.5 py-1.5 text-slate-200 text-xs focus:outline-none focus:border-emerald-500"
          >
            <option value="ALL">All Risk Severities</option>
            <option value="CRITICAL">Critical Risk</option>
            <option value="HIGH">High Risk</option>
            <option value="MEDIUM">Medium Risk</option>
            <option value="LOW">Low Risk</option>
          </select>

          <span className="text-slate-400 font-mono text-[11px] border-l border-slate-800 pl-3">
            Showing <strong className="text-emerald-400">{filteredAlerts.length}</strong> detections
          </span>
        </div>
      </div>

      {/* Main Map Stage + Detailed Inspection Drawer */}
      <div className="flex-1 flex gap-4 min-h-0 relative">
        {/* Full-bleed Leaflet Map */}
        <div className="flex-1 h-full min-h-[480px]">
          <GISMapViewer
            zones={zones}
            parcels={parcels}
            restrictedBoundaries={restrictedBoundaries}
            alerts={filteredAlerts}
            height="100%"
            focusedCoordinates={focusedCoords}
            onSelectAlert={handleSelectAlertOnMap}
          />
        </div>

        {/* Selected Detection Side Panel */}
        {selectedAlert && (
          <div className="w-80 lg:w-96 bg-slate-900 border border-slate-800 rounded-xl p-4 flex flex-col shadow-2xl overflow-y-auto">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <div className="flex items-center gap-2">
                <span className="font-mono text-sm font-bold text-emerald-400">{selectedAlert.alert_code}</span>
                <RiskBadge level={selectedAlert.risk_level} score={selectedAlert.risk_score} />
              </div>
              <button
                onClick={() => setSelectedAlert(null)}
                className="text-slate-500 hover:text-white p-1 rounded hover:bg-slate-800"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-4 py-4 text-xs">
              <div>
                <label className="text-slate-500 text-[10px] uppercase tracking-wider font-semibold">Change Classification</label>
                <p className="font-semibold text-white text-sm mt-0.5">{selectedAlert.category.replace('_', ' ')}</p>
                <div className="mt-1"><StatusBadge status={selectedAlert.status} /></div>
              </div>

              {/* Geographic Coordinates & Spatial Scope */}
              <div className="bg-slate-950 p-3 rounded-lg border border-slate-800 space-y-2">
                <div className="flex justify-between items-center text-slate-400">
                  <span>Centroid Lat/Lng:</span>
                  <span className="font-mono text-slate-200">{selectedAlert.centroid_lat.toFixed(5)}, {selectedAlert.centroid_lng.toFixed(5)}</span>
                </div>
                <div className="flex justify-between items-center text-slate-400">
                  <span>Candidate Area:</span>
                  <span className="font-mono text-cyan-400 font-bold">{selectedAlert.affected_area_sqm.toLocaleString()} m² ({selectedAlert.affected_area_hectares} ha)</span>
                </div>
                <div className="flex justify-between items-center text-slate-400">
                  <span>Monitored Zone:</span>
                  <span className="text-slate-200">{selectedAlert.zone_name}</span>
                </div>
                <div className="flex justify-between items-center text-slate-400">
                  <span>Cadastral Parcel:</span>
                  <span className="font-mono text-slate-200">{selectedAlert.parcel_number || 'Cadastral Survey Pending'}</span>
                </div>
              </div>

              {/* Explainable Reasons */}
              <div>
                <label className="text-slate-500 text-[10px] uppercase tracking-wider font-semibold">Explainable Detection Rationale</label>
                <ul className="mt-1.5 space-y-1.5">
                  {(selectedAlert.risk_reasons || ['Candidate spectral reflection anomaly detected.']).map((r, i) => (
                    <li key={i} className="text-[11px] text-slate-300 flex items-start gap-1.5 bg-slate-950/60 p-2 rounded border border-slate-800/60">
                      <ShieldAlert className="w-3.5 h-3.5 text-amber-400 flex-shrink-0 mt-0.5" />
                      <span>{r}</span>
                    </li>
                  ))}
                </ul>
              </div>

              {/* Satellite Acquisition Dates */}
              <div className="grid grid-cols-2 gap-2 text-[11px]">
                <div className="bg-slate-950 p-2.5 rounded border border-slate-800">
                  <span className="text-slate-500 block text-[10px]">First Observed</span>
                  <span className="font-mono text-slate-300">{selectedAlert.first_observed_date}</span>
                </div>
                <div className="bg-slate-950 p-2.5 rounded border border-slate-800">
                  <span className="text-slate-500 block text-[10px]">Latest Observed</span>
                  <span className="font-mono text-emerald-400">{selectedAlert.latest_observed_date}</span>
                </div>
              </div>
            </div>

            {/* Direct Link to Investigation & Evidence Slider */}
            <button
              onClick={() => navigate(`/alerts/${selectedAlert.id}`)}
              className="w-full mt-auto py-2.5 bg-gradient-to-r from-emerald-600 to-cyan-600 hover:from-emerald-500 hover:to-cyan-500 text-white rounded-lg font-semibold text-xs flex items-center justify-center gap-2 shadow-lg transition"
            >
              <Eye className="w-4 h-4" /> Open Full Evidence Viewer <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        )}
      </div>
    </div>
  );
};
