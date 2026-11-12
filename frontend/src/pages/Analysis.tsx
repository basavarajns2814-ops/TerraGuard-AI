import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import {
  DetectionJob, MonitoringZone, SatelliteScene, DetectedChange,
  LevirPredictionResponse, SNUNetPredictionResponse
} from '../types';
import { RiskBadge } from '../components/RiskBadge';
import {
  Activity, Play, CheckCircle, Clock, AlertCircle,
  Layers, Sliders, Cpu, ArrowRight, Eye, RefreshCw, Upload
} from 'lucide-react';

const RGB_IMAGE_EXTENSIONS = /\.(jpe?g|png|tif|tiff|bmp)$/i;

const readImageDimensions = (file: File): Promise<{ width: number; height: number }> =>
  new Promise((resolve, reject) => {
    const objectUrl = URL.createObjectURL(file);
    const image = new Image();
    image.onload = () => {
      URL.revokeObjectURL(objectUrl);
      resolve({ width: image.naturalWidth, height: image.naturalHeight });
    };
    image.onerror = () => {
      URL.revokeObjectURL(objectUrl);
      reject(new Error(`Unable to decode ${file.name}. The file must be a valid RGB image.`));
    };
    image.src = objectUrl;
  });

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
  const [algorithm, setAlgorithm] = useState<string>('SNUNET_CD');
  const [threshold, setThreshold] = useState<number>(0.30);
  const [launching, setLaunching] = useState<boolean>(false);
  const [activeJob, setActiveJob] = useState<DetectionJob | null>(null);
  const [levirPrediction, setLevirPrediction] = useState<LevirPredictionResponse | null>(null);
  const [predictingLevir, setPredictingLevir] = useState(false);
  const [earlierImage, setEarlierImage] = useState<File | null>(null);
  const [laterImage, setLaterImage] = useState<File | null>(null);
  const [earlierPreview, setEarlierPreview] = useState<string | null>(null);
  const [laterPreview, setLaterPreview] = useState<string | null>(null);
  const [snunetThreshold, setSNUNetThreshold] = useState<number>(0.3);
  const [snunetPrediction, setSNUNetPrediction] = useState<SNUNetPredictionResponse | null>(null);
  const [predictingSNUNet, setPredictingSNUNet] = useState(false);
  const [snunetError, setSNUNetError] = useState<string | null>(null);
  const zoneScenes = scenes
    .filter((scene) => scene.zone_id === selectedZoneId && Boolean(scene.metadata_json?.raster_url))
    .sort((a, b) => a.acquisition_date.localeCompare(b.acquisition_date));

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

      const params = new URLSearchParams(window.location.search);
      const urlZoneId = params.get('zone_id');
      const urlHistId = params.get('hist_scene_id');
      const urlRecentId = params.get('recent_scene_id');

      const targetZoneId = Number(urlZoneId) || z[0]?.id || 0;
      const targetScenes = sc
        .filter((scene) => scene.zone_id === targetZoneId && Boolean(scene.metadata_json?.raster_url))
        .sort((a, b) => a.acquisition_date.localeCompare(b.acquisition_date));
      setSelectedZoneId(targetZoneId);
      const histFromUrl = targetScenes.find((scene) => scene.id === Number(urlHistId));
      const recentFromUrl = targetScenes.find((scene) => scene.id === Number(urlRecentId));
      setHistSceneId(histFromUrl?.id ?? targetScenes[0]?.id ?? 0);
      setRecentSceneId(recentFromUrl?.id ?? targetScenes[targetScenes.length - 1]?.id ?? 0);
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
    const historical = zoneScenes.find((scene) => scene.id === histSceneId);
    const recent = zoneScenes.find((scene) => scene.id === recentSceneId);
    if (!historical || !recent || historical.id === recent.id || historical.acquisition_date >= recent.acquisition_date) {
      alert('Select two native GeoTIFF scenes from this monitoring zone, with the historical date first.');
      return;
    }
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

  const handleEarlierImage = (file: File | null) => {
    if (!file) return;
    setSNUNetError(null);
    setSNUNetPrediction(null);
    if (!RGB_IMAGE_EXTENSIONS.test(file.name)) {
      setSNUNetError('Invalid earlier image format. Use JPG, PNG, TIF, TIFF or BMP.');
      setEarlierImage(null);
      if (earlierPreview) URL.revokeObjectURL(earlierPreview);
      setEarlierPreview(null);
      return;
    }
    if (earlierPreview) URL.revokeObjectURL(earlierPreview);
    setEarlierImage(file);
    setEarlierPreview(URL.createObjectURL(file));
  };

  const handleLaterImage = (file: File | null) => {
    if (!file) return;
    setSNUNetError(null);
    setSNUNetPrediction(null);
    if (!RGB_IMAGE_EXTENSIONS.test(file.name)) {
      setSNUNetError('Invalid later image format. Use JPG, PNG, TIF, TIFF or BMP.');
      setLaterImage(null);
      if (laterPreview) URL.revokeObjectURL(laterPreview);
      setLaterPreview(null);
      return;
    }
    if (laterPreview) URL.revokeObjectURL(laterPreview);
    setLaterImage(file);
    setLaterPreview(URL.createObjectURL(file));
  };

  const handleSNUNetPrediction = async (event: React.FormEvent) => {
    event.preventDefault();
    setSNUNetError(null);
    setSNUNetPrediction(null);

    if (!earlierImage || !laterImage) {
      setSNUNetError('Select both an earlier and a later RGB image.');
      return;
    }
    if (!RGB_IMAGE_EXTENSIONS.test(earlierImage.name) || !RGB_IMAGE_EXTENSIONS.test(laterImage.name)) {
      setSNUNetError('Invalid image format. Use JPG, PNG, TIF, TIFF or BMP.');
      return;
    }

    setPredictingSNUNet(true);
    try {
      const earlierDimensions = await readImageDimensions(earlierImage);
      const laterDimensions = await readImageDimensions(laterImage);
      if (
        earlierDimensions.width !== laterDimensions.width ||
        earlierDimensions.height !== laterDimensions.height
      ) {
        throw new Error(
          `Image dimensions must match: earlier ${earlierDimensions.width}x${earlierDimensions.height}, later ${laterDimensions.width}x${laterDimensions.height}.`
        );
      }

      const prediction = await api.predictSNUNetChange(
        earlierImage,
        laterImage,
        snunetThreshold
      );
      setSNUNetPrediction(prediction);
    } catch (error: any) {
      setSNUNetError(error?.message || 'SNUNet-CD prediction failed.');
    } finally {
      setPredictingSNUNet(false);
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
                onChange={(e) => {
                  const nextZoneId = Number(e.target.value);
                  const nextScenes = scenes
                    .filter((scene) => scene.zone_id === nextZoneId && Boolean(scene.metadata_json?.raster_url))
                    .sort((a, b) => a.acquisition_date.localeCompare(b.acquisition_date));
                  setSelectedZoneId(nextZoneId);
                  setHistSceneId(nextScenes[0]?.id ?? 0);
                  setRecentSceneId(nextScenes[nextScenes.length - 1]?.id ?? 0);
                }}
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
                  {zoneScenes.map(s => (
                    <option key={s.id} value={s.id}>{s.acquisition_date} · {s.cloud_coverage_percentage.toFixed(1)}% cloud</option>
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
                  {zoneScenes.map(s => (
                    <option key={s.id} value={s.id}>{s.acquisition_date} · {s.cloud_coverage_percentage.toFixed(1)}% cloud</option>
                  ))}
                </select>
              </div>
            </div>

            {zoneScenes.length < 2 && (
              <div className="rounded-lg border border-amber-800 bg-amber-950/30 p-3 text-[11px] text-amber-200">
                This zone needs two acquired native GeoTIFF scenes before real-area SNUNet analysis. Acquire a historical/recent pair in the Imagery page.
                <button type="button" onClick={() => navigate(`/imagery?zone_id=${selectedZoneId}`)} className="ml-2 underline">Acquire scenes</button>
              </div>
            )}

            <div>
              <label className="block text-slate-300 font-medium mb-1">Detection Strategy Architecture</label>
              <select
                value={algorithm}
                onChange={(e) => setAlgorithm(e.target.value)}
                className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-white focus:outline-none focus:border-emerald-500"
              >
                <option value="SNUNET_CD">SNUNet-CD Deep Learning (EXP-02 Trained Checkpoint, Epoch 10)</option>
                <option value="SPECTRAL_NDVI_NDBI_DIFFERENCING">Spectral Index Differencing (VARI/NDVI & Gray Difference)</option>
                <option value="LEVIR_CD_HIST_GRADIENT_BOOSTING">LEVIR-CD+ HistGradientBoosting Building Model</option>
                <option value="OPTICAL_DIFFERENCE">Multi-Band Optical Reflectance Differencing</option>
              </select>
            </div>
            <p className="text-[11px] leading-relaxed text-amber-300">
              The EXP-02 SNUNet-CD checkpoint was trained on LEVIR-CD+ imagery. Sentinel-2 differs in sensor and resolution; its performance has not been independently validated, and model scores are not accuracy estimates.
            </p>

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
              disabled={launching || zoneScenes.length < 2 || !histSceneId || !recentSceneId}
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

          <div className="border-t border-slate-800 pt-4 space-y-3">
            <div>
              <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-300">
                EXP-02 SNUNet-CD Change Model
              </h3>
              <p className="text-[11px] text-slate-500 mt-1">
                Upload an aligned earlier/later image pair for pixel-level visual change inference.
              </p>
            </div>

            <form onSubmit={handleSNUNetPrediction} className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <label className="block rounded-lg border border-dashed border-slate-700 bg-slate-950 p-2 cursor-pointer hover:border-cyan-500 transition">
                  <span className="block text-[10px] text-slate-400 mb-1">Earlier RGB image</span>
                  <input
                    type="file"
                    accept=".jpg,.jpeg,.png,.tif,.tiff,.bmp,image/jpeg,image/png,image/tiff,image/bmp"
                    onChange={(event) => handleEarlierImage(event.target.files?.[0] || null)}
                    className="block w-full text-[10px] text-slate-400 file:mr-2 file:rounded file:border-0 file:bg-slate-800 file:px-2 file:py-1 file:text-[10px] file:text-white"
                  />
                  {earlierPreview && (
                    <img src={earlierPreview} alt="Earlier upload preview" className="mt-2 h-24 w-full object-contain rounded border border-slate-800" />
                  )}
                </label>
                <label className="block rounded-lg border border-dashed border-slate-700 bg-slate-950 p-2 cursor-pointer hover:border-cyan-500 transition">
                  <span className="block text-[10px] text-slate-400 mb-1">Later RGB image</span>
                  <input
                    type="file"
                    accept=".jpg,.jpeg,.png,.tif,.tiff,.bmp,image/jpeg,image/png,image/tiff,image/bmp"
                    onChange={(event) => handleLaterImage(event.target.files?.[0] || null)}
                    className="block w-full text-[10px] text-slate-400 file:mr-2 file:rounded file:border-0 file:bg-slate-800 file:px-2 file:py-1 file:text-[10px] file:text-white"
                  />
                  {laterPreview && (
                    <img src={laterPreview} alt="Later upload preview" className="mt-2 h-24 w-full object-contain rounded border border-slate-800" />
                  )}
                </label>
              </div>

              <div>
                <div className="flex justify-between text-[10px] text-slate-400 mb-1">
                  <span>Probability threshold</span>
                  <span className="font-mono text-cyan-400">{snunetThreshold.toFixed(2)}</span>
                </div>
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.01"
                  value={snunetThreshold}
                  onChange={(event) => setSNUNetThreshold(parseFloat(event.target.value))}
                  className="w-full accent-cyan-500"
                />
              </div>

              <button
                type="submit"
                disabled={predictingSNUNet || !earlierImage || !laterImage}
                className="w-full py-2.5 bg-gradient-to-r from-cyan-700 to-blue-700 hover:from-cyan-600 hover:to-blue-600 text-white rounded-lg text-xs font-semibold flex items-center justify-center gap-2 disabled:opacity-50"
              >
                {predictingSNUNet ? (
                  <>
                    <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                    Running SNUNet-CD inference…
                  </>
                ) : (
                  <>
                    <Upload className="w-4 h-4" /> Run SNUNet-CD Prediction
                  </>
                )}
              </button>
            </form>

            {snunetError && (
              <div className="rounded-lg border border-red-500/30 bg-red-950/30 p-3 text-xs text-red-300 flex items-start gap-2">
                <AlertCircle className="w-4 h-4 flex-none mt-0.5" />
                <span>{snunetError}</span>
              </div>
            )}

            {snunetPrediction && (
              <div className="rounded-lg border border-cyan-500/20 bg-slate-950 p-3 space-y-3">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="text-xs text-cyan-300 font-semibold">{snunetPrediction.model_name}</div>
                    <div className="text-[10px] text-slate-500 mt-1">
                      Epoch {snunetPrediction.epoch ?? 'N/A'} · Threshold {snunetPrediction.threshold}
                    </div>
                  </div>
                  <CheckCircle className="w-4 h-4 text-emerald-400 flex-none" />
                </div>

                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div className="rounded bg-slate-900 border border-slate-800 p-2">
                    <div className="text-[10px] text-slate-500">Changed Pixels</div>
                    <div className="text-white font-mono font-bold">{snunetPrediction.changed_pixels.toLocaleString()}</div>
                  </div>
                  <div className="rounded bg-slate-900 border border-slate-800 p-2">
                    <div className="text-[10px] text-slate-500">Changed Percentage</div>
                    <div className="text-cyan-300 font-mono font-bold">{snunetPrediction.changed_pixel_percentage}%</div>
                  </div>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <figure className="rounded border border-slate-800 overflow-hidden bg-black">
                    <img src={earlierPreview || snunetPrediction.earlier_image_url} alt="Earlier satellite image" className="w-full aspect-video object-contain" />
                    <figcaption className="text-[10px] text-slate-400 px-2 py-1.5 border-t border-slate-800">Earlier image</figcaption>
                  </figure>
                  <figure className="rounded border border-slate-800 overflow-hidden bg-black">
                    <img src={laterPreview || snunetPrediction.later_image_url} alt="Later satellite image" className="w-full aspect-video object-contain" />
                    <figcaption className="text-[10px] text-slate-400 px-2 py-1.5 border-t border-slate-800">Later image</figcaption>
                  </figure>
                  <figure className="rounded border border-slate-800 overflow-hidden bg-black">
                    <img src={snunetPrediction.probability_url} alt="SNUNet-CD probability map" className="w-full aspect-video object-contain" />
                    <figcaption className="text-[10px] text-slate-400 px-2 py-1.5 border-t border-slate-800">Probability map</figcaption>
                  </figure>
                  <figure className="rounded border border-slate-800 overflow-hidden bg-black">
                    <img src={snunetPrediction.mask_url} alt="SNUNet-CD binary change mask" className="w-full aspect-video object-contain" />
                    <figcaption className="text-[10px] text-slate-400 px-2 py-1.5 border-t border-slate-800">Binary change mask</figcaption>
                  </figure>
                  <figure className="sm:col-span-2 rounded border border-slate-800 overflow-hidden bg-black">
                    <img src={snunetPrediction.overlay_url} alt="SNUNet-CD change overlay" className="w-full max-h-80 object-contain" />
                    <figcaption className="text-[10px] text-slate-400 px-2 py-1.5 border-t border-slate-800">Change overlay</figcaption>
                  </figure>
                </div>

                <div className="flex flex-wrap gap-3 text-[11px]">
                  <a className="text-cyan-400 hover:underline" href={snunetPrediction.probability_url} target="_blank" rel="noreferrer">Open probability map</a>
                  <a className="text-cyan-400 hover:underline" href={snunetPrediction.mask_url} target="_blank" rel="noreferrer">Open change mask</a>
                  <a className="text-cyan-400 hover:underline" href={snunetPrediction.overlay_url} target="_blank" rel="noreferrer">Open overlay</a>
                </div>
                <p className="text-[10px] leading-relaxed text-amber-300">{snunetPrediction.disclaimer}</p>
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
              {activeJob.status === 'FAILED' && activeJob.error_message && <div className="text-xs text-rose-300">{activeJob.error_message}</div>}
              {activeJob.status === 'COMPLETED' && (
                <div className="space-y-1 text-[11px] text-slate-300">
                  <div>{activeJob.parameters?.historical_acquisition_date} → {activeJob.parameters?.recent_acquisition_date} · {activeJob.parameters?.analysis_crs}</div>
                  <div>Valid common-grid pixels: {activeJob.parameters?.valid_pixel_count?.toLocaleString()} ({activeJob.parameters?.valid_pixel_coverage_percentage}%)</div>
                  <div>{activeJob.changes_count ?? 0} candidate polygons · {activeJob.parameters?.total_changed_hectares ?? 0} ha candidate area</div>
                  {activeJob.changes_count === 0 && <div className="text-amber-300">No candidates passed this run’s thresholds. This is not evidence that the area has no encroachment.</div>}
                  <div className="text-amber-300">SNUNet was trained on LEVIR-CD+ imagery; Sentinel-2 is a different sensor and resolution domain. This result has not been independently validated for Sentinel-2 and is not an accuracy claim.</div>
                </div>
              )}
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
                      {j.changes_count ?? 0} candidates identified
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
                    <th className="py-2 px-3">Area (ha)</th>
                    <th className="py-2 px-3">SNUNet mean</th>
                    <th className="py-2 px-3">Composite</th>
                    <th className="py-2 px-3">Centroid</th>
                    <th className="py-2 px-3">Trend</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {changes.slice(0, 5).map((c) => (
                    <tr key={c.id} className="hover:bg-slate-800/40">
                      <td className="py-2.5 px-3 font-semibold text-slate-200">{c.category.replace('_', ' ')}</td>
                      <td className="py-2.5 px-3"><RiskBadge level={c.risk_level} score={c.risk_score} /></td>
                      <td className="py-2.5 px-3 font-mono text-cyan-400">{c.affected_area_hectares.toFixed(3)}</td>
                      <td className="py-2.5 px-3 font-mono text-cyan-300">{c.model_mean_probability == null ? '—' : `${(c.model_mean_probability * 100).toFixed(1)}%`}</td>
                      <td className="py-2.5 px-3 font-mono text-slate-300">{(c.confidence_score * 100).toFixed(1)}%</td>
                      <td className="py-2.5 px-3 font-mono text-slate-400 text-[10px]">{c.centroid_lat.toFixed(4)}, {c.centroid_lng.toFixed(4)}</td>
                      <td className="py-2.5 px-3 font-mono text-emerald-400 font-bold">{c.trend}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {changes.length === 0 && <p className="text-[11px] text-amber-300">No candidate polygons are currently stored. Zero candidates do not establish that no land change or encroachment occurred.</p>}
          </div>
        </div>
      </div>
    </div>
  );
};
