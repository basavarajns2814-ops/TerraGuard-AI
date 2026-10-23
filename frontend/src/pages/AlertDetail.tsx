import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import { Alert, User, AlertStatus } from '../types';
import { useAuth } from '../context/AuthContext';
import { ImageCompareSlider } from '../components/ImageCompareSlider';
import { RiskBadge } from '../components/RiskBadge';
import { StatusBadge } from '../components/StatusBadge';
import { GISMapViewer } from '../components/GISMapViewer';
import {
  ShieldAlert, ArrowLeft, Calendar, MapPin, User as UserIcon,
  MessageSquare, Camera, Download, CheckCircle, Clock,
  Send, Upload, AlertCircle, FileText, ChevronRight
} from 'lucide-react';

export const AlertDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { user, isOfficer } = useAuth();

  const [alert, setAlert] = useState<Alert | null>(null);
  const [officers, setOfficers] = useState<User[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string>('');

  // Interactive controls
  const [newNote, setNewNote] = useState<string>('');
  const [submittingNote, setSubmittingNote] = useState<boolean>(false);
  const [selectedStatus, setSelectedStatus] = useState<AlertStatus>('NEW');
  const [statusReason, setStatusReason] = useState<string>('');
  const [showStatusModal, setShowStatusModal] = useState<boolean>(false);

  // Evidence upload
  const [evidenceFile, setEvidenceFile] = useState<File | null>(null);
  const [evidenceCaption, setEvidenceCaption] = useState<string>('');
  const [uploadingEvidence, setUploadingEvidence] = useState<boolean>(false);

  useEffect(() => {
    const fetchDetail = async () => {
      if (!id) return;
      try {
        const [a, off] = await Promise.all([
          api.getAlert(Number(id)),
          api.getOfficers()
        ]);
        setAlert(a);
        setSelectedStatus(a.status);
        setOfficers(off);
      } catch (e: any) {
        setError(e.message || 'Failed to load alert record');
      } finally {
        setLoading(false);
      }
    };
    fetchDetail();
  }, [id]);

  const handleStatusChange = async () => {
    if (!alert) return;
    try {
      const updated = await api.updateAlertStatus(
        alert.id,
        selectedStatus,
        selectedStatus === 'DISMISSED' ? statusReason : undefined,
        selectedStatus === 'RESOLVED' ? statusReason : undefined
      );
      setAlert(updated);
      setShowStatusModal(false);
      setStatusReason('');
    } catch (e: any) {
      window.alert(e.message);
    }
  };

  const handleAssignOfficer = async (officerId: number) => {
    if (!alert) return;
    try {
      const updated = await api.assignAlert(alert.id, officerId);
      setAlert(updated);
    } catch (e: any) {
      window.alert(e.message);
    }
  };

  const handleAddNote = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!alert || !newNote.trim()) return;
    setSubmittingNote(true);
    try {
      await api.addAlertNote(alert.id, newNote.trim());
      // Refresh alert
      const refreshed = await api.getAlert(alert.id);
      setAlert(refreshed);
      setNewNote('');
    } catch (e: any) {
      window.alert(e.message);
    } finally {
      setSubmittingNote(false);
    }
  };

  const handleUploadEvidence = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!alert || !evidenceFile) return;
    setUploadingEvidence(true);
    try {
      const formData = new FormData();
      formData.append('file', evidenceFile);
      if (evidenceCaption) formData.append('caption', evidenceCaption);
      formData.append('latitude', String(alert.centroid_lat));
      formData.append('longitude', String(alert.centroid_lng));

      await api.uploadAlertEvidence(alert.id, formData);
      const refreshed = await api.getAlert(alert.id);
      setAlert(refreshed);
      setEvidenceFile(null);
      setEvidenceCaption('');
    } catch (e: any) {
      window.alert(e.message);
    } finally {
      setUploadingEvidence(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96 text-slate-400 gap-3">
        <div className="w-6 h-6 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin" />
        <span>Loading Evidence Portfolio & Satellite Imagery...</span>
      </div>
    );
  }

  if (error || !alert) {
    return (
      <div className="p-8 text-center text-slate-400 space-y-4">
        <AlertCircle className="w-12 h-12 text-rose-500 mx-auto" />
        <h3 className="text-lg font-bold text-white">Alert Record Unavailable</h3>
        <p className="text-xs">{error || 'The requested incident does not exist.'}</p>
        <button
          onClick={() => navigate('/alerts')}
          className="px-4 py-2 bg-slate-800 text-white rounded-lg text-xs"
        >
          Return to Alert Center
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12">
      {/* Top Breadcrumb & Status Actions */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-3 border-b border-slate-800">
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate('/alerts')}
            className="p-2 rounded-lg bg-slate-900 border border-slate-800 hover:border-slate-700 text-slate-300 hover:text-white transition"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-mono text-lg font-bold text-emerald-400">{alert.alert_code}</span>
              <RiskBadge level={alert.risk_level} score={alert.risk_score} />
              <StatusBadge status={alert.status} />
            </div>
            <p className="text-xs text-slate-400 mt-0.5">
              {alert.category.replace('_', ' ')} &bull; {alert.zone_name} &bull; Parcel: {alert.parcel_number || 'Cadastral Verification Pending'}
            </p>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Status Dialog Trigger */}
          <button
            onClick={() => setShowStatusModal(true)}
            className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold flex items-center gap-1.5 transition"
          >
            <CheckCircle className="w-3.5 h-3.5 text-emerald-400" /> Update Status
          </button>

          {/* Officer Assignment Dropdown */}
          {isOfficer && (
            <div className="flex items-center gap-1.5">
              <UserIcon className="w-3.5 h-3.5 text-slate-400" />
              <select
                value={alert.assigned_to_id || ''}
                onChange={(e) => handleAssignOfficer(Number(e.target.value))}
                className="bg-slate-900 border border-slate-800 rounded-lg px-2.5 py-1.5 text-slate-200 text-xs focus:outline-none focus:border-emerald-500"
              >
                <option value="">Unassigned</option>
                {officers.map(o => (
                  <option key={o.id} value={o.id}>{o.full_name} ({o.role.replace('_', ' ')})</option>
                ))}
              </select>
            </div>
          )}

          <a
            href={api.getExportPdfUrl(alert.zone_id)}
            download
            className="px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-800 hover:border-slate-700 text-slate-300 text-xs font-medium flex items-center gap-1.5 transition"
          >
            <Download className="w-3.5 h-3.5 text-cyan-400" /> Export Dossier
          </a>
        </div>
      </div>

      {/* Main Evidence Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column (7 Cols): Satellite Swipe Comparison Slider & Focused Map */}
        <div className="lg:col-span-7 space-y-6">
          {/* 1. Satellite Swipe Slider */}
          <div className="space-y-2">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400 flex items-center justify-between">
              <span>Multi-Temporal Satellite Scene Comparison</span>
              <span className="text-emerald-400 font-mono text-[11px]">Sentinel-2 L2A (10m Resolution)</span>
            </h3>
            <ImageCompareSlider
              historicalImage={alert.historical_image_url || '/storage/imagery/sentinel2_hist_20251015.png'}
              recentImage={alert.recent_image_url || '/storage/imagery/sentinel2_recent_20261001.png'}
              maskImage={alert.change_mask_url || '/storage/masks/mask_demo.png'}
              historicalDate={alert.first_observed_date}
              recentDate={alert.latest_observed_date}
            />
          </div>

          {/* 2. Focused GIS Map */}
          <div className="space-y-2">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400 flex items-center justify-between">
              <span>Cadastral Boundary Geospatial Context</span>
              <span className="text-slate-400 font-mono text-[11px]">{alert.centroid_lat.toFixed(5)}, {alert.centroid_lng.toFixed(5)}</span>
            </h3>
            <GISMapViewer
              alerts={[alert]}
              center={[alert.centroid_lat, alert.centroid_lng]}
              zoom={16}
              height="340px"
              focusedCoordinates={[alert.centroid_lat, alert.centroid_lng]}
            />
          </div>

          {/* 3. Temporal Multi-Date Observation Timeline */}
          {alert.temporal_history && alert.temporal_history.length > 0 && (
            <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-4 shadow-lg space-y-3">
              <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
                <Clock className="w-4 h-4 text-cyan-400" /> Multi-Date Temporal Encroachment Progression
              </h4>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                {alert.temporal_history.map((t, i) => (
                  <div key={t.id || i} className="bg-slate-950 p-3 rounded-lg border border-slate-800/80 space-y-1">
                    <div className="flex items-center justify-between text-slate-400 text-[10px]">
                      <span>Observation #{i+1}</span>
                      <span className="font-mono text-emerald-400">{t.observation_date}</span>
                    </div>
                    <div className="text-base font-bold font-mono text-white">{t.area_sqm.toLocaleString()} m²</div>
                    <div className="flex items-center justify-between text-[11px] text-slate-400">
                      <span>Risk: <strong className="text-amber-400 font-mono">{t.risk_score}</strong></span>
                      <span>Confidence: <strong className="text-cyan-400 font-mono">{Math.round(t.confidence_score * 100)}%</strong></span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Right Column (5 Cols): Explainable Scoring, Inspection Notes, Evidence Upload */}
        <div className="lg:col-span-5 space-y-6">
          {/* Metadata & Risk Breakdown */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-xl space-y-4">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-2">
              <ShieldAlert className="w-4 h-4 text-amber-400" /> Explainable Risk Assessment
            </h3>

            {/* Score Grid */}
            <div className="grid grid-cols-2 gap-3">
              <div className="bg-slate-950 p-3 rounded-lg border border-slate-800">
                <span className="text-[10px] text-slate-500 uppercase tracking-wider block">Risk Severity</span>
                <span className="text-xl font-bold font-mono text-rose-400">{alert.risk_score} <span className="text-xs font-normal text-slate-400">/ 100</span></span>
                <span className="block text-[10px] text-slate-400 mt-0.5">{alert.risk_level} Priority</span>
              </div>
              <div className="bg-slate-950 p-3 rounded-lg border border-slate-800">
                <span className="text-[10px] text-slate-500 uppercase tracking-wider block">Detection Confidence</span>
                <span className="text-xl font-bold font-mono text-cyan-400">{Math.round(alert.confidence_score * 100)}%</span>
                <span className="block text-[10px] text-slate-400 mt-0.5">Spectral Difference Quality</span>
              </div>
            </div>

            {/* Candidate Area */}
            <div className="bg-slate-950 p-3 rounded-lg border border-slate-800 flex justify-between items-center text-xs">
              <span className="text-slate-400">Observed Footprint Area:</span>
              <span className="font-mono text-white font-bold">{alert.affected_area_sqm.toLocaleString()} m² ({alert.affected_area_hectares} ha)</span>
            </div>

            {/* Explainable Reasons */}
            <div>
              <span className="text-[10px] uppercase tracking-wider font-semibold text-slate-500 block mb-1.5">Algorithmic Scoring Rationale:</span>
              <ul className="space-y-1.5">
                {(alert.risk_reasons || []).map((reason, i) => (
                  <li key={i} className="text-xs text-slate-300 flex items-start gap-2 bg-slate-950/70 p-2.5 rounded border border-slate-800/80">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 mt-1.5 flex-shrink-0" />
                    <span>{reason}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>

          {/* Field Evidence Photographs */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-xl space-y-4">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-2">
              <Camera className="w-4 h-4 text-emerald-400" /> On-Site Inspection Evidence ({alert.evidence?.length || 0})
            </h3>

            {/* List Evidence Photos */}
            <div className="space-y-3">
              {(!alert.evidence || alert.evidence.length === 0) ? (
                <p className="text-xs text-slate-500 italic">No on-site photographs uploaded yet. Field inspector can attach evidence below.</p>
              ) : (
                alert.evidence.map((ev) => (
                  <div key={ev.id} className="bg-slate-950 rounded-lg border border-slate-800 overflow-hidden">
                    <img
                      src={ev.file_url}
                      alt={ev.caption || 'Inspection Evidence'}
                      className="w-full h-44 object-cover"
                    />
                    <div className="p-3 text-xs space-y-1">
                      <p className="font-medium text-slate-200">{ev.caption || 'Ground verification photo'}</p>
                      <div className="flex items-center justify-between text-[10px] text-slate-500 font-mono">
                        <span>By: {ev.uploaded_by_name}</span>
                        <span>{ev.created_at?.slice(0, 10)}</span>
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>

            {/* Upload Evidence Form */}
            <form onSubmit={handleUploadEvidence} className="pt-3 border-t border-slate-800 space-y-2.5">
              <label className="text-[11px] font-semibold text-slate-300 block">Attach Field Photograph</label>
              <input
                type="file"
                accept="image/*"
                required
                onChange={(e) => setEvidenceFile(e.target.files ? e.target.files[0] : null)}
                className="w-full text-xs text-slate-400 file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-slate-800 file:text-slate-200 hover:file:bg-slate-700 cursor-pointer"
              />
              <input
                type="text"
                placeholder="Caption / Observations (e.g. Earthwork foundation in lake buffer)..."
                value={evidenceCaption}
                onChange={(e) => setEvidenceCaption(e.target.value)}
                className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-emerald-500"
              />
              <button
                type="submit"
                disabled={uploadingEvidence || !evidenceFile}
                className="w-full py-1.5 bg-slate-800 hover:bg-slate-700 text-white rounded-lg text-xs font-semibold flex items-center justify-center gap-1.5 transition disabled:opacity-50"
              >
                <Upload className="w-3.5 h-3.5" />
                {uploadingEvidence ? 'Uploading File...' : 'Upload Ground Evidence'}
              </button>
            </form>
          </div>

          {/* Investigation Notes & Audit Trail */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-xl space-y-4">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-2">
              <MessageSquare className="w-4 h-4 text-cyan-400" /> Officer Investigation Notes & Timeline
            </h3>

            {/* Notes List */}
            <div className="space-y-2.5 max-h-60 overflow-y-auto pr-1">
              {(!alert.notes || alert.notes.length === 0) ? (
                <p className="text-xs text-slate-500 italic">No notes recorded yet.</p>
              ) : (
                alert.notes.map((n) => (
                  <div key={n.id} className="p-3 rounded-lg bg-slate-950 border border-slate-800/80 space-y-1 text-xs">
                    <div className="flex items-center justify-between text-[11px]">
                      <span className="font-semibold text-slate-200">{n.user_name}</span>
                      <span className="text-[10px] text-slate-500 font-mono">{n.created_at?.slice(0, 16).replace('T', ' ')}</span>
                    </div>
                    <p className="text-slate-300 text-xs leading-relaxed">{n.note}</p>
                  </div>
                ))
              )}
            </div>

            {/* Add Note Form */}
            <form onSubmit={handleAddNote} className="pt-3 border-t border-slate-800 flex gap-2">
              <input
                type="text"
                required
                value={newNote}
                onChange={(e) => setNewNote(e.target.value)}
                placeholder="Add official inquiry note or survey remarks..."
                className="flex-1 bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-emerald-500"
              />
              <button
                type="submit"
                disabled={submittingNote || !newNote.trim()}
                className="px-3.5 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-xs font-semibold flex items-center gap-1 transition disabled:opacity-50"
              >
                <Send className="w-3.5 h-3.5" />
              </button>
            </form>
          </div>
        </div>
      </div>

      {/* Status Transition Modal */}
      {showStatusModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-4">
            <h3 className="text-sm font-bold text-white flex items-center gap-2">
              <CheckCircle className="w-4 h-4 text-emerald-400" /> Update Incident Status Workflow
            </h3>
            <p className="text-xs text-slate-400">
              Select the revised administrative or verification status for <span className="font-mono text-emerald-400">{alert.alert_code}</span>:
            </p>

            <div className="space-y-2 text-xs">
              {(['NEW', 'UNDER_REVIEW', 'FIELD_INSPECTION_REQUIRED', 'CONFIRMED', 'DISMISSED', 'RESOLVED'] as AlertStatus[]).map((st) => (
                <label
                  key={st}
                  className={`flex items-center justify-between p-3 rounded-lg border cursor-pointer transition ${
                    selectedStatus === st
                      ? 'bg-emerald-500/10 border-emerald-500 text-white'
                      : 'bg-slate-950 border-slate-800 text-slate-400 hover:border-slate-700'
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <input
                      type="radio"
                      name="status"
                      checked={selectedStatus === st}
                      onChange={() => setSelectedStatus(st)}
                      className="accent-emerald-500"
                    />
                    <span className="font-semibold">{st.replace('_', ' ')}</span>
                  </div>
                  <StatusBadge status={st} />
                </label>
              ))}
            </div>

            {(selectedStatus === 'DISMISSED' || selectedStatus === 'RESOLVED') && (
              <div>
                <label className="text-xs font-semibold text-slate-300 block mb-1">
                  {selectedStatus === 'DISMISSED' ? 'Reason for Dismissal' : 'Resolution Confirmation Details'}
                </label>
                <textarea
                  required
                  rows={3}
                  value={statusReason}
                  onChange={(e) => setStatusReason(e.target.value)}
                  placeholder="Detail survey verification reasons or authorized permit verification..."
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-emerald-500"
                />
              </div>
            )}

            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setShowStatusModal(false)}
                className="px-4 py-2 bg-slate-800 text-slate-300 rounded-lg text-xs font-semibold hover:bg-slate-700"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleStatusChange}
                className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-xs font-semibold shadow"
              >
                Save Status Transition
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
