import React, { useState, useEffect } from 'react';
import { MapContainer, TileLayer, Polygon, Marker, Popup, LayersControl, GeoJSON, useMap } from 'react-leaflet';
import L from 'leaflet';
import { MonitoringZone, LandParcel, RestrictedBoundary, DetectedChange, Alert } from '../types';
import { RiskBadge } from './RiskBadge';
import { StatusBadge } from './StatusBadge';
import { Layers, ShieldAlert, Eye, MapPin } from 'lucide-react';

// Fix Leaflet standard marker icon paths in Vite
delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
});

// Custom colored circle markers for detections
const createCustomMarker = (riskLevel: string) => {
  const colorMap: Record<string, string> = {
    CRITICAL: '#ef4444',
    HIGH: '#f59e0b',
    MEDIUM: '#06b6d4',
    LOW: '#10b981',
  };
  const color = colorMap[riskLevel] || '#10b981';

  return L.divIcon({
    className: 'custom-map-marker',
    html: `
      <div style="
        width: 18px;
        height: 18px;
        border-radius: 50%;
        background-color: ${color};
        border: 2px solid #0f172a;
        box-shadow: 0 0 10px ${color};
        animation: pulse 2s infinite;
      "></div>
    `,
    iconSize: [18, 18],
    iconAnchor: [9, 9]
  });
};

interface GISMapViewerProps {
  zones?: MonitoringZone[];
  parcels?: LandParcel[];
  restrictedBoundaries?: RestrictedBoundary[];
  changes?: DetectedChange[];
  alerts?: Alert[];
  onSelectAlert?: (alert: Alert) => void;
  onSelectChange?: (change: DetectedChange) => void;
  center?: [number, number];
  zoom?: number;
  height?: string;
  focusedCoordinates?: [number, number];
}

// Controller component to smoothly center on focused coords
const MapCenterController: React.FC<{ coords?: [number, number]; zoom?: number }> = ({ coords, zoom }) => {
  const map = useMap();
  useEffect(() => {
    if (coords && coords[0] && coords[1]) {
      map.flyTo(coords, zoom || 15, { duration: 1.2 });
    }
  }, [coords, zoom, map]);
  return null;
};

export const GISMapViewer: React.FC<GISMapViewerProps> = ({
  zones = [],
  parcels = [],
  restrictedBoundaries = [],
  changes = [],
  alerts = [],
  onSelectAlert,
  onSelectChange,
  center = [12.9352, 77.6741], // Default Bellandur Lake, Bengaluru
  zoom = 13,
  height = '600px',
  focusedCoordinates
}) => {
  const [showZones, setShowZones] = useState<boolean>(true);
  const [showParcels, setShowParcels] = useState<boolean>(true);
  const [showRestricted, setShowRestricted] = useState<boolean>(true);
  const [showDetections, setShowDetections] = useState<boolean>(true);

  return (
    <div className="relative w-full rounded-xl overflow-hidden border border-slate-800 shadow-2xl" style={{ height }}>
      {/* Floating Layer Controls */}
      <div className="absolute top-4 right-4 z-[1000] bg-slate-900/90 backdrop-blur border border-slate-800 rounded-lg p-3 shadow-xl text-xs space-y-2">
        <div className="font-semibold text-slate-300 flex items-center gap-1.5 pb-1 border-b border-slate-800">
          <Layers className="w-3.5 h-3.5 text-emerald-400" /> Layer Overlays
        </div>
        <label className="flex items-center gap-2 cursor-pointer text-slate-300 hover:text-white">
          <input
            type="checkbox"
            checked={showZones}
            onChange={(e) => setShowZones(e.target.checked)}
            className="rounded accent-emerald-500"
          />
          <span className="w-2.5 h-2.5 rounded-sm bg-cyan-500/80 inline-block border border-cyan-400" />
          Monitoring Zones ({zones.length})
        </label>
        <label className="flex items-center gap-2 cursor-pointer text-slate-300 hover:text-white">
          <input
            type="checkbox"
            checked={showParcels}
            onChange={(e) => setShowParcels(e.target.checked)}
            className="rounded accent-emerald-500"
          />
          <span className="w-2.5 h-2.5 rounded-sm bg-slate-500/60 inline-block border border-slate-400" />
          Cadastral Parcels ({parcels.length})
        </label>
        <label className="flex items-center gap-2 cursor-pointer text-slate-300 hover:text-white">
          <input
            type="checkbox"
            checked={showRestricted}
            onChange={(e) => setShowRestricted(e.target.checked)}
            className="rounded accent-emerald-500"
          />
          <span className="w-2.5 h-2.5 rounded-sm bg-rose-500/80 inline-block border border-rose-400" />
          Restricted Buffers ({restrictedBoundaries.length})
        </label>
        <label className="flex items-center gap-2 cursor-pointer text-slate-300 hover:text-white">
          <input
            type="checkbox"
            checked={showDetections}
            onChange={(e) => setShowDetections(e.target.checked)}
            className="rounded accent-emerald-500"
          />
          <span className="w-2.5 h-2.5 rounded-full bg-red-500 inline-block border border-white" />
          AI Detections ({alerts.length || changes.length})
        </label>
      </div>

      {/* Floating Map Legend */}
      <div className="absolute bottom-6 left-4 z-[1000] bg-slate-900/90 backdrop-blur border border-slate-800 rounded-lg p-2.5 shadow-xl text-[11px] text-slate-300 space-y-1">
        <div className="font-semibold text-slate-200">Risk Severity</div>
        <div className="flex items-center gap-3">
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-red-500" /> Critical</span>
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-amber-500" /> High</span>
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-cyan-500" /> Medium</span>
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-emerald-500" /> Low</span>
        </div>
      </div>

      <MapContainer
        center={center}
        zoom={zoom}
        style={{ width: '100%', height: '100%' }}
        zoomControl={true}
      >
        <MapCenterController coords={focusedCoordinates} zoom={15} />

        {/* Base Layer: CartoDB Dark Matter for sleek GIS platform aesthetics */}
        <TileLayer
          attribution='&copy; <a href="https://carto.com/">CARTO</a> &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
          maxZoom={19}
        />

        {/* 1. Monitoring Zones Layer */}
        {showZones && zones.map((z) => (
          z.geojson && (
            <GeoJSON
              key={`zone-${z.id}`}
              data={z.geojson}
              style={{
                color: '#06b6d4',
                weight: 2,
                opacity: 0.8,
                fillColor: '#06b6d4',
                fillOpacity: 0.08,
                dashArray: '4, 4'
              }}
            >
              <Popup>
                <div className="p-2 text-xs">
                  <div className="font-bold text-cyan-400 text-sm">{z.name}</div>
                  <div className="text-slate-300 mt-1">District: {z.district}, {z.state}</div>
                  <div className="text-slate-400">Monitored Area: {z.area_hectares} ha</div>
                </div>
              </Popup>
            </GeoJSON>
          )
        ))}

        {/* 2. Cadastral Land Parcels Layer */}
        {showParcels && parcels.map((p) => (
          p.geojson && (
            <GeoJSON
              key={`parcel-${p.id}`}
              data={p.geojson}
              style={{
                color: '#64748b',
                weight: 1.5,
                opacity: 0.7,
                fillColor: '#334155',
                fillOpacity: 0.12
              }}
            >
              <Popup>
                <div className="p-2 text-xs">
                  <div className="font-bold text-white">Parcel: {p.parcel_number}</div>
                  <div className="text-slate-300 mt-1">Tenure: {p.owner_type.replace('_', ' ')}</div>
                  <div className="text-slate-400">Use: {p.authorized_use}</div>
                  <div className="text-slate-400">Area: {p.area_sqm.toLocaleString()} m² ({p.area_hectares} ha)</div>
                </div>
              </Popup>
            </GeoJSON>
          )
        ))}

        {/* 3. Restricted Boundaries Layer (e.g. 30m Lake Buffer / Forest) */}
        {showRestricted && restrictedBoundaries.map((rb) => (
          rb.geojson && (
            <GeoJSON
              key={`rb-${rb.id}`}
              data={rb.geojson}
              style={{
                color: '#f43f5e',
                weight: 2.5,
                opacity: 0.9,
                fillColor: '#f43f5e',
                fillOpacity: 0.2,
                dashArray: '3, 5'
              }}
            >
              <Popup>
                <div className="p-2 text-xs">
                  <div className="font-bold text-rose-400 flex items-center gap-1">
                    <ShieldAlert className="w-3.5 h-3.5" /> {rb.name}
                  </div>
                  <div className="text-slate-300 mt-1">Type: {rb.boundary_type.replace('_', ' ')}</div>
                  <div className="text-slate-400">Statutory Buffer: {rb.buffer_distance_meters} meters</div>
                  <div className="text-slate-400 italic mt-1">{rb.description}</div>
                </div>
              </Popup>
            </GeoJSON>
          )
        ))}

        {/* 4. AI Detected Changes / Alerts */}
        {showDetections && alerts.map((a) => (
          <React.Fragment key={`alert-${a.id}`}>
            {/* Outline Polygon */}
            {a.geojson && (
              <GeoJSON
                data={a.geojson}
                style={{
                  color: a.risk_level === 'CRITICAL' ? '#ef4444' : a.risk_level === 'HIGH' ? '#f59e0b' : '#06b6d4',
                  weight: 3,
                  opacity: 0.95,
                  fillColor: a.risk_level === 'CRITICAL' ? '#ef4444' : a.risk_level === 'HIGH' ? '#f59e0b' : '#06b6d4',
                  fillOpacity: 0.35
                }}
              />
            )}

            {/* Marker Pin at Centroid */}
            <Marker
              position={[a.centroid_lat, a.centroid_lng]}
              icon={createCustomMarker(a.risk_level)}
            >
              <Popup>
                <div className="p-2 text-xs space-y-2 min-w-[220px]">
                  <div className="flex items-center justify-between">
                    <span className="font-mono font-bold text-emerald-400">{a.alert_code}</span>
                    <RiskBadge level={a.risk_level} score={a.risk_score} />
                  </div>
                  <div className="font-semibold text-white">{a.category.replace('_', ' ')}</div>
                  <div className="text-slate-400">
                    <div>Zone: {a.zone_name}</div>
                    <div>Affected Area: {a.affected_area_sqm.toLocaleString()} m² ({a.affected_area_hectares} ha)</div>
                    <div>Status: <StatusBadge status={a.status} /></div>
                  </div>
                  {onSelectAlert && (
                    <button
                      onClick={() => onSelectAlert(a)}
                      className="w-full mt-2 py-1.5 px-3 bg-emerald-600 hover:bg-emerald-500 text-white rounded font-medium flex items-center justify-center gap-1.5 transition"
                    >
                      <Eye className="w-3.5 h-3.5" /> Inspect Evidence
                    </button>
                  )}
                </div>
              </Popup>
            </Marker>
          </React.Fragment>
        ))}
      </MapContainer>
    </div>
  );
};
