import React, { useState, useEffect } from 'react';
import { NavLink, Outlet, useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { api } from '../api/client';
import {
  Shield, Map, Bell, BarChart3, AlertTriangle, Layers,
  FileText, Users, Settings, LogOut, Satellite, Activity,
  ChevronRight, CheckCircle2, Menu, X
} from 'lucide-react';

export const Layout: React.FC = () => {
  const { user, logout, isAdmin } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [unreadCount, setUnreadCount] = useState<number>(0);
  const [mobileMenuOpen, setMobileMenuOpen] = useState<boolean>(false);

  useEffect(() => {
    const fetchUnread = async () => {
      try {
        const notifs = await api.getNotifications();
        const unread = notifs.filter(n => !n.is_read).length;
        setUnreadCount(unread);
      } catch (e) {
        console.error("Failed to fetch notifications:", e);
      }
    };
    fetchUnread();
    const interval = setInterval(fetchUnread, 30000);
    return () => clearInterval(interval);
  }, []);

  const navItems = [
    { label: 'Overview Dashboard', path: '/dashboard', icon: BarChart3 },
    { label: 'GIS Monitoring Map', path: '/map', icon: Map },
    { label: 'Alerts & Encroachments', path: '/alerts', icon: AlertTriangle, badge: unreadCount },
    { label: 'Monitoring Areas', path: '/monitoring-areas', icon: Layers },
    { label: 'Satellite Imagery', path: '/imagery', icon: Satellite },
    { label: 'AI Change Detection', path: '/analysis', icon: Activity },
    { label: 'Reports & Audits', path: '/reports', icon: FileText },
    { label: 'Notifications', path: '/notifications', icon: Bell, badge: unreadCount },
    ...(isAdmin ? [{ label: 'User Management', path: '/users', icon: Users }] : []),
    { label: 'System Settings', path: '/settings', icon: Settings },
  ];

  const roleColors: Record<string, string> = {
    ADMIN: 'bg-rose-500/10 text-rose-400 border-rose-500/30',
    MONITORING_OFFICER: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30',
    FIELD_INSPECTOR: 'bg-cyan-500/10 text-cyan-400 border-cyan-500/30'
  };

  return (
    <div className="flex h-screen bg-[#0a0e17] text-slate-100 overflow-hidden font-sans">
      {/* Sidebar Navigation */}
      <aside className={`
        fixed inset-y-0 left-0 z-50 w-64 bg-[#0d131f] border-r border-slate-800/80 flex flex-col transition-transform duration-300
        md:static md:translate-x-0 ${mobileMenuOpen ? 'translate-x-0' : '-translate-x-full'}
      `}>
        {/* Brand Header */}
        <div className="p-4 border-b border-slate-800/80 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-emerald-500 to-cyan-600 flex items-center justify-center shadow-lg shadow-emerald-950/50">
              <Shield className="w-6 h-6 text-slate-950 font-bold" />
            </div>
            <div>
              <h1 className="text-base font-bold tracking-tight text-white flex items-center gap-1.5">
                TerraGuard <span className="text-emerald-400 font-mono text-xs px-1.5 py-0.5 rounded bg-emerald-500/10 border border-emerald-500/30">AI</span>
              </h1>
              <p className="text-[11px] text-slate-400">Detect. Monitor. Act.</p>
            </div>
          </div>
          <button
            onClick={() => setMobileMenuOpen(false)}
            className="md:hidden text-slate-400 hover:text-white"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Navigation Items */}
        <nav className="flex-1 overflow-y-auto p-3 space-y-1">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = location.pathname === item.path || (item.path !== '/dashboard' && location.pathname.startsWith(item.path));
            return (
              <NavLink
                key={item.path}
                to={item.path}
                onClick={() => setMobileMenuOpen(false)}
                className={`
                  flex items-center justify-between px-3 py-2.5 rounded-lg text-xs font-medium transition duration-150 group
                  ${isActive
                    ? 'bg-emerald-500/15 text-emerald-300 border border-emerald-500/30 shadow-sm'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60 border border-transparent'}
                `}
              >
                <div className="flex items-center gap-3">
                  <Icon className={`w-4 h-4 transition ${isActive ? 'text-emerald-400' : 'text-slate-400 group-hover:text-slate-200'}`} />
                  <span>{item.label}</span>
                </div>
                {item.badge !== undefined && item.badge > 0 && (
                  <span className="px-1.5 py-0.5 rounded-full text-[10px] font-bold bg-amber-500/20 text-amber-400 border border-amber-500/40">
                    {item.badge}
                  </span>
                )}
              </NavLink>
            );
          })}
        </nav>

        {/* User Card & Logout */}
        <div className="p-3 border-t border-slate-800/80 bg-slate-950/40">
          <div className="flex items-center justify-between p-2 rounded-lg bg-slate-900/60 border border-slate-800">
            <div className="overflow-hidden pr-2">
              <div className="text-xs font-semibold text-white truncate">{user?.full_name || 'Officer'}</div>
              <div className="text-[10px] text-slate-400 truncate">{user?.email}</div>
              <div className="mt-1">
                <span className={`inline-block px-1.5 py-0.2 rounded text-[9px] font-semibold border ${roleColors[user?.role || 'MONITORING_OFFICER']}`}>
                  {user?.role?.replace('_', ' ')}
                </span>
              </div>
            </div>
            <button
              onClick={logout}
              title="Sign Out"
              className="p-1.5 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-red-400 transition"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Top Operational Header */}
        <header className="h-14 border-b border-slate-800 bg-[#0d131f]/90 backdrop-blur px-4 sm:px-6 flex items-center justify-between z-10">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setMobileMenuOpen(true)}
              className="md:hidden p-1.5 rounded-lg hover:bg-slate-800 text-slate-400"
            >
              <Menu className="w-5 h-5" />
            </button>
            <div className="flex items-center gap-2">
              <span className="hidden sm:inline-block w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              <span className="text-xs font-medium text-slate-300">
                Karnataka State Sentinel-2 Land Registry Pipeline
              </span>
            </div>
            <span className="hidden lg:inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-mono bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
              <CheckCircle2 className="w-3 h-3" /> DEMO MODE: ACTIVE
            </span>
          </div>

          <div className="flex items-center gap-3">
            {/* Notifications Shortcut */}
            <button
              onClick={() => navigate('/notifications')}
              className="relative p-2 rounded-lg bg-slate-900 border border-slate-800 hover:border-slate-700 text-slate-300 hover:text-white transition"
              title="Notifications"
            >
              <Bell className="w-4 h-4" />
              {unreadCount > 0 && (
                <span className="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-amber-500 text-slate-950 font-bold text-[10px] flex items-center justify-center">
                  {unreadCount}
                </span>
              )}
            </button>

            {/* Quick Action Button */}
            <button
              onClick={() => navigate('/analysis')}
              className="hidden sm:flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-gradient-to-r from-emerald-600 to-cyan-600 hover:from-emerald-500 hover:to-cyan-500 text-white text-xs font-semibold shadow-md shadow-emerald-950/50 transition"
            >
              <Activity className="w-3.5 h-3.5" />
              <span>Run Detection</span>
            </button>
          </div>
        </header>

        {/* Page Content Outlet */}
        <main className="flex-1 overflow-y-auto bg-[#0a0e17] p-4 sm:p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
};
