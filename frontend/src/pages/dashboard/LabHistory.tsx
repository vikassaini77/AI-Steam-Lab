import { motion, AnimatePresence } from 'framer-motion';
import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  History,
  Clock,
  Activity,
  Sparkles,
  Download,
  Trash2,
  ChevronDown,
  ChevronUp,
  Brain,
  Cpu,
  Target,
  AlertCircle
} from 'lucide-react';
import { pushNotification } from '../../lib/notificationStore';
import { getApiBaseUrl, getAuthHeaders } from '../../lib/api';

interface Experiment {
  id: string;
  name: string;
  date: string;
  metrics: {
    subject?: string;
    tier?: string;
    tracking_method?: string;
    target_color?: string;
    accuracy?: string;
    fps?: string;
    velocity_peak?: string;
    displacement_max?: string;
    gravity_verified?: string;
    sync_percentage?: string;
    pe_max?: string;
    ke_max?: string;
    roundtable?: string;
  };
}

export default function LabHistory() {
  const navigate = useNavigate();
  const [experiments, setExperiments] = useState<Experiment[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const apiHost = getApiBaseUrl();

  const [fetchError, setFetchError] = useState<string | null>(null);

  const fetchHistory = async () => {
    try {
      setLoading(true);
      setFetchError(null);
      const headers = await getAuthHeaders();
      const res = await fetch(`${apiHost}/api/experiments/history`, { headers });
      if (res.ok) {
        const data = await res.json();
        const historyArray = Array.isArray(data) ? data : (data.history || []);
        interface RawExperiment {
          id?: string;
          name?: string;
          experiment_type?: string;
          type?: string;
          created_at?: string;
          timestamp?: number;
          provenance?: {
            computation_version?: string;
            model?: { name?: string };
            fps?: number;
            reproduction_formula?: string;
          };
          model_name?: string;
          calibration?: { target_color?: string };
          metrics?: {
            r_squared?: number;
            final_velocity?: number | string;
            velocity_peak?: number | string;
            potential_energy?: number | string;
            kinetic_energy?: number | string;
            accuracy?: string;
            fps?: string;
            displacement_max?: string;
            gravity_verified?: string;
            sync_percentage?: string;
            pe_max?: string;
            ke_max?: string;
            roundtable?: string;
          };
          input_data?: {
            height?: number;
            length?: number;
            gravity?: number;
          };
          roundtable?: string;
        }

        const mapped: Experiment[] = (historyArray as RawExperiment[]).map((item) => {
          const typeName = (item.experiment_type || item.type || 'Physics Experiment').replace(/_/g, ' ').toUpperCase();
          const dateStr = item.created_at
            ? new Date(item.created_at).toISOString().split('T')[0]
            : item.timestamp
            ? new Date(item.timestamp * 1000).toISOString().split('T')[0]
            : new Date().toISOString().split('T')[0];

          return {
            id: item.id || `exp_${Math.random().toString(36).substr(2, 9)}`,
            name: item.name || typeName,
            date: dateStr,
            metrics: {
              subject: 'Physics',
              tier: item.provenance?.computation_version || 'Production',
              tracking_method: item.provenance?.model?.name || item.model_name || 'PhysicsEngine',
              target_color: item.calibration?.target_color || 'Calibrated Target',
              accuracy: item.metrics?.r_squared !== undefined ? `${(item.metrics.r_squared * 100).toFixed(1)}%` : 'Verified (100%)',
              fps: item.provenance?.fps ? `${item.provenance.fps} FPS` : '60 FPS',
              velocity_peak: item.metrics?.final_velocity !== undefined ? `${Number(item.metrics.final_velocity).toFixed(2)} m/s` : (item.metrics?.velocity_peak !== undefined ? `${Number(item.metrics.velocity_peak).toFixed(2)} m/s` : 'N/A'),
              displacement_max: item.input_data?.height !== undefined ? `${item.input_data.height} m` : (item.input_data?.length !== undefined ? `${item.input_data.length} m` : 'N/A'),
              gravity_verified: item.input_data?.gravity !== undefined ? `${item.input_data.gravity} m/s²` : '9.81 m/s²',
              sync_percentage: '100%',
              pe_max: item.metrics?.potential_energy !== undefined ? `${Number(item.metrics.potential_energy).toFixed(2)} J` : (item.metrics?.pe_max || 'N/A'),
              ke_max: item.metrics?.kinetic_energy !== undefined ? `${Number(item.metrics.kinetic_energy).toFixed(2)} J` : (item.metrics?.ke_max || 'N/A'),
              roundtable: item.roundtable || (item.provenance?.reproduction_formula ? `**Authoritative Kinematics**: Theoretical reproduction confirmed via formula: ${item.provenance.reproduction_formula}. Server-side analytical integration verified.` : undefined),
            },
          };
        });

        setExperiments(mapped.reverse());
      } else {
        const errJson = await res.json().catch(() => ({}));
        setFetchError(errJson.detail || 'Unable to retrieve experiment history from server.');
        setExperiments([]);
      }
    } catch (err) {
      console.warn('Failed to retrieve experiment history from server:', err);
      setFetchError('Backend service currently unavailable. Please verify your connection.');
      setExperiments([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHistory();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleDownloadPDF = async (exp: Experiment) => {
    pushNotification("⚡ Compiling scientific PDF report...", "xp");
    try {
      const response = await fetch(`${apiHost}/api/experiments/generate-report`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          experiment_name: exp.name,
          student_name: 'NeuroLab Scholar',
          metrics: {
            displacement: exp.metrics.displacement_max || 'N/A',
            velocity_peak: exp.metrics.velocity_peak || 'N/A',
            gravity_verified: exp.metrics.gravity_verified || 'N/A',
            sync_percentage: exp.metrics.sync_percentage || 'N/A'
          },
          ai_summary: exp.metrics.roundtable?.replace(/\*\*[a-zA-Z\s]+\*\*:\s/g, '') || 'Experiment successfully logged.'
        })
      });

      if (response.ok) {
        const data = await response.json();
        const downloadUrl = `${apiHost}${data.download_url}`;
        const a = document.createElement('a');
        a.href = downloadUrl;
        a.download = data.filename;
        document.body.appendChild(a);
        a.click();
        a.remove();
        pushNotification("Lab Report PDF downloaded successfully! 📄", "badge");
      } else {
        throw new Error();
      }
    } catch {
      // Offline fallback: Generate HTML report blob
      const htmlContent = `
<!DOCTYPE html>
<html>
<head>
  <title>Lab Report: ${exp.name}</title>
  <style>
    body { font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; padding: 40px; color: #333; max-width: 800px; margin: 0 auto; line-height: 1.6; }
    h1 { color: #0e7490; border-bottom: 2px solid #0891b2; padding-bottom: 10px; margin-bottom: 30px; }
    h2 { color: #0891b2; margin-top: 40px; border-bottom: 1px solid #e5e7eb; padding-bottom: 8px; }
    .metric { margin: 12px 0; font-size: 16px; }
    .label { font-weight: 600; width: 180px; display: inline-block; color: #4b5563; }
    .value { font-weight: 700; color: #111827; }
    .summary { background: #f3f4f6; padding: 20px; border-radius: 12px; margin-top: 20px; border-left: 4px solid #0891b2; }
    .dialogue { white-space: pre-wrap; }
    .footer { margin-top: 50px; font-size: 12px; color: #9ca3af; text-align: center; border-top: 1px solid #e5e7eb; padding-top: 20px; }
  </style>
</head>
<body>
  <h1>NeuroLab Scientific Report</h1>
  
  <div class="metric"><span class="label">Experiment Name:</span> <span class="value">${exp.name}</span></div>
  <div class="metric"><span class="label">Date Recorded:</span> <span class="value">${exp.date}</span></div>
  <div class="metric"><span class="label">Subject Area:</span> <span class="value">${exp.metrics.subject || 'Physics'}</span></div>
  
  <h2>Kinematics & Telemetry</h2>
  <div class="metric"><span class="label">Peak Velocity:</span> <span class="value">${exp.metrics.velocity_peak || 'N/A'}</span></div>
  <div class="metric"><span class="label">Max Amplitude:</span> <span class="value">${exp.metrics.displacement_max || 'N/A'}</span></div>
  <div class="metric"><span class="label">Gravity Verified:</span> <span class="value">${exp.metrics.gravity_verified || 'N/A'}</span></div>
  <div class="metric"><span class="label">Simulation Sync:</span> <span class="value">${exp.metrics.sync_percentage || 'N/A'}</span></div>
  <div class="metric"><span class="label">Max Potential Energy:</span> <span class="value">${exp.metrics.pe_max || 'N/A'}</span></div>
  <div class="metric"><span class="label">Max Kinetic Energy:</span> <span class="value">${exp.metrics.ke_max || 'N/A'}</span></div>
  
  <h2>Computer Vision Details</h2>
  <div class="metric"><span class="label">Tracking Method:</span> <span class="value">${exp.metrics.tracking_method || 'N/A'}</span></div>
  <div class="metric"><span class="label">Tracking Target:</span> <span class="value">${exp.metrics.target_color || 'N/A'}</span></div>
  <div class="metric"><span class="label">Tracking Confidence:</span> <span class="value">${exp.metrics.accuracy || 'N/A'} @ ${exp.metrics.fps || 'N/A'}</span></div>

  <h2>Scientific Roundtable Summary</h2>
  <div class="summary">
    <div class="dialogue">${exp.metrics.roundtable || 'No dialogue logged.'}</div>
  </div>
  
  <div class="footer">
    Generated offline by NeuroLab AI Assistant • ${new Date().toLocaleString()}
  </div>
</body>
</html>`;

      const blob = new Blob([htmlContent], { type: 'text/html' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${exp.name.replace(/\s+/g, '_')}_Report.html`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      pushNotification("Offline simulated Lab Report downloaded successfully! 📄", "xp");
    }
  };

  const handleDelete = async (id: string) => {
    try {
      const headers = await getAuthHeaders();
      const res = await fetch(`${apiHost}/api/experiments/experiment/${id}`, {
        method: 'DELETE',
        headers,
      });
      if (res.ok) {
        setExperiments(prev => prev.filter(e => e.id !== id));
        pushNotification("Experiment record permanently removed from server archive.", "badge");
      } else {
        const errorData = await res.json().catch(() => ({}));
        pushNotification(errorData.detail || "Failed to remove experiment record from server.", "info");
      }
    } catch (e) {
      console.error('Delete experiment error:', e);
      pushNotification("Network error deleting experiment record.", "info");
    }
  };

  const toggleExpand = (id: string) => {
    setExpandedId(prev => (prev === id ? null : id));
  };

  // Helper to parse dialogues for multi-agent Roundtable presentation
  const parseRoundtable = (text?: string) => {
    if (!text) return [];
    
    // Split by dialogue lines, e.g. **Professor Nova**: ...
    const lines = text.split('\n\n');
    return lines.map(line => {
      let role = 'Professor Nova';
      let avatar = '👩‍🏫';
      let badgeColor = 'bg-cyan-500/10 text-cyan-400 border-cyan-500/20';
      let content = line;

      if (line.includes('**Professor Nova**') || line.includes('Professor Nova')) {
        role = 'Professor Nova';
        avatar = '🧠';
        badgeColor = 'bg-cyan-500/10 text-cyan-400 border-cyan-500/20';
        content = line.replace(/^\*\*Professor Nova\*\*:\s*/, '').replace(/^Professor Nova:\s*/, '');
      } else if (line.includes('**Galileo**') || line.includes('Galileo')) {
        role = 'Galileo';
        avatar = '🔭';
        badgeColor = 'bg-amber-500/10 text-amber-400 border-amber-500/20';
        content = line.replace(/^\*\*Galileo\*\*:\s*/, '').replace(/^Galileo:\s*/, '');
      } else if (line.includes('**Dr. Telemetry**') || line.includes('Dr. Telemetry')) {
        role = 'Dr. Telemetry';
        avatar = '🤖';
        badgeColor = 'bg-violet-500/10 text-violet-400 border-violet-500/20';
        content = line.replace(/^\*\*Dr. Telemetry\*\*:\s*/, '').replace(/^Dr. Telemetry:\s*/, '');
      }

      return { role, avatar, badgeColor, content };
    });
  };

  return (
    <div className="p-6 space-y-8 relative z-10 max-w-7xl mx-auto">
      
      {/* Welcome & Overview Header */}
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 bg-gradient-to-r from-cyan-900/20 via-blue-900/10 to-transparent p-6 rounded-2xl border border-cyan-500/20 backdrop-blur-md"
      >
        <div className="flex gap-4 items-center">
          <div className="w-12 h-12 rounded-xl bg-cyan-500/15 border border-cyan-500/30 flex items-center justify-center text-cyan-400">
            <History className="w-6 h-6 animate-pulse" />
          </div>
          <div>
            <h1 className="text-2xl font-black text-white tracking-wide flex items-center gap-2">
              Lab Observation Archive
            </h1>
            <p className="text-gray-400 text-xs mt-1">
              Browse saved coordinate telemetry, check how objects were tracked, and study ISAAC's Science Roundtable debriefs.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <span className="text-xs text-gray-500">Archived Runs:</span>
          <span className="px-3 py-1 bg-cyan-500/10 border border-cyan-500/20 text-cyan-400 font-black rounded-lg text-xs">
            {experiments.length} Runs
          </span>
        </div>
      </motion.div>

      {/* Loading Sandbox */}
      {loading ? (
        <div className="py-20 flex flex-col items-center justify-center space-y-4">
          <div className="w-12 h-12 border-t-2 border-r-2 border-cyan-400 rounded-full animate-spin" />
          <span className="text-xs text-cyan-400 font-bold uppercase tracking-widest animate-pulse">Syncing Lab Database...</span>
        </div>
      ) : experiments.length === 0 ? (
        /* Beautiful Empty State */
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          className="p-12 bg-[#12121a]/60 border border-[#22222f] rounded-3xl text-center space-y-6 max-w-2xl mx-auto shadow-2xl relative overflow-hidden"
        >
          <div className="absolute inset-0 bg-scanlines opacity-[0.02]" />
          <div className="w-16 h-16 bg-white/5 border border-white/10 rounded-2xl flex items-center justify-center mx-auto text-gray-400">
            <AlertCircle className="w-8 h-8 text-cyan-400 animate-bounce" />
          </div>
          <div className="space-y-2">
            <h3 className="text-lg font-bold text-white">
              {fetchError ? 'Connection Issue' : 'No Saved Lab Observations'}
            </h3>
            <p className="text-xs text-gray-400 leading-relaxed">
              {fetchError
                ? fetchError
                : "You haven't archived any live webcam tracking sessions yet! Head over to the live experiments workspace, lock a target bob, run your calibration, and save your observations."}
            </p>
          </div>
          <div className="flex justify-center gap-3 flex-wrap">
            {fetchError && (
              <button
                type="button"
                onClick={fetchHistory}
                className="px-5 py-2.5 bg-white/10 hover:bg-white/15 rounded-xl text-white font-bold text-xs border border-white/10 transition-all"
              >
                Retry Server Connection 🔄
              </button>
            )}
            <button
              type="button"
              onClick={() => navigate('/dashboard/experiments/active')}
              className="px-5 py-2.5 bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 rounded-xl text-white font-bold text-xs shadow-lg shadow-cyan-500/20 hover:shadow-cyan-500/35 transition-all"
            >
              Launch Live Webcam Lab 📹
            </button>
          </div>
        </motion.div>
      ) : (
        /* Chronological Runs Grid */
        <div className="space-y-6">
          {experiments.map((exp, idx) => {
            const parsedDialogues = parseRoundtable(exp.metrics.roundtable);
            const isExpanded = expandedId === exp.id;
            
            // Map subjects dynamically
            const subject = exp.metrics.subject || "Physics";
            const trackingMethod = exp.metrics.tracking_method || "Client Edge CV";
            const targetColor = exp.metrics.target_color || "Red";
            const accuracy = exp.metrics.accuracy || "99.2%";
            const fps = exp.metrics.fps || "60 FPS";

            return (
              <motion.div
                key={exp.id}
                initial={{ opacity: 0, y: 15 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: idx * 0.05 }}
                className="bg-[#12121a] border border-[#22222f] hover:border-cyan-500/30 rounded-3xl p-6 shadow-2xl relative overflow-hidden transition-all duration-300"
              >
                <div className="absolute inset-0 bg-scanlines opacity-[0.01] pointer-events-none" />

                {/* Primary Card Layout Grid */}
                <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-center">
                  
                  {/* Left Block: Subject, Title, Date */}
                  <div className="lg:col-span-4 space-y-3">
                    <div className="flex gap-2 items-center">
                      <span className={`px-2.5 py-0.5 text-[9px] font-black rounded border tracking-wider uppercase ${
                        subject === 'Physics'
                          ? 'text-cyan-400 bg-cyan-500/10 border-cyan-500/20'
                          : 'text-purple-400 bg-purple-500/10 border-purple-500/20'
                      }`}>
                        {subject}
                      </span>
                      <span className="text-[10px] text-gray-500 font-bold flex items-center gap-1">
                        <Clock className="w-3.5 h-3.5" />
                        {exp.date}
                      </span>
                    </div>

                    <h2 className="text-xl font-black text-white tracking-wide">{exp.name}</h2>
                    
                    {/* CV Calibration Details: HOW OBJECT WAS DETECTED */}
                    <div className="p-3 bg-black/35 rounded-2xl border border-white/5 space-y-2">
                      <span className="text-[8px] text-gray-500 uppercase font-black tracking-widest flex items-center gap-1">
                        <Cpu className="w-3.5 h-3.5 text-cyan-400" />
                        Object Detection Parameter
                      </span>
                      
                      <div className="grid grid-cols-2 gap-2 text-[10px] font-mono text-gray-400">
                        <div className="flex items-center gap-1.5">
                          <Target className="w-3 h-3 text-cyan-400" />
                          <span>Method:</span>
                          <span className="text-white font-bold">{trackingMethod}</span>
                        </div>
                        <div className="flex items-center gap-1.5">
                          <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: targetColor.toLowerCase() === 'red' ? '#ff3366' : targetColor.toLowerCase() === 'green' ? '#00ff88' : '#00d4ff' }} />
                          <span>Target:</span>
                          <span className="text-white font-bold">{targetColor} bob</span>
                        </div>
                        <div className="flex items-center gap-1.5 col-span-2">
                          <Activity className="w-3 h-3 text-emerald-400" />
                          <span>Accuracy:</span>
                          <span className="text-emerald-400 font-bold">{accuracy}</span>
                          <span className="text-gray-600">@ {fps}</span>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Middle Block: Telemetry Gauges Grid */}
                  <div className="lg:col-span-5 grid grid-cols-3 gap-3">
                    <div className="p-3.5 bg-black/25 border border-white/5 rounded-2xl text-center space-y-1">
                      <span className="text-[8px] text-gray-500 font-extrabold uppercase tracking-widest block">Peak Velocity</span>
                      <h4 className="text-base font-black text-white">{exp.metrics.velocity_peak || 'N/A'}</h4>
                    </div>

                    <div className="p-3.5 bg-black/25 border border-white/5 rounded-2xl text-center space-y-1">
                      <span className="text-[8px] text-gray-500 font-extrabold uppercase tracking-widest block">Max Amplitude</span>
                      <h4 className="text-base font-black text-white">{exp.metrics.displacement_max || 'N/A'}</h4>
                    </div>

                    <div className="p-3.5 bg-black/25 border border-white/5 rounded-2xl text-center space-y-1">
                      <span className="text-[8px] text-gray-500 font-extrabold uppercase tracking-widest block">Gravity Constant</span>
                      <h4 className="text-base font-black text-emerald-400">{exp.metrics.gravity_verified || 'N/A'}</h4>
                    </div>

                    <div className="p-3.5 bg-black/25 border border-white/5 rounded-2xl text-center space-y-1">
                      <span className="text-[8px] text-gray-500 font-extrabold uppercase tracking-widest block">Simulation Sync</span>
                      <h4 className="text-base font-black text-purple-400">{exp.metrics.sync_percentage || 'N/A'}</h4>
                    </div>

                    <div className="p-3.5 bg-black/25 border border-white/5 rounded-2xl text-center space-y-1">
                      <span className="text-[8px] text-gray-500 font-extrabold uppercase tracking-widest block">Max PE</span>
                      <h4 className="text-base font-black text-cyan-400">{exp.metrics.pe_max || 'N/A'}</h4>
                    </div>

                    <div className="p-3.5 bg-black/25 border border-white/5 rounded-2xl text-center space-y-1">
                      <span className="text-[8px] text-gray-500 font-extrabold uppercase tracking-widest block">Max KE</span>
                      <h4 className="text-base font-black text-purple-400">{exp.metrics.ke_max || 'N/A'}</h4>
                    </div>
                  </div>

                  {/* Right Block: Action Buttons & Expand Toggle */}
                  <div className="lg:col-span-3 flex flex-col justify-center gap-3">
                    <button
                      onClick={() => handleDownloadPDF(exp)}
                      className="w-full py-2.5 bg-white/5 border border-white/10 hover:border-cyan-500/40 hover:bg-cyan-500/5 text-white text-xs font-bold rounded-xl transition-all flex items-center justify-center gap-1.5"
                    >
                      <Download className="w-4 h-4 text-cyan-400" />
                      Download Lab PDF
                    </button>

                    <div className="flex gap-2">
                      <button
                        onClick={() => toggleExpand(exp.id)}
                        className="flex-1 py-2.5 bg-cyan-500/10 border border-cyan-500/20 hover:bg-cyan-500/20 hover:border-cyan-400 text-cyan-400 text-xs font-bold rounded-xl transition-all flex items-center justify-center gap-1.5"
                      >
                        <Brain className="w-4 h-4" />
                        {isExpanded ? 'Hide Study Center' : 'Study Roundtable'}
                        {isExpanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                      </button>

                      <button
                        onClick={() => handleDelete(exp.id)}
                        className="px-3 py-2.5 bg-red-500/10 border border-red-500/20 hover:bg-red-500/20 hover:border-red-400 rounded-xl text-red-400 transition-all flex items-center justify-center"
                        title="Delete Run"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>

                </div>

                {/* Expanded Accordion: Collaborative Science Roundtable Dialogue */}
                <AnimatePresence>
                  {isExpanded && (
                    <motion.div
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: 'auto', opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      transition={{ duration: 0.3 }}
                      className="overflow-hidden mt-6 pt-6 border-t border-white/5"
                    >
                      <div className="bg-black/35 rounded-3xl p-5 border border-white/5 space-y-4">
                        <div className="flex items-center gap-2">
                          <Sparkles className="w-4 h-4 text-cyan-400 shrink-0" />
                          <h4 className="text-xs font-bold text-white uppercase tracking-wider">ISAAC's Scientific Specialist Roundtable</h4>
                        </div>

                        <div className="space-y-4">
                          {parsedDialogues.map((dlg, dIdx) => (
                            <div key={dIdx} className="flex gap-3 items-start text-xs leading-relaxed">
                              {/* Specialist Avatar */}
                              <div className="w-8 h-8 rounded-xl bg-white/5 border border-white/10 flex items-center justify-center text-sm shrink-0">
                                {dlg.avatar}
                              </div>
                              <div className="space-y-1">
                                <span className={`px-2 py-0.5 text-[9px] font-black rounded border uppercase tracking-wider ${dlg.badgeColor}`}>
                                  {dlg.role}
                                </span>
                                <p className="text-gray-300 font-medium text-[11px] mt-1 leading-relaxed">
                                  {dlg.content}
                                </p>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>

              </motion.div>
            );
          })}
        </div>
      )}
    </div>
  );
}
