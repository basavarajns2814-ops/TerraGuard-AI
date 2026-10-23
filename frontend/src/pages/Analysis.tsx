import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import { DetectionJob, MonitoringZone, SatelliteScene, DetectedChange, LevirPredictionResponse } from '../types';
import { RiskBadge } from '../components/RiskBadge';
import {
  Activity, Play, CheckCircle, Clock, AlertCircle,
  Layers, Sliders, Cpu, ArrowRight, Eye, RefreshCw
} from 'lucide-react';

export const Analysis: React.FC = () => {
  const navigate = useNavigate();
  const [jobs, setJobs] = useState<DetectionJob[]>([]);
  const [zones, setZones] = useState<MonitoringZone[]>([]);
  const [scenes, setScenes] = useState<SatelliteScene[]>([]);
  const [changes, setChanges] = useState<DetectedChange[]>([]);
  const [loading, setLoading] = useState<boolean>(true);

  // Form states
  const [selectedZoneId, setSelectedZoneId] = useState<number>(1);
  const [histSceneId, setHistSceneId] = useState<number>(1);
  const [recentSceneId, setRecentSceneId] = useState<number>(3);
  const [algorithm, setAlgorithm] = useState<string>('SPECTRAL_NDVI_NDBI_DIFFERENCING');
  const [threshold, setThreshold] = useState<number>(0.18);
  const [launching, setLaunching] = useState<boolean>(false);
  const [activeJob, setActiveJob] = useState<DetectionJob | null>(null);
  const [levirPrediction, setLevirPrediction] = useState<LevirPredictionResponse | null>(null);
  const [predictingLevir, setPredictingLevir] = useState(false);

  const fetchAnalysisData = async () => {
    try {
      const [j, z, sc, ch] = await Promise.all([
        api.getJobs(),
        api.getZones(),
        api.getImagery(),
        api.getChanges()
      ]);
      setJobs(j);
      setZones(z);
      setScenes(sc);
      setChanges(ch);
      if (z.length > 0) setSelectedZoneId(z[0].id);
      if (sc.length >= 2) {
        setHistSceneId(sc[sc.length - 1].id);
        setRecentSceneId(sc[0].id);
      }
    } catch (e) {
      console.error("Error loading analysis data:", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAnalysisData();
  }, []);

  // Poll progress if active job is running
  useEffect(() => {
    if (!activeJob || activeJob.status === 'COMPLETED' || activeJob.status === 'FAILED') return;
    const interval = setInterval(async () => {
      try {
        const updated = await api.getJobs();
        const found = updated.find(j => j.id === activeJob.id);
        if (found) {
          setActiveJob(found);
          setJobs(updated);
          if (found.status === 'COMPLETED') {
            const ch = await api.getChanges();
            setChanges(ch);
          }
        }
      } catch (e) {
        console.error("Poll error:", e);
      }
    }, 2000);
    return () => clearInterval(interval);
  }, [activeJob]);

  const handleLaunchJob = async (e: React.FormEvent) => {
    e.preventDefault();
    setLaunching(true);
    try {
      const job = await api.runAnalysis({
        zone_id: selectedZoneId,
        historical_scene_id: histSceneId,
        recent_scene_id: recentSceneId,
        algorithm,
        parameters: { threshold, min_area_pixels: 25 }
      });
      setActiveJob(job);
      setJobs([job, ...jobs]);
    } catch (e: any) {
      alert(e.message || "Failed to launch detection pipeline");
    } finally {
      setLaunching(false);
    }
  };

  const handleLevirPrediction = async () => {
    setPredictingLevir(true);
    try {
      const prediction = await api.predictLevirChange({
        earlier_scene_id: histSceneId,
        later_scene_id: recentSceneId,
        threshold: 0.7
      });
      setLevirPrediction(prediction);
    } catch (e: any) {
      alert(e.message || 'LEVIR-CD+ prediction failed');
    } finally {
      setPredictingLevir(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Title Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b border-slate-800/80">
        <div>
          <h2 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
            AI Change Detection Engine & Analytics Execution
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Execute spectral index differencing and U-Net structural segmentation across acquisition passes.
          </p>
        </div>

        <button
          onClick={fetchAnalysisData}
          className="p-2 bg-slate-900 border border-slate-800 text-slate-300 hover:text-white rounded-lg text-xs flex items-center gap-1.5 transition"
        >
          <RefreshCw className="w-3.5 h-3.5" /> Refresh Pipeline
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column (5 Cols): Launch Form */}
        <div className="lg:col-span-5 bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-2xl space-y-4">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-300 flex items-center gap-2 pb-2 border-b border-slate-800">
            <Cpu className="w-4 h-4 text-emerald-400" /> Pipeline Parameters & Execution
          </h3>

          <form onSubmit={handleLaunchJob} className="space-y-4 text-xs">
            <div>
              <label className="block text-slate-300 font-medium mb-1">Target Monitoring Zone</label>
              <select
                value={selectedZoneId}
                onChange={(e) => setSelectedZoneId(Number(e.target.value))}
                className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-white focus:outline-none focus:border-emerald-500"
              >
                {zones.map(z => (
                  <option key={z.id} value={z.id}>{z.name} ({z.district})</option>
                ))}
              </select>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-slate-300 font-medium mb-1">Historical Baseline Scene</label>
                <select
                  value={histSceneId}
                  onChange={(e) => setHistSceneId(Number(e.target.value))}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-white focus:outline-none focus:border-emerald-500"
                >
                  {scenes.map(s => (
                    <option key={s.id} value={s.id}>{s.acquisition_date}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-slate-300 font-medium mb-1">Recent Scene</label>
                <select
                  value={recentSceneId}
                  onChange={(e) => setRecentSceneId(Number(e.target.value))}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-white focus:outline-none focus:border-emerald-500"
                >
                  {scenes.map(s => (
                    <option key={s.id} value={s.id}>{s.acquisition_date}</option>
                  ))}
                </select>
              </div>
            </div>

            <div>
              <label className="block text-slate-300 font-medium mb-1">Detection Strategy Architecture</label>
              <select
                value={algorithm}
                onChange={(e) => setAlgorithm(e.target.value)}
                className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-white focus:outline-none focus:border-emerald-500"
              >
                <option value="SPECTRAL_NDVI_NDBI_DIFFERENCING">Spectral Index Differencing (VARI/NDVI & Gray Difference)</option>
                <option value="DEEP_LEARNING_SEGMENTATION">Deep Learning Building Edge Feature Extractor (U-Net Interface)</option>
                <option value="OPTICAL_DIFFERENCE">Multi-Band Optical Reflectance Differencing</option>
              </select>
            </div>

            <div>
              <div className="flex justify-between items-center text-slate-300 mb-1">
                <span>Reflectance Sensitivity Threshold:</span>
                <span className="font-mono text-cyan-400 font-bold">{threshold}</span>
              </div>
              <input
                type="range"
                min="0.05"
                max="0.40"
                step="0.01"
                value={threshold}
                onChange={(e) => setThreshold(parseFloat(e.target.value))}
                className="w-full accent-emerald-500 cursor-pointer"
              />
            </div>

            <button
              type="submit"
              disabled={launching}
              className="w-full py-2.5 bg-gradient-to-r from-emerald-600 to-cyan-600 hover:from-emerald-500 hover:to-cyan-500 text-white rounded-lg font-semibold flex items-center justify-center gap-2 shadow-lg shadow-emerald-950/50 transition duration-150 disabled:opacity-50"
            >
              <Play className="w-4 h-4 fill-white" />
              {launching ? 'Initializing Pipeline...' : 'Execute Change Detection'}
            </button>
          </form>

          <div className="border-t border-slate-800 pt-4 space-y-3">
            <div>
              <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-300">LEVIR-CD+ Building Change Model</h3>
              <p className="text-[11px] text-slate-500 mt-1">Runs the trained model on the selected earlier and recent scenes.</p>
            </div>
            <button
              type="button"
              onClick={handleLevirPrediction}
              disabled={predictingLevir || scenes.length < 2 || histSceneId === recentSceneId}
              className="w-full py-2 bg-slate-800 hover:bg-slate-700 text-white rounded-lg text-xs font-semibold disabled:opacity-50"
            >
              {predictingLevir ? 'Predicting…' : 'Run LEVIR-CD+ Prediction'}
            </button>
            {levirPrediction && (
              <div className="rounded-lg border border-slate-800 bg-slate-950 p-3 space-y-2">
                <div className="text-xs text-cyan-300 font-semibold">
                  {levirPrediction.changed_pixel_percentage}% potential building change pixels
                </div>
                <div className="text-[10px] text-slate-500">
                  {levirPrediction.changed_pixels.toLocaleString()} of {levirPrediction.total_pixels.toLocaleString()} pixels · threshold {levirPrediction.threshold}
                </div>
                <img
                  src={levirPrediction.overlay_url}
                  alt="LEVIR-CD+ potential building change overlay"
                  className="w-full rounded-md border border-slate-800"
                />
                <div className="flex gap-3 text-[11px]">
                  <a className="text-cyan-400 hover:underline" href={levirPrediction.mask_url} target="_blank" rel="noreferrer">View change mask</a>
                  <a className="text-cyan-400 hover:underline" href={levirPrediction.overlay_url} target="_blank" rel="noreferrer">Open overlay</a>
                </div>
                <p className="text-[10px] leading-relaxed text-amber-300">{levirPrediction.disclaimer}</p>
              </div>
            )}
          </div>

          {/* Active Progress Card */}
          {activeJob && (
            <div className="bg-slate-950 p-4 rounded-xl border border-slate-800 space-y-2 mt-4">
              <div className="flex items-center justify-between text-xs">
                <span className="font-mono font-bold text-emerald-400">{activeJob.job_code}</span>
                <span className="text-[11px] font-semibold text-slate-300">{activeJob.status}</span>
              </div>
              <div className="w-full bg-slate-800 h-2 rounded-full overflow-hidden">
                <div
                  className="bg-emerald-500 h-full transition-all duration-300"
                  style={{ width: `${activeJob.progress}%` }}
                />
              </div>
              <div className="flex justify-between items-center text-[10px] text-slate-500 font-mono">
                <span>Progress: {activeJob.progress}%</span>
                {activeJob.status === 'COMPLETED' && <span className="text-emerald-400">Analysis Completed</span>}
              </div>
            </div>
          )}
        </div>

        {/* Right Column (7 Cols): Jobs History & Detected Changes List */}
        <div className="lg:col-span-7 space-y-6">
          {/* Jobs Execution History */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-xl space-y-3">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-2">
              <Clock className="w-4 h-4 text-cyan-400" /> Pipeline Execution Audit ({jobs.length})
            </h3>
            <div className="divide-y divide-slate-800/80 max-h-64 overflow-y-auto pr-1">
              {jobs.map((j) => (
                <div key={j.id} className="py-2.5 flex items-center justify-between text-xs">
                  <div>
                    <span className="font-mono font-bold text-white">{j.job_code}</span>
                    <div className="text-[10px] text-slate-400">{j.algorithm.replace(/_/g, ' ')}</div>
                  </div>
                  <div className="text-right">
                    <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                      j.status === 'COMPLETED' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30' : 'bg-amber-500/10 text-amber-400'
                    }`}>
                      {j.status}
                    </span>
                    <div className="text-[10px] text-slate-500 font-mono mt-0.5">
                      {j.changes_count || 3} candidates identified
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Extracted Candidates Table */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-xl space-y-3">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400 flex items-center justify-between">
              <span className="flex items-center gap-2"><Activity className="w-4 h-4 text-emerald-400" /> Detected Change Polygons ({changes.length})</span>
              <button onClick={() => navigate('/alerts')} className="text-emerald-400 text-xs flex items-center gap-1 font-medium hover:underline">
                View in Alert Center <ArrowRight className="w-3.5 h-3.5" />
              </button>
            </h3>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-950/80 border-b border-slate-800 text-slate-400 text-[11px]">
                  <tr>
                    <th className="py-2 px-3">Classification</th>
                    <th className="py-2 px-3">Risk</th>
                    <th className="py-2 px-3">Area (m²)</th>
                    <th className="py-2 px-3">Centroid</th>
                    <th className="py-2 px-3">Trend</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {changes.slice(0, 5).map((c) => (
                    <tr key={c.id} className="hover:bg-slate-800/40">
                      <td className="py-2.5 px-3 font-semibold text-slate-200">{c.category.replace('_', ' ')}</td>
                      <td className="py-2.5 px-3"><RiskBadge level={c.risk_level} score={c.risk_score} /></td>
                      <td className="py-2.5 px-3 font-mono text-cyan-400">{c.affected_area_sqm.toLocaleString()}</td>
                      <td className="py-2.5 px-3 font-mono text-slate-400 text-[10px]">{c.centroid_lat.toFixed(4)}, {c.centroid_lng.toFixed(4)}</td>
                      <td className="py-2.5 px-3 font-mono text-emerald-400 font-bold">{c.trend}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
