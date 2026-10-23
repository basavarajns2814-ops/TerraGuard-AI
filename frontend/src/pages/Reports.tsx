import React, { useState, useEffect } from 'react';
import { api } from '../api/client';
import { MonitoringZone } from '../types';
import {
  FileText, Download, Filter, Calendar, ShieldAlert,
  BarChart2, CheckCircle, PieChart as PieIcon, ArrowDownToLine
} from 'lucide-react';
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, Cell
} from 'recharts';

export const Reports: React.FC = () => {
  const [zones, setZones] = useState<MonitoringZone[]>([]);
  const [selectedZone, setSelectedZone] = useState<string>('ALL');
  const [summary, setSummary] = useState<any>(null);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    const loadReportData = async () => {
      try {
        const [z, s] = await Promise.all([
          api.getZones(),
          api.getReportsSummary()
        ]);
        setZones(z);
        setSummary(s);
      } catch (e) {
        console.error("Error loading report summary:", e);
      } finally {
        setLoading(false);
      }
    };
    loadReportData();
  }, []);

  const handleZoneChange = async (zoneId: string) => {
    setSelectedZone(zoneId);
    setLoading(true);
    try {
      const s = await api.getReportsSummary(zoneId === 'ALL' ? undefined : Number(zoneId));
      setSummary(s);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const categoryChartData = summary?.by_category
    ? Object.entries(summary.by_category).map(([name, count]) => ({
        name: name.replace(/_/g, ' '),
        count
      }))
    : [];

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Title & Exports Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b border-slate-800/80">
        <div>
          <h2 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
            Regulatory Intelligence & Audit Reporting
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Download certified audit records and summary intelligence dossiers for statutory action.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <a
            href={api.getExportCsvUrl(selectedZone !== 'ALL' ? Number(selectedZone) : undefined)}
            download
            className="px-3.5 py-2 rounded-lg bg-slate-900 border border-slate-800 hover:border-slate-700 text-slate-200 text-xs font-semibold flex items-center gap-2 transition"
          >
            <Download className="w-4 h-4 text-emerald-400" /> Export CSV Data
          </a>
          <a
            href={api.getExportPdfUrl(selectedZone !== 'ALL' ? Number(selectedZone) : undefined)}
            download
            className="px-3.5 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold flex items-center gap-2 shadow-lg transition"
          >
            <ArrowDownToLine className="w-4 h-4" /> Generate Official PDF Dossier
          </a>
        </div>
      </div>

      {/* Filter Toolbar */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 flex items-center justify-between shadow-md text-xs">
        <div className="flex items-center gap-2 text-slate-300">
          <Filter className="w-4 h-4 text-emerald-400" />
          <span className="font-semibold">Filter Report Scope by Jurisdiction:</span>
          <select
            value={selectedZone}
            onChange={(e) => handleZoneChange(e.target.value)}
            className="bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-slate-200 focus:outline-none focus:border-emerald-500"
          >
            <option value="ALL">All Karnataka Monitoring Zones</option>
            {zones.map(z => (
              <option key={z.id} value={z.id}>{z.name} ({z.district})</option>
            ))}
          </select>
        </div>

        <div className="text-slate-400 font-mono text-[11px]">
          Report Generated: {summary?.generated_at || 'Just now'}
        </div>
      </div>

      {/* Report Summary Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-lg space-y-1">
          <span className="text-[10px] uppercase tracking-wider text-slate-400 font-semibold">Total Documented Incidents</span>
          <div className="text-2xl font-bold font-mono text-white">{summary?.total_alerts || 0}</div>
          <span className="text-xs text-slate-500">Across surveyed land units</span>
        </div>
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-lg space-y-1">
          <span className="text-[10px] uppercase tracking-wider text-slate-400 font-semibold">Total Affected Area</span>
          <div className="text-2xl font-bold font-mono text-cyan-400">{summary?.total_affected_area_hectares || 0} ha</div>
          <span className="text-xs text-slate-500">{summary?.total_affected_area_sqm?.toLocaleString()} m² footprint</span>
        </div>
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-lg space-y-1">
          <span className="text-[10px] uppercase tracking-wider text-slate-400 font-semibold">Confirmed Encroachments</span>
          <div className="text-2xl font-bold font-mono text-rose-400">{summary?.by_status?.CONFIRMED || 0}</div>
          <span className="text-xs text-slate-500">Ground verified cases</span>
        </div>
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-lg space-y-1">
          <span className="text-[10px] uppercase tracking-wider text-slate-400 font-semibold">Pending Inspection</span>
          <div className="text-2xl font-bold font-mono text-amber-400">{summary?.by_status?.FIELD_INSPECTION_REQUIRED || 0}</div>
          <span className="text-xs text-slate-500">Scheduled for survey team</span>
        </div>
      </div>

      {/* Breakdown Chart & Audit Methodology */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        <div className="lg:col-span-7 bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-xl space-y-4">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-300 flex items-center gap-2">
            <BarChart2 className="w-4 h-4 text-emerald-400" /> Land Use Alterations by Category
          </h3>
          <div className="h-60">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={categoryChartData}>
                <XAxis dataKey="name" stroke="#64748b" fontSize={10} tickLine={false} />
                <YAxis stroke="#64748b" fontSize={10} tickLine={false} />
                <Tooltip
                  contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '8px', fontSize: '11px' }}
                />
                <Bar dataKey="count" fill="#10b981" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Audit Methodology & Legal Status Box */}
        <div className="lg:col-span-5 bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-xl space-y-3 text-xs">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-300 flex items-center gap-2">
            <ShieldAlert className="w-4 h-4 text-cyan-400" /> Data Provenance & Methodology Notice
          </h3>
          <div className="p-3.5 bg-slate-950 rounded-lg border border-slate-800/80 space-y-2 text-slate-300 leading-relaxed text-[11px]">
            <p>
              <strong>Data Source:</strong> European Space Agency (ESA) Copernicus Sentinel-2 L2A optical surface reflectance and Karnataka demonstration cadastral datasets.
            </p>
            <p>
              <strong>Resolution:</strong> 10 meters per pixel, calibrated using VARI & NDBI optical differencing.
            </p>
            <p className="text-amber-400/90 italic">
              <strong>Mandatory Notice:</strong> TerraGuard AI candidates indicate statistical reflectance variation and do not constitute final judicial proof of encroachment. Physical on-site cadastral survey by authorized revenue surveyors is required before statutory enforcement.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};
