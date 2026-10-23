import React from 'react';
import { RiskLevel } from '../types';

interface RiskBadgeProps {
  level: RiskLevel;
  score?: number;
}

export const RiskBadge: React.FC<RiskBadgeProps> = ({ level, score }) => {
  const styles: Record<RiskLevel, string> = {
    CRITICAL: 'bg-red-950/70 text-red-400 border-red-500/50 shadow-red-950/50',
    HIGH: 'bg-amber-950/70 text-amber-400 border-amber-500/50 shadow-amber-950/50',
    MEDIUM: 'bg-cyan-950/70 text-cyan-400 border-cyan-500/50 shadow-cyan-950/50',
    LOW: 'bg-emerald-950/70 text-emerald-400 border-emerald-500/50 shadow-emerald-950/50',
  };

  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold border ${styles[level]} shadow-sm`}>
      <span className={`w-1.5 h-1.5 rounded-full ${level === 'CRITICAL' ? 'bg-red-400 animate-pulse' : level === 'HIGH' ? 'bg-amber-400' : level === 'MEDIUM' ? 'bg-cyan-400' : 'bg-emerald-400'}`} />
      {level}
      {score !== undefined && <span className="opacity-75 font-mono text-[11px]">({Math.round(score)})</span>}
    </span>
  );
};
