import React, { useState, useRef, useEffect } from 'react';
import { Layers, Eye, Sliders, Calendar } from 'lucide-react';

interface ImageCompareSliderProps {
  historicalImage: string;
  recentImage: string;
  maskImage?: string;
  historicalDate?: string;
  recentDate?: string;
}

export const ImageCompareSlider: React.FC<ImageCompareSliderProps> = ({
  historicalImage,
  recentImage,
  maskImage,
  historicalDate = 'Historical Scene',
  recentDate = 'Recent Scene'
}) => {
  const [sliderPosition, setSliderPosition] = useState<number>(50);
  const [mode, setMode] = useState<'SWIPE' | 'OPACITY'>('SWIPE');
  const [opacity, setOpacity] = useState<number>(50);
  const [showMask, setShowMask] = useState<boolean>(true);
  const containerRef = useRef<HTMLDivElement>(null);
  const [isDragging, setIsDragging] = useState<boolean>(false);

  const handleMove = (clientX: number) => {
    if (!containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    const x = Math.max(0, Math.min(clientX - rect.left, rect.width));
    const percent = Math.max(0, Math.min((x / rect.width) * 100, 100));
    setSliderPosition(percent);
  };

  const handleTouchMove = (e: React.TouchEvent) => {
    if (isDragging && e.touches[0]) {
      handleMove(e.touches[0].clientX);
    }
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (isDragging) {
      handleMove(e.clientX);
    }
  };

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-2xl flex flex-col">
      {/* Control Header */}
      <div className="p-3 bg-slate-950/80 border-b border-slate-800 flex flex-wrap items-center justify-between gap-3 text-xs">
        <div className="flex items-center gap-2">
          <button
            onClick={() => setMode('SWIPE')}
            className={`px-3 py-1.5 rounded-lg flex items-center gap-1.5 font-medium transition ${
              mode === 'SWIPE' ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40' : 'text-slate-400 hover:text-white'
            }`}
          >
            <Sliders className="w-3.5 h-3.5" /> Swipe Slider
          </button>
          <button
            onClick={() => setMode('OPACITY')}
            className={`px-3 py-1.5 rounded-lg flex items-center gap-1.5 font-medium transition ${
              mode === 'OPACITY' ? 'bg-cyan-500/20 text-cyan-400 border border-cyan-500/40' : 'text-slate-400 hover:text-white'
            }`}
          >
            <Eye className="w-3.5 h-3.5" /> Opacity Fade
          </button>
        </div>

        <div className="flex items-center gap-4">
          {mode === 'OPACITY' && (
            <div className="flex items-center gap-2">
              <span className="text-slate-400">Recent Opacity:</span>
              <input
                type="range"
                min="0"
                max="100"
                value={opacity}
                onChange={(e) => setOpacity(Number(e.target.value))}
                className="w-24 accent-cyan-400 cursor-pointer"
              />
              <span className="font-mono text-cyan-400">{opacity}%</span>
            </div>
          )}

          {maskImage && (
            <label className="flex items-center gap-2 cursor-pointer text-slate-300 hover:text-white select-none">
              <input
                type="checkbox"
                checked={showMask}
                onChange={(e) => setShowMask(e.target.checked)}
                className="rounded accent-emerald-500 bg-slate-800 border-slate-700"
              />
              <Layers className="w-3.5 h-3.5 text-emerald-400" />
              <span>Change Mask Overlay</span>
            </label>
          )}
        </div>
      </div>

      {/* Main Image Stage */}
      <div
        ref={containerRef}
        onMouseDown={() => setIsDragging(true)}
        onMouseUp={() => setIsDragging(false)}
        onMouseLeave={() => setIsDragging(false)}
        onMouseMove={handleMouseMove}
        onTouchStart={() => setIsDragging(true)}
        onTouchEnd={() => setIsDragging(false)}
        onTouchMove={handleTouchMove}
        className="relative w-full aspect-video bg-black select-none overflow-hidden cursor-ew-resize"
      >
        {mode === 'SWIPE' ? (
          <>
            {/* Historical Underlayer (Left side) */}
            <img
              src={historicalImage}
              alt="Historical Satellite Acquisition"
              className="absolute inset-0 w-full h-full object-cover pointer-events-none"
            />

            {/* Recent Overlayer (Clipped by slider position) */}
            <div
              className="absolute inset-0 overflow-hidden pointer-events-none"
              style={{ clipPath: `inset(0 0 0 ${sliderPosition}%)` }}
            >
              <img
                src={recentImage}
                alt="Recent Satellite Acquisition"
                className="absolute inset-0 w-full h-full object-cover"
              />
            </div>

            {/* AI Change Mask Overlay */}
            {maskImage && showMask && (
              <div
                className="absolute inset-0 pointer-events-none mix-blend-screen opacity-70"
                style={{ clipPath: `inset(0 0 0 ${sliderPosition}%)` }}
              >
                <img
                  src={maskImage}
                  alt="AI Change Detection Mask"
                  className="w-full h-full object-cover filter invert contrast-200 hue-rotate-90"
                />
              </div>
            )}

            {/* Vertical Divider Handle */}
            <div
              className="absolute top-0 bottom-0 w-0.5 bg-emerald-400 shadow-[0_0_12px_rgba(16,185,129,0.8)] pointer-events-none"
              style={{ left: `${sliderPosition}%` }}
            >
              <div className="absolute top-1/2 -translate-y-1/2 -translate-x-1/2 w-8 h-8 rounded-full bg-slate-900 border-2 border-emerald-400 flex items-center justify-center shadow-lg text-emerald-400">
                <Sliders className="w-4 h-4 rotate-90" />
              </div>
            </div>
          </>
        ) : (
          <>
            {/* Historical Base */}
            <img
              src={historicalImage}
              alt="Historical Base"
              className="absolute inset-0 w-full h-full object-cover"
            />
            {/* Recent with Opacity */}
            <img
              src={recentImage}
              alt="Recent Layer"
              className="absolute inset-0 w-full h-full object-cover transition-opacity duration-75"
              style={{ opacity: opacity / 100 }}
            />
            {maskImage && showMask && (
              <img
                src={maskImage}
                alt="AI Mask"
                className="absolute inset-0 w-full h-full object-cover mix-blend-screen opacity-60"
              />
            )}
          </>
        )}

        {/* Date Labels Overlaid */}
        <div className="absolute bottom-3 left-3 bg-slate-950/80 backdrop-blur px-2.5 py-1 rounded border border-slate-800 text-[11px] text-slate-300 flex items-center gap-1.5 pointer-events-none">
          <Calendar className="w-3 h-3 text-emerald-400" />
          <span>Historical: {historicalDate}</span>
        </div>
        <div className="absolute bottom-3 right-3 bg-slate-950/80 backdrop-blur px-2.5 py-1 rounded border border-slate-800 text-[11px] text-slate-300 flex items-center gap-1.5 pointer-events-none">
          <Calendar className="w-3 h-3 text-cyan-400" />
          <span>Recent: {recentDate}</span>
        </div>
      </div>
    </div>
  );
};
