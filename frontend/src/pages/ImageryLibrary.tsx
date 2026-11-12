import React, { useEffect, useState } from 'react';
import { api } from '../api/client';
import { ImageCompareSlider } from '../components/ImageCompareSlider';
import { MonitoringZone, SatelliteCompareResponse } from '../types';
import { Calendar, Cloud, Layers, Satellite } from 'lucide-react';

export const ImageryLibrary: React.FC = () => {
  const [zones, setZones] = useState<MonitoringZone[]>([]);
  const [zoneId, setZoneId] = useState<number | ''>('');
  const [historicalStart, setHistoricalStart] = useState('2024-01-01');
  const [historicalEnd, setHistoricalEnd] = useState('2024-03-31');
  const [recentStart, setRecentStart] = useState('2025-01-01');
  const [recentEnd, setRecentEnd] = useState('2025-03-31');
  const [cloudThreshold, setCloudThreshold] = useState(30);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [health, setHealth] = useState<any>(null);
  const [result, setResult] = useState<SatelliteCompareResponse | null>(null);

  useEffect(() => {
    Promise.all([api.getZones(), api.getSatelliteHealth()])
      .then(([zoneList, healthResult]) => {
        setZones(zoneList);
        const requestedZoneId = Number(new URLSearchParams(window.location.search).get('zone_id'));
        const requestedZone = zoneList.find((zone) => zone.id === requestedZoneId);
        if (requestedZone) setZoneId(requestedZone.id);
        else if (zoneList.length) setZoneId(zoneList[0].id);
        setHealth(healthResult);
      })
      .catch((e) => setError(e.message || 'Failed to initialize satellite services'));
  }, []);

  const handleCompare = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!zoneId) {
      setError('Select a monitoring area.');
      return;
    }
    setLoading(true);
    setError('');
    setResult(null);
    try {
      const response = await api.compareSatellite({
        zone_id: zoneId,
        historical_start_date: historicalStart,
        historical_end_date: historicalEnd,
        recent_start_date: recentStart,
        recent_end_date: recentEnd,
        max_cloud_coverage: cloudThreshold,
        width: 512,
        height: 512,
        resolution_meters: 10,
      });
      setResult(response);
    } catch (e: any) {
      setError(e.message || 'Satellite acquisition failed.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="pb-2 border-b border-slate-800/80">
        <h2 className="text-xl font-bold text-white flex items-center gap-2">
          <Satellite className="w-5 h-5 text-emerald-400" />
          Satellite Imagery Repository
        </h2>
        <p className="text-xs text-slate-400 mt-1">
          Sentinel-2 Level-2A acquisitions through Google Earth Engine
        </p>
        <p className="text-[11px] text-amber-300 mt-2">
          SNUNet-CD was trained on LEVIR-CD+ imagery. Sentinel-2 differs in sensor and resolution; results on Sentinel-2 have not been independently validated and are not an accuracy claim.
        </p>
      </div>

      {health && (
        <div className={`text-xs rounded-lg border px-3 py-2 ${health.status === 'configured' ? 'border-emerald-800 bg-emerald-950/30 text-emerald-300' : 'border-amber-800 bg-amber-950/30 text-amber-300'}`}>
          Earth Engine: {health.status === 'configured' ? 'configured' : health.error || 'not configured'}
        </div>
      )}

      <form onSubmit={handleCompare} className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <label className="text-xs text-slate-300">
            Monitoring Area
            <select value={zoneId} onChange={(e) => setZoneId(Number(e.target.value))} className="mt-1 w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2">
              <option value="">Select monitoring area</option>
              {zones.map((zone) => <option key={zone.id} value={zone.id}>{zone.name}</option>)}
            </select>
          </label>
          <label className="text-xs text-slate-300">
            Cloud threshold: {cloudThreshold}% maximum
            <input type="range" min="0" max="100" value={cloudThreshold} onChange={(e) => setCloudThreshold(Number(e.target.value))} className="mt-3 w-full accent-emerald-500" />
          </label>
          <div className="text-xs text-slate-400 flex items-end pb-1">
            <Cloud className="w-4 h-4 mr-1 text-cyan-400" /> Sentinel-2 L2A / 10 m RGB
          </div>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="border border-slate-800 rounded-lg p-3">
            <div className="text-xs font-semibold text-slate-300 mb-2 flex items-center gap-1"><Calendar className="w-3.5 h-3.5" /> Historical range</div>
            <div className="grid grid-cols-2 gap-2">
              <input aria-label="Historical start date" type="date" value={historicalStart} onChange={(e) => setHistoricalStart(e.target.value)} className="bg-slate-950 border border-slate-800 rounded px-2 py-2 text-xs text-white" />
              <input aria-label="Historical end date" type="date" value={historicalEnd} onChange={(e) => setHistoricalEnd(e.target.value)} className="bg-slate-950 border border-slate-800 rounded px-2 py-2 text-xs text-white" />
            </div>
          </div>
          <div className="border border-slate-800 rounded-lg p-3">
            <div className="text-xs font-semibold text-slate-300 mb-2 flex items-center gap-1"><Calendar className="w-3.5 h-3.5" /> Recent range</div>
            <div className="grid grid-cols-2 gap-2">
              <input aria-label="Recent start date" type="date" value={recentStart} onChange={(e) => setRecentStart(e.target.value)} className="bg-slate-950 border border-slate-800 rounded px-2 py-2 text-xs text-white" />
              <input aria-label="Recent end date" type="date" value={recentEnd} onChange={(e) => setRecentEnd(e.target.value)} className="bg-slate-950 border border-slate-800 rounded px-2 py-2 text-xs text-white" />
            </div>
          </div>
        </div>
        <button disabled={loading || !zoneId} className="px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white text-xs font-semibold">
          {loading ? 'Acquiring Sentinel-2 imagery...' : 'Acquire and Compare'}
        </button>
      </form>

      {error && <div className="rounded-lg border border-red-900 bg-red-950/30 px-4 py-3 text-sm text-red-300">{error}</div>}

      {result && result.historical.image_url && result.recent.image_url && (
        <div className="space-y-4">
          <ImageCompareSlider
            historicalImage={result.historical.image_url}
            recentImage={result.recent.image_url}
            historicalDate={`${result.historical.date || 'Unknown'} (${result.historical.cloud_coverage_percentage ?? 'Unknown'}% cloud)`}
            recentDate={`${result.recent.date || 'Unknown'} (${result.recent.cloud_coverage_percentage ?? 'Unknown'}% cloud)`}
          />
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {[['Historical', result.historical], ['Recent', result.recent]].map(([label, image]) => (
              <div key={String(label)} className="bg-slate-900 border border-slate-800 rounded-xl p-4 text-xs text-slate-300">
                <div className="font-bold text-white mb-2">{String(label)} acquisition</div>
                <img src={(image as any).image_url} alt={`${label} Sentinel-2`} className="w-full rounded border border-slate-800 mb-2" />
                <div>Date: {(image as any).date || 'Unavailable'}</div>
                <div>Cloud: {(image as any).cloud_coverage_percentage ?? 'Unavailable'}%</div>
                <div>Source: Earth Engine / COPERNICUS/S2_SR_HARMONIZED</div>
                <div>Cache: {(image as any).cached ? 'Cached data' : 'Live acquisition'}</div>
                <div>Analysis grid: {(image as any).raster_width} × {(image as any).raster_height} pixels</div>
                <div>CRS: {(image as any).crs} · {(image as any).resolution_meters} m</div>
                <div>No-data value: {(image as any).nodata ?? 'Unavailable'}</div>
                <div>Native GeoTIFF valid coverage: {(image as any).valid_pixel_coverage_percentage ?? 'Unavailable'}% ({(image as any).valid_pixel_count ?? '—'} / {(image as any).zone_pixel_count ?? '—'} polygon pixels)</div>
                <div className="break-all">Affine: {JSON.stringify((image as any).transform || [])}</div>
                {(image as any).geotiff_url && <a className="text-emerald-400 hover:text-emerald-300 block mt-1" href={(image as any).geotiff_url}>Download GeoTIFF package</a>}
              </div>
            ))}
          </div>

          {/* Direct CTA to Launch AI Change Detection on this Sentinel-2 Pair */}
          <div className="bg-slate-900 border border-emerald-500/40 rounded-xl p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 shadow-xl">
            <div>
              <div className="text-sm font-bold text-white flex items-center gap-2">
                <Satellite className="w-4 h-4 text-emerald-400" /> Ready for Deep Learning Change Detection
              </div>
              <p className="text-xs text-slate-400 mt-0.5">
                Execute the trained SNUNet-CD neural network on this registered Sentinel-2 dual-date pair to extract georeferenced land-cover change vectors.
              </p>
            </div>
            <button
              onClick={() => {
                const params = new URLSearchParams();
                if (zoneId) params.append('zone_id', String(zoneId));
                if (result.historical_scene_id) params.append('hist_scene_id', String(result.historical_scene_id));
                if (result.recent_scene_id) params.append('recent_scene_id', String(result.recent_scene_id));
                window.location.href = `/analysis?${params.toString()}`;
              }}
              className="px-5 py-2.5 bg-gradient-to-r from-emerald-600 to-cyan-600 hover:from-emerald-500 hover:to-cyan-500 text-white font-semibold text-xs rounded-lg flex items-center justify-center gap-2 shadow-lg transition whitespace-nowrap"
            >
              Run SNUNet-CD Analysis &rarr;
            </button>
          </div>

          <div className="rounded-lg border border-slate-800 bg-slate-900 px-4 py-3 text-xs text-slate-400">
            <Layers className="inline w-4 h-4 mr-1 text-amber-400" />
            {result.disclaimer}
          </div>
        </div>
      )}
    </div>
  );
};
