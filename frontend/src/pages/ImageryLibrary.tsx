import React, { useState, useEffect } from 'react';
import { api } from '../api/client';
import { SatelliteScene, MonitoringZone } from '../types';
import { ImageCompareSlider } from '../components/ImageCompareSlider';
import {
  Satellite, Upload, Search, Calendar, Cloud,
  Layers, ArrowRight, Eye, CheckCircle, Sliders
} from 'lucide-react';

export const ImageryLibrary: React.FC = () => {
  const [scenes, setScenes] = useState<SatelliteScene[]>([]);
  const [zones, setZones] = useState<MonitoringZone[]>([]);
  const [loading, setLoading] = useState<boolean>(true);

  // Comparison selection
  const [historicalSceneId, setHistoricalSceneId] = useState<number | null>(null);
  const [recentSceneId, setRecentSceneId] = useState<number | null>(null);

  // Upload modal state
  const [showUploadModal, setShowUploadModal] = useState<boolean>(false);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadTitle, setUploadTitle] = useState<string>('');
  const [uploadDate, setUploadDate] = useState<string>('2026-10-23');
  const [uploadZoneId, setUploadZoneId] = useState<number | undefined>(undefined);
  const [uploading, setUploading] = useState<boolean>(false);

  // Copernicus Search
  const [searchProviderResults, setSearchProviderResults] = useState<any[]>([]);
  const [searching, setSearching] = useState<boolean>(false);

  useEffect(() => {
    const loadImagery = async () => {
      try {
        const [sc, z] = await Promise.all([
          api.getImagery(),
          api.getZones()
        ]);
        setScenes(sc);
        setZones(z);
        if (sc.length >= 2) {
          // Default historical is earliest, recent is latest
          setHistoricalSceneId(sc[sc.length - 1].id);
          setRecentSceneId(sc[0].id);
        }
      } catch (e) {
        console.error("Failed to load imagery:", e);
      } finally {
        setLoading(false);
      }
    };
    loadImagery();
  }, []);

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!uploadFile || !uploadTitle) return;
    setUploading(true);
    try {
      const formData = new FormData();
      formData.append('file', uploadFile);
      formData.append('title', uploadTitle);
      formData.append('acquisition_date', uploadDate);
      if (uploadZoneId) formData.append('zone_id', String(uploadZoneId));
      formData.append('provider', 'LOCAL_UPLOAD');

      const created = await api.uploadImagery(formData);
      setScenes([created, ...scenes]);
      setShowUploadModal(false);
      setUploadTitle('');
      setUploadFile(null);
    } catch (e: any) {
      alert(e.message || "Failed to upload image");
    } finally {
      setUploading(false);
    }
  };

  const handleSearchCopernicus = async () => {
    setSearching(true);
    try {
      const res = await api.searchCopernicus(zones[0]?.id || 1);
      setSearchProviderResults(res.results || []);
    } catch (e: any) {
      alert(e.message);
    } finally {
      setSearching(false);
    }
  };

  const histScene = scenes.find(s => s.id === historicalSceneId);
  const recScene = scenes.find(s => s.id === recentSceneId);

  return (
    <div className="space-y-6">
      {/* Title & Actions Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b border-slate-800/80">
        <div>
          <h2 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
            Satellite Imagery Repository & Scene Comparer
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Manage Sentinel-2, Sentinel-1 radar, and high-resolution optical scene datasets.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={handleSearchCopernicus}
            disabled={searching}
            className="px-3.5 py-2 rounded-lg bg-slate-900 border border-slate-800 hover:border-slate-700 text-slate-300 text-xs font-medium flex items-center gap-1.5 transition"
          >
            <Search className="w-3.5 h-3.5 text-cyan-400" />
            {searching ? 'Querying CDSE...' : 'Search Copernicus Hub'}
          </button>
          <button
            onClick={() => setShowUploadModal(true)}
            className="px-3.5 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold flex items-center gap-1.5 shadow transition"
          >
            <Upload className="w-4 h-4" /> Upload Georeferenced Scene
          </button>
        </div>
      </div>

      {/* Side-by-Side / Swipe Scene Comparator */}
      {histScene && recScene && (
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-2xl space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-800">
            <div className="flex items-center gap-2">
              <Sliders className="w-4 h-4 text-emerald-400" />
              <h3 className="text-sm font-bold text-white">Interactive Dual-Date Comparison</h3>
            </div>

            {/* Selectors */}
            <div className="flex flex-wrap items-center gap-3 text-xs">
              <div className="flex items-center gap-1.5">
                <span className="text-slate-400">Historical:</span>
                <select
                  value={historicalSceneId || ''}
                  onChange={(e) => setHistoricalSceneId(Number(e.target.value))}
                  className="bg-slate-950 border border-slate-800 rounded-lg px-2.5 py-1 text-slate-200 focus:outline-none focus:border-emerald-500"
                >
                  {scenes.map(s => (
                    <option key={s.id} value={s.id}>{s.acquisition_date} - {s.title.slice(0, 24)}...</option>
                  ))}
                </select>
              </div>

              <div className="flex items-center gap-1.5">
                <span className="text-slate-400">Recent:</span>
                <select
                  value={recentSceneId || ''}
                  onChange={(e) => setRecentSceneId(Number(e.target.value))}
                  className="bg-slate-950 border border-slate-800 rounded-lg px-2.5 py-1 text-slate-200 focus:outline-none focus:border-emerald-500"
                >
                  {scenes.map(s => (
                    <option key={s.id} value={s.id}>{s.acquisition_date} - {s.title.slice(0, 24)}...</option>
                  ))}
                </select>
              </div>
            </div>
          </div>

          <ImageCompareSlider
            historicalImage={histScene.image_url}
            recentImage={recScene.image_url}
            maskImage="/storage/masks/mask_demo.png"
            historicalDate={histScene.acquisition_date}
            recentDate={recScene.acquisition_date}
          />
        </div>
      )}

      {/* Imagery Scene Cards Grid */}
      <div>
        <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-3 flex items-center gap-2">
          <Satellite className="w-4 h-4 text-emerald-400" /> Acquired Satellite Scenes ({scenes.length})
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {scenes.map((s) => (
            <div key={s.id} className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-xl space-y-2">
              <div className="relative aspect-video bg-black overflow-hidden">
                <img
                  src={s.image_url}
                  alt={s.title}
                  className="w-full h-full object-cover"
                />
                <span className="absolute top-2 right-2 px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-slate-950/80 backdrop-blur text-emerald-400 border border-slate-700">
                  {s.provider}
                </span>
              </div>

              <div className="p-4 space-y-2 text-xs">
                <h4 className="font-bold text-white text-sm line-clamp-1">{s.title}</h4>
                <div className="flex items-center justify-between text-slate-400">
                  <span className="flex items-center gap-1">
                    <Calendar className="w-3.5 h-3.5 text-cyan-400" /> {s.acquisition_date}
                  </span>
                  <span className="flex items-center gap-1">
                    <Cloud className="w-3.5 h-3.5 text-slate-400" /> {s.cloud_coverage_percentage}% Cloud
                  </span>
                </div>
                <div className="text-[11px] text-slate-500 pt-2 border-t border-slate-800 flex justify-between">
                  <span>Spatial Res: {s.resolution_meters}m</span>
                  <span className="text-emerald-400 font-mono">Calibrated L2A</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Upload Scene Modal */}
      {showUploadModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-4">
            <h3 className="text-sm font-bold text-white flex items-center gap-2">
              <Upload className="w-4 h-4 text-emerald-400" /> Upload Satellite / Orthophoto Image
            </h3>

            <form onSubmit={handleUpload} className="space-y-3 text-xs">
              <div>
                <label className="block text-slate-300 font-medium mb-1">Scene Title</label>
                <input
                  type="text"
                  required
                  value={uploadTitle}
                  onChange={(e) => setUploadTitle(e.target.value)}
                  placeholder="e.g. Sentinel-2 L2A Pass - Zone 1 Oct 2026"
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-white focus:outline-none focus:border-emerald-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-300 font-medium mb-1">Acquisition Date</label>
                  <input
                    type="date"
                    required
                    value={uploadDate}
                    onChange={(e) => setUploadDate(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-white focus:outline-none focus:border-emerald-500"
                  />
                </div>
                <div>
                  <label className="block text-slate-300 font-medium mb-1">Monitoring Zone</label>
                  <select
                    value={uploadZoneId || ''}
                    onChange={(e) => setUploadZoneId(Number(e.target.value) || undefined)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-white focus:outline-none focus:border-emerald-500"
                  >
                    <option value="">Select Zone</option>
                    {zones.map(z => (
                      <option key={z.id} value={z.id}>{z.name}</option>
                    ))}
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-slate-300 font-medium mb-1">Image File (PNG, JPG, TIFF)</label>
                <input
                  type="file"
                  required
                  accept="image/png,image/jpeg,image/tiff"
                  onChange={(e) => setUploadFile(e.target.files ? e.target.files[0] : null)}
                  className="w-full text-xs text-slate-400 file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-slate-800 file:text-slate-200"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowUploadModal(false)}
                  className="px-4 py-2 bg-slate-800 text-slate-300 rounded-lg hover:bg-slate-700"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={uploading}
                  className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white font-semibold rounded-lg shadow"
                >
                  {uploading ? 'Processing Image...' : 'Upload Scene'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
