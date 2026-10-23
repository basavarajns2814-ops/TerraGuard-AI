import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import { Alert, MonitoringZone, AlertStatus, RiskLevel } from '../types';
import { RiskBadge } from '../components/RiskBadge';
import { StatusBadge } from '../components/StatusBadge';
import {
  ShieldAlert, Filter, Search, Download, Eye,
  ArrowUpDown, Calendar, MapPin, CheckCircle, FileText
} from 'lucide-react';

export const Alerts: React.FC = () => {
  const navigate = useNavigate();
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [zones, setZones] = useState<MonitoringZone[]>([]);
  const [loading, setLoading] = useState<boolean>(true);

  // Filters
  const [search, setSearch] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [riskFilter, setRiskFilter] = useState<string>('ALL');
  const [zoneFilter, setZoneFilter] = useState<string>('ALL');

  useEffect(() => {
    const fetchAlerts = async () => {
      try {
        const [a, z] = await Promise.all([
          api.getAlerts(),
          api.getZones()
        ]);
        setAlerts(a);
        setZones(z);
      } catch (e) {
        console.error("Error loading alerts:", e);
      } finally {
        setLoading(false);
      }
    };
    fetchAlerts();
  }, []);

  const filteredAlerts = alerts.filter(a => {
    if (statusFilter !== 'ALL' && a.status !== statusFilter) return false;
    if (riskFilter !== 'ALL' && a.risk_level !== riskFilter) return false;
    if (zoneFilter !== 'ALL' && String(a.zone_id) !== zoneFilter) return false;
    if (search.trim()) {
      const q = search.toLowerCase();
      return (
        a.alert_code.toLowerCase().includes(q) ||
        (a.zone_name && a.zone_name.toLowerCase().includes(q)) ||
        (a.parcel_number && a.parcel_number.toLowerCase().includes(q)) ||
        a.category.toLowerCase().includes(q)
      );
    }
    return true;
  });

  return (
    <div className="space-y-6">
      {/* Title & Actions Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b border-slate-800/80">
        <div>
          <h2 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
            Alert Center & Cadastral Encroachment Registry
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Evaluate, prioritize, assign, and verify candidate land-use change incidents.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <a
            href={api.getExportCsvUrl(zoneFilter !== 'ALL' ? Number(zoneFilter) : undefined)}
            download
            className="px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-800 hover:border-slate-700 text-slate-200 text-xs font-medium flex items-center gap-1.5 transition"
          >
            <Download className="w-3.5 h-3.5 text-emerald-400" /> Export CSV
          </a>
          <a
            href={api.getExportPdfUrl(zoneFilter !== 'ALL' ? Number(zoneFilter) : undefined)}
            download
            className="px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold flex items-center gap-1.5 shadow transition"
          >
            <FileText className="w-3.5 h-3.5" /> Export PDF Summary
          </a>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 flex flex-wrap items-center justify-between gap-3 shadow-md">
        <div className="relative flex-1 min-w-[240px]">
          <Search className="w-4 h-4 text-slate-500 absolute left-3.5 top-2.5" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Filter by alert code, zone, parcel, or category..."
            className="w-full bg-slate-950 border border-slate-800 rounded-lg pl-10 pr-3 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-emerald-500"
          />
        </div>

        <div className="flex flex-wrap items-center gap-3 text-xs">
          {/* Zone Filter */}
          <select
            value={zoneFilter}
            onChange={(e) => setZoneFilter(e.target.value)}
            className="bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 focus:outline-none focus:border-emerald-500"
          >
            <option value="ALL">All Monitoring Zones</option>
            {zones.map(z => (
              <option key={z.id} value={z.id}>{z.name}</option>
            ))}
          </select>

          {/* Status Filter */}
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 focus:outline-none focus:border-emerald-500"
          >
            <option value="ALL">All Statuses</option>
            <option value="NEW">New</option>
            <option value="UNDER_REVIEW">Under Review</option>
            <option value="FIELD_INSPECTION_REQUIRED">Inspection Required</option>
            <option value="CONFIRMED">Confirmed</option>
            <option value="DISMISSED">Dismissed</option>
            <option value="RESOLVED">Resolved</option>
          </select>

          {/* Risk Filter */}
          <select
            value={riskFilter}
            onChange={(e) => setRiskFilter(e.target.value)}
            className="bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 focus:outline-none focus:border-emerald-500"
          >
            <option value="ALL">All Risk Levels</option>
            <option value="CRITICAL">Critical</option>
            <option value="HIGH">High</option>
            <option value="MEDIUM">Medium</option>
            <option value="LOW">Low</option>
          </select>
        </div>
      </div>

      {/* Alerts Data Table */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-2xl">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="bg-slate-950/80 border-b border-slate-800 text-slate-400 font-semibold uppercase tracking-wider text-[11px]">
                <th className="py-3 px-4">Alert Code</th>
                <th className="py-3 px-4">Category</th>
                <th className="py-3 px-4">Zone & Parcel</th>
                <th className="py-3 px-4">Risk Severity</th>
                <th className="py-3 px-4">Footprint Area</th>
                <th className="py-3 px-4">Status</th>
                <th className="py-3 px-4">Assigned To</th>
                <th className="py-3 px-4">Acquisition Date</th>
                <th className="py-3 px-4 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/80">
              {loading ? (
                <tr>
                  <td colSpan={9} className="py-12 text-center text-slate-500">
                    Loading registered alerts...
                  </td>
                </tr>
              ) : filteredAlerts.length === 0 ? (
                <tr>
                  <td colSpan={9} className="py-12 text-center text-slate-500">
                    No alerts matching the selected filters.
                  </td>
                </tr>
              ) : (
                filteredAlerts.map((a) => (
                  <tr
                    key={a.id}
                    onClick={() => navigate(`/alerts/${a.id}`)}
                    className="hover:bg-slate-800/50 cursor-pointer transition"
                  >
                    <td className="py-3 px-4 font-mono font-bold text-emerald-400 whitespace-nowrap">
                      {a.alert_code}
                    </td>
                    <td className="py-3 px-4 font-medium text-slate-200">
                      {a.category.replace('_', ' ')}
                    </td>
                    <td className="py-3 px-4 text-slate-300">
                      <div>{a.zone_name}</div>
                      <div className="text-[10px] text-slate-500 font-mono">{a.parcel_number || 'Parcel Unassigned'}</div>
                    </td>
                    <td className="py-3 px-4 whitespace-nowrap">
                      <RiskBadge level={a.risk_level} score={a.risk_score} />
                    </td>
                    <td className="py-3 px-4 font-mono text-cyan-400 whitespace-nowrap">
                      {a.affected_area_sqm.toLocaleString()} m²
                      <span className="text-[10px] text-slate-500 ml-1">({a.affected_area_hectares} ha)</span>
                    </td>
                    <td className="py-3 px-4 whitespace-nowrap">
                      <StatusBadge status={a.status} />
                    </td>
                    <td className="py-3 px-4 text-slate-400 whitespace-nowrap">
                      {a.assigned_to_name || 'Unassigned'}
                    </td>
                    <td className="py-3 px-4 font-mono text-slate-400 whitespace-nowrap">
                      {a.latest_observed_date}
                    </td>
                    <td className="py-3 px-4 text-right whitespace-nowrap">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          navigate(`/alerts/${a.id}`);
                        }}
                        className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white transition"
                        title="View Detailed Evidence"
                      >
                        <Eye className="w-4 h-4" />
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
