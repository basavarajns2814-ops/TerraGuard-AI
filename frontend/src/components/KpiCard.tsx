import React from 'react';
import { LucideIcon } from 'lucide-react';

interface KpiCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon: LucideIcon;
  trend?: string;
  trendType?: 'positive' | 'negative' | 'neutral' | 'alert';
  onClick?: () => void;
  accentColor?: string;
}

export const KpiCard: React.FC<KpiCardProps> = ({
  title,
  value,
  subtitle,
  icon: Icon,
  trend,
  trendType = 'neutral',
  onClick,
  accentColor = 'text-emerald-400'
}) => {
  const trendColor = {
    positive: 'text-emerald-400',
    negative: 'text-red-400',
    alert: 'text-amber-400',
    neutral: 'text-slate-400'
  }[trendType];

  return (
    <div
      onClick={onClick}
      className={`bg-slate-900/80 backdrop-blur border border-slate-800 rounded-xl p-5 hover:border-slate-700 transition duration-200 shadow-lg relative overflow-hidden group ${
        onClick ? 'cursor-pointer hover:bg-slate-800/60' : ''
      }`}
    >
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs font-medium uppercase tracking-wider text-slate-400">{title}</p>
          <h3 className="text-2xl font-bold text-white mt-1.5 font-mono tracking-tight">{value}</h3>
        </div>
        <div className={`p-2.5 rounded-lg bg-slate-800/80 border border-slate-700/60 ${accentColor}`}>
          <Icon className="w-5 h-5" />
        </div>
      </div>

      {(subtitle || trend) && (
        <div className="mt-3 flex items-center justify-between text-xs text-slate-400 pt-3 border-t border-slate-800/60">
          <span>{subtitle}</span>
          {trend && <span className={`font-medium ${trendColor}`}>{trend}</span>}
        </div>
      )}
    </div>
  );
};
