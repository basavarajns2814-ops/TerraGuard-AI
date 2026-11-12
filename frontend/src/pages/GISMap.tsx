import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import { MonitoringZone, LandParcel, RestrictedBoundary, Alert, DetectedChange } from '../types';
import { GISMapViewer } from '../components/GISMapViewer';
import { RiskBadge } from '../components/RiskBadge';
import { StatusBadge } from '../components/StatusBadge';
import {
  MapPin, ShieldAlert, Layers, Search, Filter,
  ArrowRight, X, Calendar, Crosshair, Eye,
  Plus, Trash2, Edit3, Check, Undo2, Satellite,
  Save, AlertTriangle, Sparkles, Compass
} from 'lucide-react';

// Geodesic area calculation for UI feedback in square meters
function calculateGeodesicArea(coords: [number, number][]): number {
  if (coords.length < 3) return 0;
  let latSum = 0;
  for (const [lat] of coords) latSum += lat;
  const meanLatRad = (latSum / coords.length) * (Math.PI / 180);
  const mPerDegLat = 111320.0;
  const mPerDegLng = 111320.0 * Math.cos(meanLatRad);

  let area = 0;
  for (let i = 0; i < coords.length; i++) {
    const j = (i + 1) % coords.length;
    const xi = coords[i][1] * mPerDegLng;
    const yi = coords[i][0] * mPerDegLat;
    const xj = coords[j][1] * mPerDegLng;
    const yj = coords[j][0] * mPerDegLat;
    area += xi * yj - xj * yi;
  }
  return Math.abs(area) / 2.0;
}

// Karnataka geographical locations for instant navigation
const KARNATAKA_PRESETS: { name: string; district: string; coords: [number, number] }[] = [
  { name: 'Bellandur Lake Catchment', district: 'Bengaluru Urban', coords: [12.9352, 77.6741] },
  { name: 'Varthur Lake Wetland', district: 'Bengaluru Urban', coords: [12.9421, 77.7423] },
  { name: 'Bannerghatta Forest Corridor', district: 'Bengaluru Rural', coords: [12.8000, 77.5800] },
  { name: 'Hebbal Lake & Buffer', district: 'Bengaluru Urban', coords: [13.0382, 77.5916] },
  { name: 'Sarjapur Peripheral Zone', district: 'Bengaluru Urban', coords: [12.8600, 77.7800] },
  { name: 'Whitefield Eastern Suburb', district: 'Bengaluru Urban', coords: [12.9698, 77.7500] },
  { name: 'Mysuru Chamundi Foothills', district: 'Mysuru', coords: [12.2958, 76.6710] },
  { name: 'Hubballi-Dharwad Corridor', district: 'Dharwad', coords: [15.3647, 75.1240] }
];

export const GISMap: React.FC = () => {
  const navigate = useNavigate();
  const [zones, setZones] = useState<MonitoringZone[]>([]);
  const [parcels, setParcels] = useState<LandParcel[]>([]);
  const [restrictedBoundaries, setRestrictedBoundaries] = useState<RestrictedBoundary[]>([]);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [changes, setChanges] = useState<DetectedChange[]>([]);
  const [selectedAlert, setSelectedAlert] = useState<Alert | null>(null);
  const [selectedZone, setSelectedZone] = useState<MonitoringZone | null>(null);

  const [selectedZoneId, setSelectedZoneId] = useState<string>('ALL');
  const [selectedRisk, setSelectedRisk] = useState<string>('ALL');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [focusedCoords, setFocusedCoords] = useState<[number, number] | undefined>(undefined);
  const [loading, setLoading] = useState<boolean>(true);

  // Drawing state
  const [isDrawing, setIsDrawing] = useState<boolean>(false);
  const [drawingPoints, setDrawingPoints] = useState<[number, number][]>([]);
  const [showSaveModal, setShowSaveModal] = useState<boolean>(false);
  const [savingZone, setSavingZone] = useState<boolean>(false);
  const [zoneName, setZoneName] = useState<string>('');
  const [zoneDistrict, setZoneDistrict] = useState<string>('Bengaluru Urban');
  const [zoneDescription, setZoneDescription] = useState<string>('');
  const [errorMessage, setErrorMessage] = useState<string>('');
  const [successMessage, setSuccessMessage] = useState<string>('');

  useEffect(() => {
    loadGISData();
  }, []);

  const loadGISData = async () => {
    try {
      setLoading(true);
      const [z, p, rb, a, c] = await Promise.all([
        api.getZones(),
        api.getParcels(),
        api.getRestrictedBoundaries(),
        api.getAlerts(),
        api.getChanges()
      ]);
      setZones(z);
      setParcels(p);
      setRestrictedBoundaries(rb);
      setAlerts(a);
      setChanges(c);
      if (z.length > 0 && !selectedZone) {
        setSelectedZone(z[0]);
      }
    } catch (e) {
      console.error("GIS map data loading failed:", e);
    } finally {
      setLoading(false);
    }
  };

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
  const filteredChanges = changes.filter(c => selectedZoneId === 'ALL' || String(c.zone_id) === selectedZoneId);

  const handleSearchCoordinate = (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchQuery.trim()) return;

    // Check for preset match
    const preset = KARNATAKA_PRESETS.find(p => p.name.toLowerCase().includes(searchQuery.toLowerCase()));
    if (preset) {
      setFocusedCoords(preset.coords);
      return;
    }

    // Check for comma separated lat, lng
    const parts = searchQuery.split(',').map(s => parseFloat(s.trim()));
    if (parts.length === 2 && !isNaN(parts[0]) && !isNaN(parts[1])) {
      setFocusedCoords([parts[0], parts[1]]);
    }
  };

  const handlePresetSelect = (coords: [number, number]) => {
    setFocusedCoords(coords);
  };

  // Drawing Handlers
  const handleStartDrawing = () => {
    setIsDrawing(true);
    setDrawingPoints([]);
    setSelectedAlert(null);
    setSelectedZone(null);
    setErrorMessage('');
  };

  const handleAddDrawingPoint = (point: [number, number]) => {
    setDrawingPoints(prev => [...prev, point]);
  };

  const handleUpdateDrawingPoint = (index: number, point: [number, number]) => {
    setDrawingPoints(prev => {
      const copy = [...prev];
      copy[index] = point;
      return copy;
    });
  };

  const handleUndoPoint = () => {
    setDrawingPoints(prev => prev.slice(0, -1));
  };

  const handleCancelDrawing = () => {
    setIsDrawing(false);
    setDrawingPoints([]);
    setErrorMessage('');
  };

  const handleFinishDrawing = () => {
    if (drawingPoints.length < 3) {
      setErrorMessage("A monitoring area polygon requires at least 3 boundary vertices.");
      return;
    }
    setErrorMessage('');
    setShowSaveModal(true);
  };

  const calculatedAreaSqm = calculateGeodesicArea(drawingPoints);
  const calculatedAreaHa = Number((calculatedAreaSqm / 10000).toFixed(2));

  const handleSaveZone = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!zoneName.trim()) {
      setErrorMessage("Please enter a name for the monitoring area.");
      return;
    }

    // Build standard GeoJSON Polygon [lng, lat] format
    const geojsonCoords = drawingPoints.map(pt => [Number(pt[1].toFixed(6)), Number(pt[0].toFixed(6))]);
    // Close polygon ring: first vertex must equal last vertex
    geojsonCoords.push([geojsonCoords[0][0], geojsonCoords[0][1]]);

    const geojson = {
      type: "Polygon",
      coordinates: [geojsonCoords]
    };

    setSavingZone(true);
    setErrorMessage('');
    try {
      const newZone = await api.createZone({
        name: zoneName.trim(),
        district: zoneDistrict.trim(),
        state: 'Karnataka',
        description: zoneDescription.trim(),
        area_hectares: calculatedAreaHa,
        geojson
      });

      setZones(prev => [newZone, ...prev]);
      setSelectedZone(newZone);
      setIsDrawing(false);
      setDrawingPoints([]);
      setShowSaveModal(false);
      setZoneName('');
      setZoneDescription('');
      setSuccessMessage(`Monitoring Area "${newZone.name}" successfully registered (${newZone.area_hectares} ha).`);
      setTimeout(() => setSuccessMessage(''), 5000);
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to save monitoring zone.");
    } finally {
      setSavingZone(false);
    }
  };

  const handleDeleteZone = async (zone: MonitoringZone) => {
    if (!window.confirm(`Are you sure you want to delete monitoring area "${zone.name}"? This action will remove the surveillance boundary.`)) {
      return;
    }
    try {
      await api.deleteZone(zone.id);
      setZones(prev => prev.filter(z => z.id !== zone.id));
      if (selectedZone?.id === zone.id) {
        setSelectedZone(null);
      }
      setSuccessMessage(`Monitoring Area "${zone.name}" deleted.`);
      setTimeout(() => setSuccessMessage(''), 4000);
    } catch (err: any) {
      alert(err.message || "Failed to delete monitoring zone.");
    }
  };

  const handleSelectZoneOnMap = (zone: MonitoringZone) => {
    setSelectedZone(zone);
    setSelectedAlert(null);
    if (zone.geojson?.coordinates?.[0]?.[0]) {
      const firstCoord = zone.geojson.coordinates[0][0];
      setFocusedCoords([firstCoord[1], firstCoord[0]]);
    }
  };

  const handleSelectAlertOnMap = (alert: Alert) => {
    setSelectedAlert(alert);
    setSelectedZone(null);
    setFocusedCoords([alert.centroid_lat, alert.centroid_lng]);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full text-slate-400 gap-3 py-32">
        <div className="w-6 h-6 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin" />
        <span>Loading Interactive GIS Layers & Cadastral Boundaries...</span>
      </div>
    );
  }

  return (
    <div className="h-[calc(100vh-6.5rem)] flex flex-col space-y-3">
      {/* Notifications */}
      {successMessage && (
        <div className="bg-emerald-950/80 border border-emerald-500 text-emerald-200 text-xs px-3.5 py-2 rounded-lg flex items-center justify-between shadow-lg">
          <span className="flex items-center gap-2">
            <Check className="w-4 h-4 text-emerald-400" />
            {successMessage}
          </span>
          <button onClick={() => setSuccessMessage('')}><X className="w-3.5 h-3.5" /></button>
        </div>
      )}
      {errorMessage && (
        <div className="bg-rose-950/80 border border-rose-500 text-rose-200 text-xs px-3.5 py-2 rounded-lg flex items-center justify-between shadow-lg">
          <span className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-rose-400" />
            {errorMessage}
          </span>
          <button onClick={() => setErrorMessage('')}><X className="w-3.5 h-3.5" /></button>
        </div>
      )}

      {/* Search & Spatial Tools Bar */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-3 flex flex-wrap items-center justify-between gap-3 shadow-md">
        <form onSubmit={handleSearchCoordinate} className="flex items-center gap-2 flex-1 min-w-[280px]">
          <div className="relative flex-1">
            <Search className="w-4 h-4 text-slate-500 absolute left-3 top-2.5" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search location (e.g. Bellandur Lake, Hebbal, or lat, lng: 12.935, 77.674)..."
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

        {/* Location Presets Pill Row */}
        <div className="hidden xl:flex items-center gap-1.5 text-[11px] text-slate-400">
          <span className="text-slate-500">Karnataka Hotspots:</span>
          {KARNATAKA_PRESETS.slice(0, 4).map((p, idx) => (
            <button
              key={idx}
              type="button"
              onClick={() => handlePresetSelect(p.coords)}
              className="px-2 py-0.5 rounded bg-slate-950 hover:bg-slate-800 text-slate-300 border border-slate-800 text-[10px] transition"
            >
              {p.name.split(' ')[0]}
            </button>
          ))}
        </div>

        {/* Action Controls: Draw Boundary / Filter */}
        <div className="flex items-center gap-2.5 text-xs">
          {!isDrawing ? (
            <button
              type="button"
              onClick={handleStartDrawing}
              className="px-3 py-1.5 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white font-semibold text-xs rounded-lg flex items-center gap-1.5 shadow transition"
            >
              <Plus className="w-3.5 h-3.5" /> Draw Boundary
            </button>
          ) : (
            <div className="flex items-center gap-1.5">
              <button
                type="button"
                onClick={handleUndoPoint}
                disabled={drawingPoints.length === 0}
                className="px-2.5 py-1.5 bg-slate-800 hover:bg-slate-700 disabled:opacity-40 text-slate-200 text-xs rounded-lg flex items-center gap-1 transition"
                title="Undo last placed vertex"
              >
                <Undo2 className="w-3.5 h-3.5" /> Undo
              </button>
              <button
                type="button"
                onClick={handleFinishDrawing}
                disabled={drawingPoints.length < 3}
                className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-40 text-white font-semibold text-xs rounded-lg flex items-center gap-1.5 shadow transition"
              >
                <Check className="w-3.5 h-3.5" /> Complete Boundary ({drawingPoints.length})
              </button>
              <button
                type="button"
                onClick={handleCancelDrawing}
                className="px-2.5 py-1.5 bg-rose-900/60 hover:bg-rose-800 text-rose-200 text-xs rounded-lg flex items-center gap-1 transition"
              >
                <X className="w-3.5 h-3.5" /> Cancel
              </button>
            </div>
          )}

          {/* Zone Selector */}
          <select
            value={selectedZoneId}
            onChange={(e) => {
              const val = e.target.value;
              setSelectedZoneId(val);
              if (val !== 'ALL') {
                const z = zones.find(item => String(item.id) === val);
                if (z) handleSelectZoneOnMap(z);
              }
            }}
            className="bg-slate-950 border border-slate-800 rounded-lg px-2.5 py-1.5 text-slate-200 text-xs focus:outline-none focus:border-emerald-500"
          >
            <option value="ALL">All Monitored Areas ({zones.length})</option>
            {zones.map(z => (
              <option key={z.id} value={z.id}>{z.name}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Drawing Mode Active Banner HUD */}
      {isDrawing && (
        <div className="bg-slate-950/90 border border-emerald-500/50 rounded-lg p-2.5 flex items-center justify-between text-xs text-slate-200 shadow-xl">
          <div className="flex items-center gap-3">
            <span className="flex items-center gap-1.5 font-bold text-emerald-400">
              <Crosshair className="w-4 h-4 animate-pulse" /> Boundary Drawing Mode Active
            </span>
            <span className="text-slate-400">
              Click on the satellite map to place perimeter vertices. Drag points to adjust. Click the first point or "Complete Boundary" when done.
            </span>
          </div>
          <div className="flex items-center gap-4 font-mono">
            <span>Vertices: <strong className="text-white">{drawingPoints.length}</strong></span>
            <span>Calculated Area: <strong className="text-cyan-400">{calculatedAreaHa} ha</strong> ({calculatedAreaSqm.toLocaleString()} m²)</span>
          </div>
        </div>
      )}

      {/* Main Map Stage + Detailed Inspection Drawer */}
      <div className="flex-1 flex gap-4 min-h-0 relative">
        {/* Full-bleed Leaflet Map */}
        <div className="flex-1 h-full min-h-[480px]">
          <GISMapViewer
            zones={zones}
            parcels={parcels}
            restrictedBoundaries={restrictedBoundaries}
            alerts={filteredAlerts}
            changes={filteredChanges}
            height="100%"
            focusedCoordinates={focusedCoords}
            onSelectAlert={handleSelectAlertOnMap}
            onSelectZone={handleSelectZoneOnMap}
            isDrawing={isDrawing}
            drawingPoints={drawingPoints}
            onAddDrawingPoint={handleAddDrawingPoint}
            onUpdateDrawingPoint={handleUpdateDrawingPoint}
            onCloseDrawingPolygon={handleFinishDrawing}
            selectedZoneId={selectedZone?.id}
          />
        </div>

        {/* Selected Zone Side Panel */}
        {selectedZone && !selectedAlert && !isDrawing && (
          <div className="w-80 lg:w-96 bg-slate-900 border border-slate-800 rounded-xl p-4 flex flex-col shadow-2xl overflow-y-auto">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <div className="flex items-center gap-2">
                <Compass className="w-4 h-4 text-cyan-400" />
                <span className="font-bold text-white text-sm truncate max-w-[200px]">{selectedZone.name}</span>
              </div>
              <button
                onClick={() => setSelectedZone(null)}
                className="text-slate-500 hover:text-white p-1 rounded hover:bg-slate-800"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-4 py-4 text-xs">
              <div className="bg-slate-950 p-3 rounded-lg border border-slate-800 space-y-2">
                <div className="flex justify-between items-center text-slate-400">
                  <span>District:</span>
                  <span className="text-slate-200 font-medium">{selectedZone.district}, {selectedZone.state}</span>
                </div>
                <div className="flex justify-between items-center text-slate-400">
                  <span>Monitored Area:</span>
                  <span className="font-mono text-cyan-400 font-bold">{selectedZone.area_hectares} ha</span>
                </div>
                <div className="flex justify-between items-center text-slate-400">
                  <span>Risk Status:</span>
                  <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                    selectedZone.risk_status === 'CRITICAL' ? 'bg-rose-500/10 text-rose-400 border border-rose-500/30' : 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30'
                  }`}>
                    {selectedZone.risk_status}
                  </span>
                </div>
                <div className="flex justify-between items-center text-slate-400">
                  <span>Cadastral Parcels:</span>
                  <span className="text-slate-200 font-mono">{selectedZone.parcels_count || 0}</span>
                </div>
                <div className="flex justify-between items-center text-slate-400">
                  <span>Active Alerts:</span>
                  <span className="text-amber-400 font-mono font-bold">{selectedZone.alerts_count || 0}</span>
                </div>
              </div>

              {selectedZone.description && (
                <div>
                  <label className="text-slate-500 text-[10px] uppercase tracking-wider font-semibold">Description</label>
                  <p className="text-slate-300 mt-1 text-xs leading-relaxed bg-slate-950/60 p-2.5 rounded border border-slate-800/60">
                    {selectedZone.description}
                  </p>
                </div>
              )}

              {/* Geographic Geometry Information */}
              <div>
                <label className="text-slate-500 text-[10px] uppercase tracking-wider font-semibold">Boundary Polygon Metadata</label>
                <div className="bg-slate-950 p-2.5 rounded border border-slate-800 mt-1 space-y-1 font-mono text-[11px] text-slate-300">
                  <div>Type: {selectedZone.geojson?.type || 'Polygon'}</div>
                  <div>Vertices: {selectedZone.geojson?.coordinates?.[0]?.length || 0} points</div>
                  <div className="text-[10px] text-slate-500 truncate">
                    Bounds: {JSON.stringify(selectedZone.geojson?.coordinates?.[0]?.[0])}
                  </div>
                </div>
              </div>

              {/* Quick Actions */}
              <div className="pt-2 space-y-2">
                <button
                  type="button"
                  onClick={() => navigate('/imagery')}
                  className="w-full py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg font-semibold text-xs flex items-center justify-center gap-2 shadow transition"
                >
                  <Satellite className="w-3.5 h-3.5" /> Acquire Earth Engine Satellite Scenes
                </button>
                <button
                  type="button"
                  onClick={() => handleDeleteZone(selectedZone)}
                  className="w-full py-1.5 bg-rose-950/60 hover:bg-rose-900 border border-rose-800/60 text-rose-300 rounded-lg text-xs font-medium flex items-center justify-center gap-1.5 transition"
                >
                  <Trash2 className="w-3.5 h-3.5" /> Delete Monitoring Area
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Selected Detection Side Panel */}
        {selectedAlert && !isDrawing && (
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

            <button
              onClick={() => navigate(`/alerts/${selectedAlert.id}`)}
              className="w-full mt-auto py-2.5 bg-gradient-to-r from-emerald-600 to-cyan-600 hover:from-emerald-500 hover:to-cyan-500 text-white rounded-lg font-semibold text-xs flex items-center justify-center gap-2 shadow-lg transition"
            >
              <Eye className="w-4 h-4" /> Open Full Evidence Viewer <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        )}
      </div>

      {/* Save Monitoring Area Modal */}
      {showSaveModal && (
        <div className="fixed inset-0 z-[2000] bg-black/75 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-lg w-full p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <div className="flex items-center gap-2 text-white font-bold text-base">
                <Save className="w-5 h-5 text-emerald-400" /> Save New Monitoring Area
              </div>
              <button
                type="button"
                onClick={() => setShowSaveModal(false)}
                className="text-slate-400 hover:text-white"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleSaveZone} className="space-y-4 text-xs">
              <div>
                <label className="text-slate-300 font-semibold block mb-1">
                  Monitoring Area Name <span className="text-rose-400">*</span>
                </label>
                <input
                  type="text"
                  required
                  value={zoneName}
                  onChange={(e) => setZoneName(e.target.value)}
                  placeholder="e.g. Bellandur Lake North Catchment Zone"
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-emerald-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-slate-300 font-semibold block mb-1">District (Karnataka)</label>
                  <select
                    value={zoneDistrict}
                    onChange={(e) => setZoneDistrict(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-emerald-500"
                  >
                    <option value="Bengaluru Urban">Bengaluru Urban</option>
                    <option value="Bengaluru Rural">Bengaluru Rural</option>
                    <option value="Mysuru">Mysuru</option>
                    <option value="Ramanagara">Ramanagara</option>
                    <option value="Tumakuru">Tumakuru</option>
                    <option value="Dharwad">Dharwad</option>
                    <option value="Dakshina Kannada">Dakshina Kannada</option>
                  </select>
                </div>
                <div>
                  <label className="text-slate-300 font-semibold block mb-1">Calculated Area</label>
                  <div className="w-full bg-slate-950/80 border border-slate-800 rounded-lg px-3 py-2 text-emerald-400 font-mono font-bold">
                    {calculatedAreaHa} hectares
                  </div>
                </div>
              </div>

              <div>
                <label className="text-slate-300 font-semibold block mb-1">Surveillance Description & Notes</label>
                <textarea
                  rows={3}
                  value={zoneDescription}
                  onChange={(e) => setZoneDescription(e.target.value)}
                  placeholder="e.g. Eco-sensitive wetland buffer monitored for unauthorized land clearing or construction creep."
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-emerald-500"
                />
              </div>

              {/* GeoJSON Geometry Summary */}
              <div className="bg-slate-950 p-3 rounded-lg border border-slate-800 space-y-1 font-mono text-[11px] text-slate-400">
                <div className="text-slate-300 font-semibold font-sans text-xs">Verified Geospatial Geometry</div>
                <div>Polygon closed ring: {drawingPoints.length + 1} vertices</div>
                <div>Approximate metric surface area: {calculatedAreaSqm.toLocaleString()} m²</div>
                <div className="text-[10px] text-emerald-400">CRS: WGS84 (EPSG:4326) / Geodesic Metric Proj</div>
              </div>

              <div className="flex justify-end gap-3 pt-3 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setShowSaveModal(false)}
                  className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg font-medium transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={savingZone}
                  className="px-5 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white font-semibold rounded-lg flex items-center gap-2 shadow-lg transition"
                >
                  {savingZone ? 'Saving...' : 'Confirm & Save Boundary'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
