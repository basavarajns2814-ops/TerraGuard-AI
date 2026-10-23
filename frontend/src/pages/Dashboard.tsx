import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import { DashboardStats, Alert, MonitoringZone } from '../types';
import { KpiCard } from '../components/KpiCard';
import { RiskBadge } from '../components/RiskBadge';
import { StatusBadge } from '../components/StatusBadge';
import { GISMapViewer } from '../components/GISMapViewer';
import {
  ShieldAlert, Layers, MapPin, AlertCircle, Clock,
  Calendar, CheckCircle, ArrowUpRight, TrendingUp, Filter,
  Building, Activity
} from 'lucide-react';
import {
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis,
  Tooltip, PieChart, Pie, Cell, BarChart, Bar
} from 'recharts';

export const Dashboard: React.FC = () => {
  const navigate = useNavigate();
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [trends, setTrends] = useState<any>(null);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [zones, setZones] = useState<MonitoringZone[]>([]);
  const [selectedZone, setSelectedZone] = useState<string>('ALL');
  const [selectedRisk, setSelectedRisk] = useState<string>('ALL');
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    const loadDashboardData = async () => {
      try {
        const [statsData, trendsData, alertsData, zonesData] = await Promise.all([
          api.getDashboardStats(),
          api.getDashboardTrends(),
          api.getAlerts(),
          api.getZones()
        ]);
        setStats(statsData);
        setTrends(trendsData);
        setAlerts(alertsData);
        setZones(zonesData);
      } catch (e) {
        console.error("Dashboard data load error:", e);
      } finally {
        setLoading(false);
      }
    };
    loadDashboardData();
  }, []);

  const filteredAlerts = alerts.filter(a => {
    if (selectedZone !== 'ALL' && String(a.zone_id) !== selectedZone) return false;
    if (selectedRisk !== 'ALL' && a.risk_level !== selectedRisk) return false;
    return true;
  });

  const RISK_COLORS: Record<string, string> = {
    CRITICAL: '#ef4444',
    HIGH: '#f59e0b',
    MEDIUM: '#06b6d4',
    LOW: '#10b981'
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96 text-slate-400 gap-3">
        <div className="w-6 h-6 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin" />
        <span className="text-sm">Synthesizing Geospatial Intelligence Dashboard...</span>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Title & Metadata Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-2 border-b border-slate-800/80">
        <div>
          <h2 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
            Executive Command & Monitoring Overview
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Real-time satellite change detection & cadastral boundary infringement monitoring.
          </p>
        </div>

        {/* Global Metadata & Status */}
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <div className="px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-800 text-slate-300 flex items-center gap-2">
            <Calendar className="w-3.5 h-3.5 text-emerald-400" />
            <span>Latest Pass: <strong className="text-white font-mono">{stats?.latest_imagery_date}</strong></span>
          </div>
          <div className="px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-800 text-slate-300 flex items-center gap-2">
            <Clock className="w-3.5 h-3.5 text-cyan-400" />
            <span>Last Analysis: <strong className="text-white font-mono">{stats?.last_analysis_timestamp}</strong></span>
          </div>
        </div>
      </div>

      {/* 8 Primary KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <KpiCard
          title="Monitored Parcels"
          value={stats?.monitored_parcels || 0}
          subtitle="Cadastral boundaries"
          icon={Layers}
          accentColor="text-cyan-400"
          onClick={() => navigate('/monitoring-areas')}
        />
        <KpiCard
          title="Total Area"
          value={`${stats?.total_area_hectares || 0} ha`}
          subtitle="Catchment & forest perimeter"
          icon={MapPin}
          accentColor="text-emerald-400"
        />
        <KpiCard
          title="Detected Changes"
          value={stats?.new_changes_detected || 0}
          subtitle="Surface reflectance anomalies"
          trend="+12% this cycle"
          trendType="alert"
          icon={Activity}
          accentColor="text-amber-400"
          onClick={() => navigate('/analysis')}
        />
        <KpiCard
          title="Pending Alerts"
          value={stats?.pending_alerts || 0}
          subtitle="Requiring officer evaluation"
          trend="Action required"
          trendType="alert"
          icon={AlertCircle}
          accentColor="text-rose-400"
          onClick={() => navigate('/alerts')}
        />
        <KpiCard
          title="High / Critical Risk"
          value={stats?.high_risk_alerts || 0}
          subtitle="Boundary buffer violations"
          trend="Immediate attention"
          trendType="negative"
          icon={ShieldAlert}
          accentColor="text-red-400"
          onClick={() => navigate('/alerts')}
        />
        <KpiCard
          title="Awaiting Inspection"
          value={stats?.awaiting_inspection || 0}
          subtitle="Assigned to field survey"
          icon={Clock}
          accentColor="text-amber-400"
          onClick={() => navigate('/alerts')}
        />
        <KpiCard
          title="Confirmed Encroachments"
          value={stats?.confirmed_encroachments || 0}
          subtitle="Ground verified violations"
          trend="Statutory notice issued"
          trendType="negative"
          icon={Building}
          accentColor="text-rose-500"
          onClick={() => navigate('/alerts')}
        />
        <KpiCard
          title="Last 30 Days Changes"
          value={stats?.changes_last_30_days || 0}
          subtitle="Emerging candidate footprints"
          trend="Active rate"
          trendType="positive"
          icon={TrendingUp}
          accentColor="text-emerald-400"
        />
      </div>

      {/* Main Operational Section: Map + Live Feed */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Interactive GIS Map (2 columns) */}
        <div className="lg:col-span-2 space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-white flex items-center gap-2">
              <MapPin className="w-4 h-4 text-emerald-400" /> Active Cadastral Monitoring Map
            </h3>
            <button
              onClick={() => navigate('/map')}
              className="text-xs text-emerald-400 hover:text-emerald-300 flex items-center gap-1 font-medium"
            >
              Expand Full Map <ArrowUpRight className="w-3.5 h-3.5" />
            </button>
          </div>

          <GISMapViewer
            zones={zones}
            alerts={filteredAlerts}
            height="460px"
            onSelectAlert={(a) => navigate(`/alerts/${a.id}`)}
          />
        </div>

        {/* Priority Alerts Side Feed (1 column) */}
        <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-4 flex flex-col shadow-xl">
          <div className="flex items-center justify-between pb-3 border-b border-slate-800">
            <h3 className="text-sm font-semibold text-white flex items-center gap-2">
              <ShieldAlert className="w-4 h-4 text-rose-400" /> High Priority Alerts
            </h3>
            <span className="text-xs font-mono text-slate-400">{filteredAlerts.length} items</span>
          </div>

          <div className="flex-1 overflow-y-auto space-y-2.5 mt-3 pr-1 max-h-[400px]">
            {filteredAlerts.slice(0, 5).map((a) => (
              <div
                key={a.id}
                onClick={() => navigate(`/alerts/${a.id}`)}
                className="p-3 rounded-lg bg-slate-950/70 border border-slate-800/80 hover:border-slate-700 cursor-pointer transition space-y-1.5"
              >
                <div className="flex items-center justify-between">
                  <span className="font-mono text-xs font-bold text-emerald-400">{a.alert_code}</span>
                  <RiskBadge level={a.risk_level} score={a.risk_score} />
                </div>
                <div className="text-xs font-medium text-slate-200">
                  {a.category.replace('_', ' ')}
                </div>
                <div className="text-[11px] text-slate-400 flex items-center justify-between">
                  <span>{a.zone_name}</span>
                  <span className="font-mono text-cyan-400">{a.affected_area_sqm.toLocaleString()} m²</span>
                </div>
                <div className="pt-1 flex items-center justify-between text-[10px]">
                  <StatusBadge status={a.status} />
                  <span className="text-slate-500 font-mono">{a.latest_observed_date}</span>
                </div>
              </div>
            ))}
          </div>

          <button
            onClick={() => navigate('/alerts')}
            className="w-full mt-3 py-2 text-xs font-semibold text-center text-slate-300 hover:text-white bg-slate-800/60 hover:bg-slate-800 rounded-lg transition"
          >
            View All Alert Records
          </button>
        </div>
      </div>

      {/* Analytics Charts Row */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* 1. Time Series Detections Chart */}
        <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-5 shadow-lg">
          <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-4 flex items-center gap-1.5">
            <TrendingUp className="w-4 h-4 text-emerald-400" /> Temporal Change Trajectory
          </h4>
          <div className="h-52">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={trends?.timeline || []}>
                <defs>
                  <linearGradient id="colorCount" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#10b981" stopOpacity={0.4}/>
                    <stop offset="95%" stopColor="#10b981" stopOpacity={0.0}/>
                  </linearGradient>
                </defs>
                <XAxis dataKey="date" stroke="#64748b" fontSize={10} tickLine={false} />
                <YAxis stroke="#64748b" fontSize={10} tickLine={false} />
                <Tooltip
                  contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '8px', fontSize: '11px' }}
                />
                <Area type="monotone" dataKey="count" stroke="#10b981" fillOpacity={1} fill="url(#colorCount)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* 2. Risk Distribution Pie Chart */}
        <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-5 shadow-lg">
          <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-4 flex items-center gap-1.5">
            <ShieldAlert className="w-4 h-4 text-cyan-400" /> Risk Severity Distribution
          </h4>
          <div className="h-52 flex items-center justify-center">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={trends?.risks || []}
                  dataKey="count"
                  nameKey="name"
                  cx="50%"
                  cy="50%"
                  innerRadius={45}
                  outerRadius={75}
                  paddingAngle={4}
                >
                  {(trends?.risks || []).map((entry: any, index: number) => (
                    <Cell key={`cell-${index}`} fill={RISK_COLORS[entry.name] || '#06b6d4'} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '8px', fontSize: '11px' }}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* 3. Category Breakdown Bar Chart */}
        <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-5 shadow-lg">
          <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-4 flex items-center gap-1.5">
            <Building className="w-4 h-4 text-amber-400" /> Land Use Change Types
          </h4>
          <div className="h-52">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={trends?.categories || []}>
                <XAxis dataKey="name" stroke="#64748b" fontSize={9} tickLine={false} interval={0} />
                <YAxis stroke="#64748b" fontSize={10} tickLine={false} />
                <Tooltip
                  contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '8px', fontSize: '11px' }}
                />
                <Bar dataKey="count" fill="#06b6d4" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </div>
  );
};
