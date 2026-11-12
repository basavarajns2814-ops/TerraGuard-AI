import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import { MonitoringZone, LandParcel, RestrictedBoundary } from '../types';
import { useAuth } from '../context/AuthContext';
import {
  Layers, MapPin, ShieldAlert, Plus, CheckCircle,
  Building, Compass, ArrowRight, X, Trash2, Satellite, Map as MapIcon
} from 'lucide-react';

export const MonitoringAreas: React.FC = () => {
  const navigate = useNavigate();
  const { isAdmin } = useAuth();
  const [zones, setZones] = useState<MonitoringZone[]>([]);
  const [parcels, setParcels] = useState<LandParcel[]>([]);
  const [boundaries, setBoundaries] = useState<RestrictedBoundary[]>([]);
  const [activeTab, setActiveTab] = useState<'ZONES' | 'PARCELS' | 'BOUNDARIES'>('ZONES');
  const [loading, setLoading] = useState<boolean>(true);

  // New Zone Modal
  const [showZoneModal, setShowZoneModal] = useState<boolean>(false);
  const [newZoneName, setNewZoneName] = useState<string>('');
  const [newDistrict, setNewDistrict] = useState<string>('Bengaluru Urban');
  const [newAreaHa, setNewAreaHa] = useState<number>(100);
  const [newDescription, setNewDescription] = useState<string>('');
  const [customGeoJSON, setCustomGeoJSON] = useState<string>('');
  const [submittingZone, setSubmittingZone] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string>('');

  useEffect(() => {
    loadAreas();
  }, []);

  const loadAreas = async () => {
    try {
      setLoading(true);
      const [z, p, b] = await Promise.all([
        api.getZones(),
        api.getParcels(),
        api.getRestrictedBoundaries()
      ]);
      setZones(z);
      setParcels(p);
      setBoundaries(b);
    } catch (e) {
      console.error("Areas loading error:", e);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateZone = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmittingZone(true);
    setErrorMessage('');

    let geojsonPayload: any = null;
    if (customGeoJSON.trim()) {
      try {
        geojsonPayload = JSON.parse(customGeoJSON);
      } catch (err) {
        setErrorMessage("Invalid GeoJSON JSON structure.");
        setSubmittingZone(false);
        return;
      }
    } else {
      // Default bounding polygon around specified district
      geojsonPayload = {
        type: "Polygon",
        coordinates: [[
          [77.6500, 12.9200],
          [77.7000, 12.9200],
          [77.7000, 12.9600],
          [77.6500, 12.9600],
          [77.6500, 12.9200]
        ]]
      };
    }

    try {
      const created = await api.createZone({
        name: newZoneName.trim(),
        district: newDistrict.trim(),
        state: 'Karnataka',
        area_hectares: Number(newAreaHa) || 0,
        description: newDescription.trim(),
        geojson: geojsonPayload
      });
      setZones([created, ...zones]);
      setShowZoneModal(false);
      setNewZoneName('');
      setNewDescription('');
      setCustomGeoJSON('');
    } catch (e: any) {
      setErrorMessage(e.message || "Failed to create monitoring zone");
    } finally {
      setSubmittingZone(false);
    }
  };

  const handleDeleteZone = async (zone: MonitoringZone) => {
    if (!window.confirm(`Are you sure you want to delete monitoring area "${zone.name}"?`)) {
      return;
    }
    try {
      await api.deleteZone(zone.id);
      setZones(prev => prev.filter(z => z.id !== zone.id));
    } catch (err: any) {
      alert(err.message || "Failed to delete monitoring zone");
    }
  };

  return (
    <div className="space-y-6">
      {/* Title & Actions Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b border-slate-800/80">
        <div>
          <h2 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
            Jurisdictional Monitoring Zones & Cadastral Parcels
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Configure surveillance areas, legal boundaries, and protected statutory buffer corridors in Karnataka.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => navigate('/gis')}
            className="px-3.5 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold flex items-center gap-1.5 border border-slate-700 transition"
          >
            <MapIcon className="w-4 h-4 text-cyan-400" /> Open Interactive GIS Map
          </button>
          <button
            onClick={() => setShowZoneModal(true)}
            className="px-3.5 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold flex items-center gap-1.5 shadow transition"
          >
            <Plus className="w-4 h-4" /> Add Monitoring Zone
          </button>
        </div>
      </div>

      {/* Navigation Tabs */}
      <div className="flex items-center gap-2 border-b border-slate-800">
        <button
          onClick={() => setActiveTab('ZONES')}
          className={`px-4 py-2 text-xs font-semibold border-b-2 transition ${
            activeTab === 'ZONES'
              ? 'border-emerald-500 text-emerald-400'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          Monitoring Zones ({zones.length})
        </button>
        <button
          onClick={() => setActiveTab('PARCELS')}
          className={`px-4 py-2 text-xs font-semibold border-b-2 transition ${
            activeTab === 'PARCELS'
              ? 'border-emerald-500 text-emerald-400'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          Cadastral Land Parcels ({parcels.length})
        </button>
        <button
          onClick={() => setActiveTab('BOUNDARIES')}
          className={`px-4 py-2 text-xs font-semibold border-b-2 transition ${
            activeTab === 'BOUNDARIES'
              ? 'border-emerald-500 text-emerald-400'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          Restricted Buffer Zones ({boundaries.length})
        </button>
      </div>

      {/* Content for Active Tab */}
      {activeTab === 'ZONES' && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {zones.length === 0 ? (
            <div className="col-span-2 text-center py-16 text-slate-500 text-xs">
              No monitoring areas registered yet. Click "Open Interactive GIS Map" to draw a boundary on the live satellite map.
            </div>
          ) : (
            zones.map((z) => (
              <div key={z.id} className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-xl space-y-3 flex flex-col justify-between">
                <div className="space-y-2">
                  <div className="flex items-start justify-between">
                    <div>
                      <h3 className="text-base font-bold text-white">{z.name}</h3>
                      <p className="text-xs text-slate-400 flex items-center gap-1 mt-0.5">
                        <MapPin className="w-3.5 h-3.5 text-cyan-400" />
                        {z.district}, {z.state}
                      </p>
                    </div>
                    <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${
                      z.risk_status === 'CRITICAL' ? 'bg-red-500/10 text-red-400 border-red-500/30' : 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
                    }`}>
                      {z.risk_status} RISK
                    </span>
                  </div>

                  {z.description && <p className="text-xs text-slate-300 leading-relaxed">{z.description}</p>}

                  <div className="grid grid-cols-3 gap-2 pt-2 border-t border-slate-800/80 text-xs text-slate-400">
                    <div>
                      <span className="text-[10px] text-slate-500 uppercase block">Area Scope</span>
                      <span className="font-mono text-white font-bold">{z.area_hectares} ha</span>
                    </div>
                    <div>
                      <span className="text-[10px] text-slate-500 uppercase block">Parcels</span>
                      <span className="font-mono text-cyan-400 font-bold">{z.parcels_count ?? 0}</span>
                    </div>
                    <div>
                      <span className="text-[10px] text-slate-500 uppercase block">Active Alerts</span>
                      <span className="font-mono text-amber-400 font-bold">{z.alerts_count ?? 0}</span>
                    </div>
                  </div>
                </div>

                {/* Actions */}
                <div className="flex items-center gap-2 pt-3 border-t border-slate-800/80">
                  <button
                    onClick={() => navigate('/gis')}
                    className="flex-1 py-1.5 px-2.5 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs rounded-lg font-medium flex items-center justify-center gap-1.5 transition"
                  >
                    <MapIcon className="w-3.5 h-3.5 text-cyan-400" /> View on Map
                  </button>
                  <button
                    onClick={() => navigate(`/imagery?zone_id=${z.id}`)}
                    className="flex-1 py-1.5 px-2.5 bg-emerald-950/60 hover:bg-emerald-900 border border-emerald-800/60 text-emerald-300 text-xs rounded-lg font-medium flex items-center justify-center gap-1.5 transition"
                  >
                    <Satellite className="w-3.5 h-3.5" /> Acquire Scenes
                  </button>
                  <button
                    onClick={() => handleDeleteZone(z)}
                    className="p-1.5 bg-rose-950/40 hover:bg-rose-900/80 border border-rose-800/40 text-rose-400 rounded-lg transition"
                    title="Delete Monitoring Area"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {activeTab === 'PARCELS' && (
        <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-2xl">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-950/80 border-b border-slate-800 text-slate-400 uppercase tracking-wider text-[11px]">
              <tr>
                <th className="py-3 px-4">Parcel Number</th>
                <th className="py-3 px-4">Ownership Status</th>
                <th className="py-3 px-4">Authorized Land Use</th>
                <th className="py-3 px-4">Area (m²)</th>
                <th className="py-3 px-4">Area (Hectares)</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/80">
              {parcels.length === 0 ? (
                <tr>
                  <td colSpan={5} className="py-8 text-center text-slate-500">No cadastral parcels loaded.</td>
                </tr>
              ) : (
                parcels.map((p) => (
                  <tr key={p.id} className="hover:bg-slate-800/40">
                    <td className="py-3 px-4 font-mono font-bold text-emerald-400">{p.parcel_number}</td>
                    <td className="py-3 px-4 font-semibold text-slate-200">{p.owner_type.replace('_', ' ')}</td>
                    <td className="py-3 px-4 text-slate-300">{p.authorized_use}</td>
                    <td className="py-3 px-4 font-mono text-slate-200">{p.area_sqm.toLocaleString()}</td>
                    <td className="py-3 px-4 font-mono text-cyan-400">{p.area_hectares} ha</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}

      {activeTab === 'BOUNDARIES' && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {boundaries.length === 0 ? (
            <div className="col-span-2 text-center py-16 text-slate-500 text-xs">No statutory buffer corridors registered.</div>
          ) : (
            boundaries.map((b) => (
              <div key={b.id} className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-xl space-y-2">
                <div className="flex items-center justify-between">
                  <h4 className="text-sm font-bold text-rose-400 flex items-center gap-1.5">
                    <ShieldAlert className="w-4 h-4" /> {b.name}
                  </h4>
                  <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-rose-500/10 text-rose-300 border border-rose-500/30">
                    {b.boundary_type.replace('_', ' ')}
                  </span>
                </div>
                <p className="text-xs text-slate-300">{b.description}</p>
                <div className="text-xs text-slate-400 pt-2 border-t border-slate-800 font-mono">
                  Statutory Non-Construction Buffer: <strong className="text-white">{b.buffer_distance_meters} meters</strong>
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {/* Add Zone Modal */}
      {showZoneModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between pb-2 border-b border-slate-800">
              <h3 className="text-sm font-bold text-white flex items-center gap-2">
                <Plus className="w-4 h-4 text-emerald-400" /> Register Monitoring Zone
              </h3>
              <button onClick={() => setShowZoneModal(false)} className="text-slate-400 hover:text-white">
                <X className="w-4 h-4" />
              </button>
            </div>

            {errorMessage && (
              <div className="p-2.5 rounded bg-rose-950/60 border border-rose-800 text-rose-300 text-xs">
                {errorMessage}
              </div>
            )}

            <form onSubmit={handleCreateZone} className="space-y-3 text-xs">
              <div>
                <label className="block text-slate-300 font-medium mb-1">Zone Name *</label>
                <input
                  type="text"
                  required
                  value={newZoneName}
                  onChange={(e) => setNewZoneName(e.target.value)}
                  placeholder="e.g. Bellandur Wetland Surveillance Corridor"
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-emerald-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-300 font-medium mb-1">District</label>
                  <select
                    value={newDistrict}
                    onChange={(e) => setNewDistrict(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-emerald-500"
                  >
                    <option value="Bengaluru Urban">Bengaluru Urban</option>
                    <option value="Bengaluru Rural">Bengaluru Rural</option>
                    <option value="Mysuru">Mysuru</option>
                    <option value="Ramanagara">Ramanagara</option>
                    <option value="Dharwad">Dharwad</option>
                  </select>
                </div>
                <div>
                  <label className="block text-slate-300 font-medium mb-1">Area (Hectares)</label>
                  <input
                    type="number"
                    step="0.01"
                    value={newAreaHa}
                    onChange={(e) => setNewAreaHa(Number(e.target.value))}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-emerald-500"
                  />
                </div>
              </div>

              <div>
                <label className="block text-slate-300 font-medium mb-1">Description</label>
                <textarea
                  rows={2}
                  value={newDescription}
                  onChange={(e) => setNewDescription(e.target.value)}
                  placeholder="Description of the monitored zone..."
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-emerald-500"
                />
              </div>

              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="text-slate-300 font-medium">Custom GeoJSON Polygon (Optional)</label>
                  <button
                    type="button"
                    onClick={() => {
                      setShowZoneModal(false);
                      navigate('/gis');
                    }}
                    className="text-cyan-400 hover:text-cyan-300 text-[10px] underline"
                  >
                    Draw on map instead &rarr;
                  </button>
                </div>
                <textarea
                  rows={3}
                  value={customGeoJSON}
                  onChange={(e) => setCustomGeoJSON(e.target.value)}
                  placeholder='{"type": "Polygon", "coordinates": [[[77.65, 12.92], ...]]}'
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-white font-mono text-[10px] focus:outline-none focus:border-emerald-500"
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setShowZoneModal(false)}
                  className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg font-medium transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submittingZone}
                  className="px-4 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg font-semibold shadow transition"
                >
                  {submittingZone ? 'Registering...' : 'Register Zone'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
