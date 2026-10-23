import React from 'react';
import { AlertStatus } from '../types';

interface StatusBadgeProps {
  status: AlertStatus;
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status }) => {
  const config: Record<AlertStatus, { label: string; style: string }> = {
    NEW: {
      label: 'New',
      style: 'bg-blue-950/60 text-blue-400 border-blue-500/40'
    },
    UNDER_REVIEW: {
      label: 'Under Review',
      style: 'bg-purple-950/60 text-purple-400 border-purple-500/40'
    },
    FIELD_INSPECTION_REQUIRED: {
      label: 'Inspection Required',
      style: 'bg-amber-950/60 text-amber-400 border-amber-500/40'
    },
    CONFIRMED: {
      label: 'Confirmed Violation',
      style: 'bg-rose-950/60 text-rose-400 border-rose-500/40'
    },
    DISMISSED: {
      label: 'Dismissed',
      style: 'bg-slate-800 text-slate-400 border-slate-700'
    },
    RESOLVED: {
      label: 'Resolved',
      style: 'bg-emerald-950/60 text-emerald-400 border-emerald-500/40'
    }
  };

  const item = config[status] || { label: status, style: 'bg-slate-800 text-slate-300 border-slate-700' };

  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border ${item.style}`}>
      {item.label}
    </span>
  );
};
