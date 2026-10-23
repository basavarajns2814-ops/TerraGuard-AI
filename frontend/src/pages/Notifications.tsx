import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import { NotificationItem } from '../types';
import { Bell, CheckCheck, ShieldAlert, ArrowRight, Clock } from 'lucide-react';

export const Notifications: React.FC = () => {
  const navigate = useNavigate();
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);

  const fetchNotifs = async () => {
    try {
      const items = await api.getNotifications();
      setNotifications(items);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchNotifs();
  }, []);

  const handleMarkRead = async (id: number) => {
    try {
      await api.markNotificationRead(id);
      setNotifications(notifications.map(n => n.id === id ? { ...n, is_read: true } : n));
    } catch (e) {
      console.error(e);
    }
  };

  const handleMarkAllRead = async () => {
    try {
      await api.markAllNotificationsRead();
      setNotifications(notifications.map(n => ({ ...n, is_read: true })));
    } catch (e) {
      console.error(e);
    }
  };

  const handleClickItem = (item: NotificationItem) => {
    if (!item.is_read) {
      handleMarkRead(item.id);
    }
    if (item.alert_id) {
      navigate(`/alerts/${item.alert_id}`);
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Title & Actions */}
      <div className="flex items-center justify-between pb-2 border-b border-slate-800/80">
        <div>
          <h2 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
            Operational Alerts & System Notifications
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Real-time critical risk warnings, officer assignments, and workflow status shifts.
          </p>
        </div>

        <button
          onClick={handleMarkAllRead}
          className="px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-800 hover:border-slate-700 text-slate-300 text-xs font-semibold flex items-center gap-1.5 transition"
        >
          <CheckCheck className="w-4 h-4 text-emerald-400" /> Mark All as Read
        </button>
      </div>

      {/* Notifications List */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-2xl divide-y divide-slate-800/80">
        {loading ? (
          <div className="py-12 text-center text-slate-500 text-xs">
            Loading notification feed...
          </div>
        ) : notifications.length === 0 ? (
          <div className="py-12 text-center text-slate-500 text-xs">
            No notification events in your log.
          </div>
        ) : (
          notifications.map((n) => (
            <div
              key={n.id}
              onClick={() => handleClickItem(n)}
              className={`p-4 flex items-start justify-between gap-4 cursor-pointer transition ${
                n.is_read ? 'hover:bg-slate-800/40 opacity-75' : 'bg-slate-950/40 hover:bg-slate-800/60'
              }`}
            >
              <div className="flex items-start gap-3">
                <div className={`p-2 rounded-lg mt-0.5 ${
                  n.type === 'ALERT_HIGH' ? 'bg-red-500/10 text-red-400 border border-red-500/30' :
                  n.type === 'INSPECTION' ? 'bg-cyan-500/10 text-cyan-400 border border-cyan-500/30' :
                  'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30'
                }`}>
                  <ShieldAlert className="w-4 h-4" />
                </div>
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <h4 className="text-xs font-bold text-white">{n.title}</h4>
                    {!n.is_read && (
                      <span className="w-2 h-2 rounded-full bg-amber-400 inline-block animate-pulse" />
                    )}
                  </div>
                  <p className="text-xs text-slate-300 leading-relaxed">{n.message}</p>
                  <div className="text-[10px] text-slate-500 font-mono flex items-center gap-1">
                    <Clock className="w-3 h-3" />
                    {n.created_at?.slice(0, 16).replace('T', ' ')}
                  </div>
                </div>
              </div>

              {n.alert_id && (
                <div className="flex items-center gap-1 text-xs text-emerald-400 font-semibold whitespace-nowrap self-center hover:underline">
                  <span>Inspect</span> <ArrowRight className="w-3.5 h-3.5" />
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
};
