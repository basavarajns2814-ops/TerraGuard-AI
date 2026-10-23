import React, { useState, useEffect } from 'react';
import { api } from '../api/client';
import { SystemSettings, AuditLog } from '../types';
import { useAuth } from '../context/AuthContext';
import {
  Settings as SettingsIcon, Sliders, Shield, History,
  Save, CheckCircle, RefreshCw, AlertTriangle
} from 'lucide-react';

export const Settings: React.FC = () => {
  const { isAdmin } = useAuth();
  const [settings, setSettings] = useState<SystemSettings>({
    detection_threshold_ndvi: 0.22,
    detection_threshold_ndbi: 0.18,
    min_change_area_sqm: 120.0,
    risk_weight_boundary: 40.0,
    risk_weight_area: 30.0,
    risk_weight_persistence: 30.0,
    auto_alert_high_risk: true,
    copernicus_enabled: false,
    demo_mode: true
  });
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([]);
  const [saving, setSaving] = useState<boolean>(false);
  const [savedSuccess, setSavedSuccess] = useState<boolean>(false);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    const loadSettings = async () => {
      try {
        const s = await api.getSettings();
        setSettings(s);
        if (isAdmin) {
          const logs = await api.getAuditLogs();
          setAuditLogs(logs);
        }
      } catch (e) {
        console.error("Settings load error:", e);
      } finally {
        setLoading(false);
      }
    };
    loadSettings();
  }, [isAdmin]);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setSavedSuccess(false);
    try {
      const updated = await api.updateSettings(settings);
      setSettings(updated);
      setSavedSuccess(true);
      setTimeout(() => setSavedSuccess(false), 3000);
    } catch (e: any) {
      alert(e.message || "Failed to update settings");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      {/* Title Header */}
      <div className="flex items-center justify-between pb-2 border-b border-slate-800/80">
        <div>
          <h2 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
            System Configuration & Operational Thresholds
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Calibrate AI detection sensitivity, risk factor weights, and inspection dispatch triggers.
          </p>
        </div>

        {savedSuccess && (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 text-xs font-semibold animate-pulse">
            <CheckCircle className="w-3.5 h-3.5" /> Settings Saved Successfully
          </span>
        )}
      </div>

      <form onSubmit={handleSave} className="space-y-6">
        {/* Detection Sensitivity Settings */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-xl space-y-4">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-300 flex items-center gap-2">
            <Sliders className="w-4 h-4 text-emerald-400" /> AI Change Detection Sensitivity
          </h3>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
            <div>
              <label className="block text-slate-300 font-medium mb-1">
                NDVI Vegetation Drop Threshold
              </label>
              <input
                type="number"
                step="0.01"
                disabled={!isAdmin}
                value={settings.detection_threshold_ndvi}
                onChange={(e) => setSettings({ ...settings, detection_threshold_ndvi: parseFloat(e.target.value) })}
                className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-white focus:outline-none focus:border-emerald-500 font-mono disabled:opacity-50"
              />
              <span className="text-[10px] text-slate-500 mt-1 block">Default: 0.22 (Reflectance difference)</span>
            </div>

            <div>
              <label className="block text-slate-300 font-medium mb-1">
                NDBI Structural Built-up Threshold
              </label>
              <input
                type="number"
                step="0.01"
                disabled={!isAdmin}
                value={settings.detection_threshold_ndbi}
                onChange={(e) => setSettings({ ...settings, detection_threshold_ndbi: parseFloat(e.target.value) })}
                className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-white focus:outline-none focus:border-emerald-500 font-mono disabled:opacity-50"
              />
              <span className="text-[10px] text-slate-500 mt-1 block">Default: 0.18 (Built-up index sensitivity)</span>
            </div>

            <div>
              <label className="block text-slate-300 font-medium mb-1">
                Minimum Candidate Footprint (m²)
              </label>
              <input
                type="number"
                disabled={!isAdmin}
                value={settings.min_change_area_sqm}
                onChange={(e) => setSettings({ ...settings, min_change_area_sqm: parseFloat(e.target.value) })}
                className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-white focus:outline-none focus:border-emerald-500 font-mono disabled:opacity-50"
              />
              <span className="text-[10px] text-slate-500 mt-1 block">Excludes minor noise below 120 m²</span>
            </div>
          </div>
        </div>

        {/* Explainable Risk Scoring Weights */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-xl space-y-4">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-300 flex items-center gap-2">
            <Shield className="w-4 h-4 text-cyan-400" /> Explainable Risk Formula Weight Allocation
          </h3>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
            <div>
              <label className="block text-slate-300 font-medium mb-1">
                Restricted Buffer Intersection Weight
              </label>
              <input
                type="number"
                disabled={!isAdmin}
                value={settings.risk_weight_boundary}
                onChange={(e) => setSettings({ ...settings, risk_weight_boundary: parseFloat(e.target.value) })}
                className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-white focus:outline-none focus:border-emerald-500 font-mono disabled:opacity-50"
              />
              <span className="text-[10px] text-slate-500 mt-1 block">Points for Lake Buffer / Forest overlap</span>
            </div>

            <div>
              <label className="block text-slate-300 font-medium mb-1">
                Footprint Magnitude Weight
              </label>
              <input
                type="number"
                disabled={!isAdmin}
                value={settings.risk_weight_area}
                onChange={(e) => setSettings({ ...settings, risk_weight_area: parseFloat(e.target.value) })}
                className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-white focus:outline-none focus:border-emerald-500 font-mono disabled:opacity-50"
              />
              <span className="text-[10px] text-slate-500 mt-1 block">Points scaling with affected square meters</span>
            </div>

            <div>
              <label className="block text-slate-300 font-medium mb-1">
                Multi-Date Persistence Weight
              </label>
              <input
                type="number"
                disabled={!isAdmin}
                value={settings.risk_weight_persistence}
                onChange={(e) => setSettings({ ...settings, risk_weight_persistence: parseFloat(e.target.value) })}
                className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-white focus:outline-none focus:border-emerald-500 font-mono disabled:opacity-50"
              />
              <span className="text-[10px] text-slate-500 mt-1 block">Points for observed repeated expansions</span>
            </div>
          </div>
        </div>

        {/* Integration Status & Flags */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-xl space-y-3">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-300 flex items-center gap-2">
            <CheckCircle className="w-4 h-4 text-emerald-400" /> Operational Integration Environment
          </h3>

          <div className="space-y-3 text-xs">
            <label className="flex items-center gap-2.5 cursor-pointer text-slate-300">
              <input
                type="checkbox"
                disabled={!isAdmin}
                checked={settings.auto_alert_high_risk}
                onChange={(e) => setSettings({ ...settings, auto_alert_high_risk: e.target.checked })}
                className="rounded accent-emerald-500"
              />
              <span>Automatically generate Critical Alerts and notify monitoring officers upon pipeline completion</span>
            </label>

            <div className="p-3 bg-slate-950 rounded-lg border border-slate-800 flex items-center justify-between text-xs text-slate-400">
              <div>
                <span className="text-white font-semibold block">Copernicus Data Space Ecosystem (CDSE) Connector</span>
                <span className="text-[11px]">ESA Sentinel-2 OData API & STAC Catalogue</span>
              </div>
              <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-slate-800 text-slate-300">
                {settings.copernicus_enabled ? 'ONLINE' : 'DEMO MODE (LOCAL REPO)'}
              </span>
            </div>
          </div>
        </div>

        {isAdmin && (
          <div className="flex justify-end">
            <button
              type="submit"
              disabled={saving}
              className="px-5 py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg font-semibold text-xs flex items-center gap-2 shadow-lg transition"
            >
              <Save className="w-4 h-4" />
              {saving ? 'Updating Settings...' : 'Save Configuration Changes'}
            </button>
          </div>
        )}
      </form>

      {/* Admin Audit Logs */}
      {isAdmin && (
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-xl space-y-3">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-300 flex items-center gap-2">
            <History className="w-4 h-4 text-amber-400" /> Administrative Audit Trail ({auditLogs.length})
          </h3>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-950 border-b border-slate-800 text-slate-400 text-[11px]">
                <tr>
                  <th className="py-2.5 px-3">Timestamp</th>
                  <th className="py-2.5 px-3">Officer Email</th>
                  <th className="py-2.5 px-3">Action</th>
                  <th className="py-2.5 px-3">Target Resource</th>
                  <th className="py-2.5 px-3">Audit Details</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/80">
                {auditLogs.slice(0, 10).map((l) => (
                  <tr key={l.id} className="hover:bg-slate-800/40">
                    <td className="py-2.5 px-3 font-mono text-slate-400 text-[10px]">
                      {l.timestamp?.slice(0, 19).replace('T', ' ')}
                    </td>
                    <td className="py-2.5 px-3 font-medium text-slate-200">{l.user_email}</td>
                    <td className="py-2.5 px-3 font-mono text-emerald-400">{l.action}</td>
                    <td className="py-2.5 px-3 text-slate-400">{l.resource_type} #{l.resource_id}</td>
                    <td className="py-2.5 px-3 text-slate-300 text-[11px]">{l.details}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};
