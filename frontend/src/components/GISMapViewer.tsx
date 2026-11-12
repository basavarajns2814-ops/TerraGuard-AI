import React, { useState, useEffect } from 'react';
import {
  MapContainer, TileLayer, Polygon, Polyline, Marker, Popup,
  GeoJSON, useMap, useMapEvents
} from 'react-leaflet';
import L from 'leaflet';
import { MonitoringZone, LandParcel, RestrictedBoundary, DetectedChange, Alert } from '../types';
import { RiskBadge } from './RiskBadge';
import { StatusBadge } from './StatusBadge';
import { Layers, ShieldAlert, Eye, MapPin, Globe, Compass, Edit3, XCircle, CheckCircle } from 'lucide-react';

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

// Custom vertex handle marker for interactive polygon drawing
const createVertexIcon = (isFirst: boolean) =>
  L.divIcon({
    className: 'custom-vertex-marker',
    html: `
      <div style="
        width: ${isFirst ? '18px' : '14px'};
        height: ${isFirst ? '18px' : '14px'};
        border-radius: 50%;
        background-color: ${isFirst ? '#10b981' : '#38bdf8'};
        border: 2px solid #ffffff;
        box-shadow: 0 0 8px ${isFirst ? '#10b981' : '#38bdf8'};
        cursor: ${isFirst ? 'pointer' : 'grab'};
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 9px;
        font-weight: bold;
        color: white;
      ">${isFirst ? '●' : ''}</div>
    `,
    iconSize: isFirst ? [18, 18] : [14, 14],
    iconAnchor: isFirst ? [9, 9] : [7, 7]
  });

export interface GISMapViewerProps {
  zones?: MonitoringZone[];
  parcels?: LandParcel[];
  restrictedBoundaries?: RestrictedBoundary[];
  changes?: DetectedChange[];
  alerts?: Alert[];
  onSelectAlert?: (alert: Alert) => void;
  onSelectChange?: (change: DetectedChange) => void;
  onSelectZone?: (zone: MonitoringZone) => void;
  center?: [number, number];
  zoom?: number;
  height?: string;
  focusedCoordinates?: [number, number];
  // Drawing mode properties
  isDrawing?: boolean;
  drawingPoints?: [number, number][];
  onAddDrawingPoint?: (point: [number, number]) => void;
  onUpdateDrawingPoint?: (index: number, point: [number, number]) => void;
  onCloseDrawingPolygon?: () => void;
  selectedZoneId?: number | null;
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

// Map click listener for interactive polygon drawing
const MapDrawingEvents: React.FC<{
  isDrawing: boolean;
  onAddPoint?: (point: [number, number]) => void;
}> = ({ isDrawing, onAddPoint }) => {
  useMapEvents({
    click(e) {
      if (isDrawing && onAddPoint) {
        onAddPoint([e.latlng.lat, e.latlng.lng]);
      }
    },
  });
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
  onSelectZone,
  center = [12.9352, 77.6741], // Default Bellandur Lake, Bengaluru
  zoom = 13,
  height = '600px',
  focusedCoordinates,
  isDrawing = false,
  drawingPoints = [],
  onAddDrawingPoint,
  onUpdateDrawingPoint,
  onCloseDrawingPolygon,
  selectedZoneId
}) => {
  const [showZones, setShowZones] = useState<boolean>(true);
  const [showParcels, setShowParcels] = useState<boolean>(true);
  const [showRestricted, setShowRestricted] = useState<boolean>(true);
  const [showDetections, setShowDetections] = useState<boolean>(true);
  const [basemap, setBasemap] = useState<'dark' | 'satellite' | 'streets'>('satellite');

  return (
    <div
      className={`relative w-full rounded-xl overflow-hidden border border-slate-800 shadow-2xl ${
        isDrawing ? 'cursor-crosshair' : ''
      }`}
      style={{ height }}
    >
      {/* Floating Basemap & Layer Controls */}
      <div className="absolute top-4 right-4 z-[1000] bg-slate-900/90 backdrop-blur border border-slate-800 rounded-lg p-3 shadow-xl text-xs space-y-2.5 max-w-[210px]">
        {/* Basemap Switcher */}
        <div>
          <div className="font-semibold text-slate-300 flex items-center gap-1.5 pb-1 border-b border-slate-800 mb-1.5">
            <Globe className="w-3.5 h-3.5 text-cyan-400" /> Basemap Provider
          </div>
          <div className="grid grid-cols-3 gap-1">
            <button
              type="button"
              onClick={() => setBasemap('satellite')}
              className={`py-1 px-1.5 rounded text-[10px] font-semibold transition ${
                basemap === 'satellite'
                  ? 'bg-emerald-600 text-white shadow'
                  : 'bg-slate-950 text-slate-400 hover:text-white'
              }`}
            >
              Satellite
            </button>
            <button
              type="button"
              onClick={() => setBasemap('dark')}
              className={`py-1 px-1.5 rounded text-[10px] font-semibold transition ${
                basemap === 'dark'
                  ? 'bg-emerald-600 text-white shadow'
                  : 'bg-slate-950 text-slate-400 hover:text-white'
              }`}
            >
              Dark GIS
            </button>
            <button
              type="button"
              onClick={() => setBasemap('streets')}
              className={`py-1 px-1.5 rounded text-[10px] font-semibold transition ${
                basemap === 'streets'
                  ? 'bg-emerald-600 text-white shadow'
                  : 'bg-slate-950 text-slate-400 hover:text-white'
              }`}
            >
              Streets
            </button>
          </div>
        </div>

        {/* Layer Overlays */}
        <div className="pt-1 border-t border-slate-800 space-y-1.5">
          <div className="font-semibold text-slate-300 flex items-center gap-1.5 pb-1">
            <Layers className="w-3.5 h-3.5 text-emerald-400" /> Overlays
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
            Parcels ({parcels.length})
          </label>
          <label className="flex items-center gap-2 cursor-pointer text-slate-300 hover:text-white">
            <input
              type="checkbox"
              checked={showRestricted}
              onChange={(e) => setShowRestricted(e.target.checked)}
              className="rounded accent-emerald-500"
            />
            <span className="w-2.5 h-2.5 rounded-sm bg-rose-500/80 inline-block border border-rose-400" />
            Buffers ({restrictedBoundaries.length})
          </label>
          <label className="flex items-center gap-2 cursor-pointer text-slate-300 hover:text-white">
            <input
              type="checkbox"
              checked={showDetections}
              onChange={(e) => setShowDetections(e.target.checked)}
              className="rounded accent-emerald-500"
            />
            <span className="w-2.5 h-2.5 rounded-full bg-red-500 inline-block border border-white" />
            Detections ({alerts.length || changes.length})
          </label>
        </div>
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
        <MapDrawingEvents isDrawing={isDrawing} onAddPoint={onAddDrawingPoint} />

        {/* Basemap Selection */}
        {basemap === 'satellite' && (
          <TileLayer
            attribution='&copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community'
            url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
            maxZoom={18}
          />
        )}
        {basemap === 'dark' && (
          <TileLayer
            attribution='&copy; <a href="https://carto.com/">CARTO</a> &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
            url="https://{s}.basemaps.cartocdn.com/rastertiles/dark_all/{z}/{x}/{y}{r}.png"
            maxZoom={19}
          />
        )}
        {basemap === 'streets' && (
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            maxZoom={19}
          />
        )}

        {/* 1. Monitoring Zones Layer */}
        {showZones && zones.map((z) => {
          const isSelected = selectedZoneId === z.id;
          return (
            z.geojson && (
              <GeoJSON
                key={`zone-${z.id}-${isSelected ? 'sel' : 'norm'}`}
                data={z.geojson}
                style={{
                  color: isSelected ? '#10b981' : '#06b6d4',
                  weight: isSelected ? 3.5 : 2,
                  opacity: isSelected ? 1 : 0.8,
                  fillColor: isSelected ? '#10b981' : '#06b6d4',
                  fillOpacity: isSelected ? 0.2 : 0.08,
                  dashArray: isSelected ? undefined : '4, 4'
                }}
                eventHandlers={{
                  click: () => {
                    if (onSelectZone) onSelectZone(z);
                  }
                }}
              >
                <Popup>
                  <div className="p-2 text-xs">
                    <div className="font-bold text-cyan-400 text-sm flex items-center justify-between gap-2">
                      <span>{z.name}</span>
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-cyan-950 border border-cyan-800 text-cyan-300 font-mono">
                        ID: {z.id}
                      </span>
                    </div>
                    <div className="text-slate-300 mt-1">District: {z.district}, {z.state}</div>
                    <div className="text-slate-400 font-semibold mt-0.5">Monitored Area: {z.area_hectares} ha</div>
                    {z.description && <div className="text-slate-400 italic text-[11px] mt-1">{z.description}</div>}
                    {onSelectZone && (
                      <button
                        onClick={() => onSelectZone(z)}
                        className="mt-2.5 w-full py-1 px-2 bg-cyan-600 hover:bg-cyan-500 text-white rounded font-medium flex items-center justify-center gap-1 transition"
                      >
                        <Compass className="w-3.5 h-3.5" /> Select Zone Details
                      </button>
                    )}
                  </div>
                </Popup>
              </GeoJSON>
            )
          );
        })}

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

        {/* 3. Restricted Boundaries Layer */}
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

        {/* 4. Active Interactive Drawing Polygon & Vertices */}
        {isDrawing && drawingPoints.length > 0 && (
          <>
            {/* Filled polygon preview when >= 3 points */}
            {drawingPoints.length >= 3 && (
              <Polygon
                positions={drawingPoints}
                pathOptions={{
                  color: '#10b981',
                  weight: 2.5,
                  fillColor: '#10b981',
                  fillOpacity: 0.28,
                  dashArray: '4, 4'
                }}
              />
            )}

            {/* Polyline outline */}
            {drawingPoints.length >= 2 && (
              <Polyline
                positions={drawingPoints}
                pathOptions={{
                  color: '#34d399',
                  weight: 3,
                  dashArray: '6, 6'
                }}
              />
            )}

            {/* Draggable vertex handles */}
            {drawingPoints.map((pt, idx) => (
              <Marker
                key={`draw-pt-${idx}`}
                position={pt}
                draggable={true}
                icon={createVertexIcon(idx === 0)}
                eventHandlers={{
                  dragend: (e) => {
                    const marker = e.target;
                    const pos = marker.getLatLng();
                    if (onUpdateDrawingPoint) {
                      onUpdateDrawingPoint(idx, [pos.lat, pos.lng]);
                    }
                  },
                  click: () => {
                    if (idx === 0 && drawingPoints.length >= 3 && onCloseDrawingPolygon) {
                      onCloseDrawingPolygon();
                    }
                  }
                }}
              >
                <Popup>
                  <div className="p-1 text-[11px]">
                    <div className="font-bold text-emerald-400">Vertex #{idx + 1}</div>
                    <div className="font-mono text-slate-300">{pt[0].toFixed(5)}, {pt[1].toFixed(5)}</div>
                    {idx === 0 && drawingPoints.length >= 3 && (
                      <div className="text-emerald-300 text-[10px] mt-1 font-semibold">
                        Click to close polygon boundary
                      </div>
                    )}
                  </div>
                </Popup>
              </Marker>
            ))}
          </>
        )}

        {/* 5. AI Detected Changes / Alerts */}
        {showDetections && changes
          .filter((change) => !alerts.some((alert) => alert.change_id === change.id))
          .map((change) => change.geojson && (
            <GeoJSON
              key={`change-${change.id}`}
              data={change.geojson}
              style={{ color: '#22d3ee', weight: 3, opacity: 0.95, fillColor: '#06b6d4', fillOpacity: 0.3 }}
            >
              <Popup>
                <div className="p-2 text-xs space-y-1 min-w-[190px]">
                  <div className="font-semibold text-cyan-300">Candidate change #{change.id}</div>
                  <div>{change.category.replace(/_/g, ' ')}</div>
                  <div>Affected area: {change.affected_area_hectares.toFixed(3)} ha</div>
                  <div>SNUNet mean pixel score: {change.model_mean_probability == null ? 'Unavailable' : `${(change.model_mean_probability * 100).toFixed(1)}%`}</div>
                  <div>Composite risk confidence: {(change.confidence_score * 100).toFixed(1)}%</div>
                  <div>Scenes: {change.first_observed_date} → {change.latest_observed_date}</div>
                  <div className="text-amber-300">Candidate only; field verification required.</div>
                </div>
              </Popup>
            </GeoJSON>
          ))}
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
                    <div>SNUNet mean pixel score: {changes.find((change) => change.id === a.change_id)?.model_mean_probability == null ? 'Unavailable' : `${((changes.find((change) => change.id === a.change_id)!.model_mean_probability as number) * 100).toFixed(1)}%`}</div>
                    <div>Composite risk confidence: {(a.confidence_score * 100).toFixed(1)}%</div>
                    <div>Scenes: {a.first_observed_date} → {a.latest_observed_date}</div>
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
