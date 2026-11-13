import { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Play,
  Pause,
  RotateCcw,
  Save,
  Check,
  Info,
  Sparkles,
  BookOpen,
  Clock,
  Activity,
  Sliders,
  Brain,
  Video,
  ListPlus,
  Trash2,
  Atom,
  ArrowRight
} from 'lucide-react';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  CartesianGrid,
  AreaChart,
  Area
} from 'recharts';
import { getApiBaseUrl, getAuthHeaders } from '../../lib/api';
import { pushNotification } from '../../lib/notificationStore';

interface ExperimentMetadata {
  id: string;
  title: string;
  category: string;
  tier: string;
  time_estimate: string;
  learning_objectives: string[];
  required_materials: string[];
  instructions: string[];
  theoretical_model_summary: string;
  governing_equations: string[];
  small_angle_approximation_note?: string;
  assumptions: string[];
  limitations: string[];
  measurement_modes: string[];
  units: Record<string, string>;
}

interface TimeSeriesPoint {
  time: number;
  position?: number;
  velocity?: number;
  acceleration?: number;
  kinetic_energy?: number;
  potential_energy?: number;
  total_energy?: number;
}

interface ErrorAnalysis {
  absolute_error: number;
  percentage_error: number;
  sample_size: number;
  standard_deviation?: number;
  standard_error_of_mean?: number;
  confidence_interval_95?: [number, number];
  scientific_verdict: string;
  discrepancy_sources: Array<{ factor: string; contribution_percent?: number; description: string; explanation?: string }>;
}

interface TheoreticalData {
  primary_theoretical_value?: number;
  theoretical_series?: TimeSeriesPoint[];
  time_series?: TimeSeriesPoint[];
  [key: string]: unknown;
}

interface TutorExplanation {
  explanation?: string;
  phenomenon_demonstrated?: string;
  what_it_demonstrates?: string;
  why_observed_differs_from_theory?: string;
  parameter_sensitivity?: string;
  graph_interpretation?: string;
  student_question_answer?: string;
  discrepancy_reasons?: string[];
  sources_of_error?: string[];
  next_investigations?: string[];
  [key: string]: unknown;
}

interface ExperimentResult {
  experiment_type: string;
  measurement_mode: string;
  parameters: Record<string, unknown>;
  theoretical_value: number;
  experimental_value: number;
  primary_metric_name: string;
  primary_metric_unit: string;
  error_analysis: ErrorAnalysis;
  observation_count: number;
  theoretical_series: TimeSeriesPoint[];
  experimental_series: TimeSeriesPoint[];
  metadata?: Record<string, unknown>;
}

export default function ExperimentWorkspace() {
  const { expId = 'pendulum' } = useParams<{ expId?: string }>();
  const navigate = useNavigate();
  const apiBase = getApiBaseUrl();

  const [activeTab, setActiveTab] = useState<'guide' | 'setup' | 'measure' | 'results' | 'tutor'>('guide');
  const [metadata, setMetadata] = useState<ExperimentMetadata | null>(null);
  const [loadingMeta, setLoadingMeta] = useState<boolean>(true);

  // Simulation Parameters (Default to Simple Pendulum)
  const [length, setLength] = useState<number>(1.0);
  const [gravity, setGravity] = useState<number>(9.81);
  const [angleDeg, setAngleDeg] = useState<number>(15.0);
  const [mass, setMass] = useState<number>(1.0);
  const [damping, setDamping] = useState<number>(0.0);

  // Real-time Physics Simulation Animation State
  const [simPlaying, setSimPlaying] = useState<boolean>(true);
  const [simTime, setSimTime] = useState<number>(0);
  const [simSpeed, setSimSpeed] = useState<number>(1.0);

  // High-precision RequestAnimationFrame loop for live 60 FPS model physics
  useEffect(() => {
    let animId: number;
    let lastTime: number | null = null;

    const loop = (timestamp: number) => {
      if (lastTime !== null) {
        const deltaSec = (timestamp - lastTime) / 1000;
        const dt = Math.min(deltaSec, 0.1) * simSpeed;
        if (simPlaying) {
          setSimTime((prev) => prev + dt);
        }
      }
      lastTime = timestamp;
      animId = requestAnimationFrame(loop);
    };

    animId = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(animId);
  }, [simPlaying, simSpeed]);

  // Theoretical Results
  const [theoreticalData, setTheoreticalData] = useState<TheoreticalData | null>(null);
  const [calculating, setCalculating] = useState<boolean>(false);

  // Measurement State
  const [measurementMode, setMeasurementMode] = useState<'manual' | 'cv_derived'>('manual');
  const [manualTrials, setManualTrials] = useState<number[]>([2.01, 1.99, 2.03]);
  const [stopwatchTime, setStopwatchTime] = useState<number>(0);
  const [stopwatchRunning, setStopwatchRunning] = useState<boolean>(false);
  const stopwatchIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Processed Experimental Results
  const [experimentResult, setExperimentResult] = useState<ExperimentResult | null>(null);
  const [measuring, setMeasuring] = useState<boolean>(false);

  // AI Tutor State
  const [tutorQuestion, setTutorQuestion] = useState<string>('');
  const [tutorExplanation, setTutorExplanation] = useState<TutorExplanation | null>(null);
  const [explaining, setExplaining] = useState<boolean>(false);

  // Save State
  const [saving, setSaving] = useState<boolean>(false);
  const [savedSuccess, setSavedSuccess] = useState<boolean>(false);

  // Fetch Experiment Metadata
  useEffect(() => {
    let isMounted = true;
    const fetchMetadata = async () => {
      try {
        setLoadingMeta(true);
        const res = await fetch(`${apiBase}/api/experiments/metadata/${expId}`);
        if (res.ok) {
          const data = await res.json();
          if (isMounted) setMetadata(data.metadata);
        }
      } catch (err) {
        console.warn('Failed to load experiment metadata:', err);
      } finally {
        if (isMounted) setLoadingMeta(false);
      }
    };
    fetchMetadata();
    return () => {
      isMounted = false;
    };
  }, [apiBase, expId]);

  // Compute Theoretical Baseline whenever parameters change
  useEffect(() => {
    let isMounted = true;
    const calculateBaseline = async () => {
      try {
        setCalculating(true);
        const params = {
          length,
          gravity,
          angle_deg: angleDeg,
          mass,
          damping,
        };
        const res = await fetch(`${apiBase}/api/experiments/calculate/${expId}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ parameters: params }),
        });
        if (res.ok) {
          const data = await res.json();
          if (isMounted) setTheoreticalData(data);
        }
      } catch (err) {
        console.warn('Calculation error:', err);
      } finally {
        if (isMounted) setCalculating(false);
      }
    };
    calculateBaseline();
    return () => {
      isMounted = false;
    };
  }, [apiBase, expId, length, gravity, angleDeg, mass, damping]);

  // Stopwatch loop
  useEffect(() => {
    if (stopwatchRunning) {
      const startTime = performance.now() - stopwatchTime * 1000;
      stopwatchIntervalRef.current = setInterval(() => {
        setStopwatchTime((performance.now() - startTime) / 1000);
      }, 50);
    } else {
      if (stopwatchIntervalRef.current) clearInterval(stopwatchIntervalRef.current);
    }
    return () => {
      if (stopwatchIntervalRef.current) clearInterval(stopwatchIntervalRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stopwatchRunning]);

  const handleAddStopwatchTrial = () => {
    if (stopwatchTime > 0.1) {
      setManualTrials((prev) => [...prev, Number(stopwatchTime.toFixed(3))]);
      setStopwatchTime(0);
      setStopwatchRunning(false);
    }
  };

  const handleComputeResults = async () => {
    try {
      setMeasuring(true);
      const observations = manualTrials.map((t) => ({ period_s: t }));
      const params = { length, gravity, angle_deg: angleDeg, mass, damping };

      const res = await fetch(`${apiBase}/api/experiments/measure/${expId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          parameters: params,
          observations,
          measurement_mode: measurementMode,
        }),
      });

      if (res.ok) {
        const data = await res.json();
        setExperimentResult(data);
        setActiveTab('results');
        pushNotification('Measurements processed & error analysis compiled!', 'xp');
      } else {
        const err = await res.json().catch(() => ({}));
        pushNotification(err.detail || 'Failed to process measurements', 'info');
      }
    } catch {
      pushNotification('Connection error while computing results', 'info');
    } finally {
      setMeasuring(false);
    }
  };

  const handleExplainResults = async () => {
    if (!experimentResult) return;
    try {
      setExplaining(true);
      const res = await fetch(`${apiBase}/api/experiments/explain/${expId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          parameters: { length, gravity, angle_deg: angleDeg, mass, damping },
          results: experimentResult,
          student_question: tutorQuestion || undefined,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        setTutorExplanation(data);
        setActiveTab('tutor');
      }
    } catch {
      pushNotification('Failed to generate AI tutor explanation', 'info');
    } finally {
      setExplaining(false);
    }
  };

  const handleSaveExperiment = async () => {
    try {
      setSaving(true);
      const headers = await getAuthHeaders();
      const payload = {
        type: expId,
        name: metadata?.title || `${expId} Experiment`,
        parameters: { length, gravity, angle_deg: angleDeg, mass, damping },
        metrics: {
          theoretical_value: theoreticalData?.primary_theoretical_value,
          experimental_value: experimentResult?.experimental_value || theoreticalData?.primary_theoretical_value,
          percentage_error: experimentResult?.error_analysis?.percentage_error || 0.0,
          sample_size: manualTrials.length,
        },
      };

      const res = await fetch(`${apiBase}/api/experiments/save`, {
        method: 'POST',
        headers: {
          ...headers,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      });

      if (res.ok) {
        setSavedSuccess(true);
        pushNotification('Experiment successfully saved to your lab history! +100 XP', 'xp');
        setTimeout(() => setSavedSuccess(false), 3000);
      } else {
        const err = await res.json().catch(() => ({}));
        pushNotification(err.detail || 'Could not save experiment', 'info');
      }
    } catch {
      pushNotification('Network error while saving experiment', 'info');
    } finally {
      setSaving(false);
    }
  };

  const theoreticalPeriod = theoreticalData?.primary_theoretical_value ?? (2 * Math.PI * Math.sqrt(length / gravity));

  if (loadingMeta && !metadata) {
    return (
      <div className="min-h-[60vh] flex flex-col items-center justify-center space-y-4">
        <Atom className="w-8 h-8 text-cyan-400 animate-spin" />
        <p className="text-xs text-gray-400 font-mono">Loading scientific experiment curriculum...</p>
      </div>
    );
  }

  return (
    <div className="p-6 relative z-10 max-w-7xl mx-auto space-y-6 pt-2 text-gray-200">
      {/* Top Header & Breadcrumb */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 bg-[#12121e] border border-[#232338] rounded-2xl p-5 shadow-xl">
        <div className="space-y-1">
          <div className="flex items-center gap-2 text-xs font-mono text-cyan-400">
            <span className="cursor-pointer hover:underline" onClick={() => navigate('/dashboard/experiments')}>
              Experiments
            </span>
            <span>/</span>
            <span className="uppercase">{expId.replace('_', ' ')}</span>
          </div>
          <h1 className="text-2xl font-extrabold text-white tracking-tight flex items-center gap-3">
            <Atom className="w-6 h-6 text-cyan-400" />
            {metadata?.title || 'Scientific Physics Experiment'}
          </h1>
          <p className="text-xs text-gray-400 max-w-2xl">{metadata?.theoretical_model_summary}</p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate('/dashboard/history')}
            className="px-4 py-2.5 bg-white/5 border border-white/10 hover:border-cyan-500/30 text-xs font-bold rounded-xl transition-all"
          >
            History & Records
          </button>
          <button
            onClick={handleSaveExperiment}
            disabled={saving}
            className={`px-5 py-2.5 rounded-xl text-xs font-bold transition-all flex items-center gap-2 ${
              savedSuccess
                ? 'bg-emerald-500 text-white shadow-lg shadow-emerald-500/20'
                : 'bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-white shadow-lg shadow-cyan-500/20'
            }`}
          >
            {saving ? (
              <span className="animate-spin">⏳</span>
            ) : savedSuccess ? (
              <Check className="w-4 h-4" />
            ) : (
              <Save className="w-4 h-4" />
            )}
            {savedSuccess ? 'Saved to History' : 'Save Experiment'}
          </button>
        </div>
      </div>

      {/* Navigation Steps */}
      <div className="flex flex-wrap items-center gap-2 border-b border-white/5 pb-3">
        {(
          [
            { id: 'guide', label: '1. Guide & Objectives', icon: BookOpen },
            { id: 'setup', label: '2. Setup Parameters', icon: Sliders },
            { id: 'measure', label: '3. Record Measurements', icon: Clock },
            { id: 'results', label: '4. Graphs & Analysis', icon: Activity },
            { id: 'tutor', label: '5. AI Tutor Explanation', icon: Brain },
          ] as const
        ).map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-4 py-2.5 text-xs rounded-full font-bold transition-all flex items-center gap-2 ${
                isActive
                  ? 'bg-cyan-500/20 border border-cyan-500/50 text-cyan-300 shadow-md shadow-cyan-500/10'
                  : 'bg-white/5 border border-white/10 text-gray-400 hover:text-white hover:bg-white/10'
              }`}
            >
              <Icon className="w-3.5 h-3.5" />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Main Container by Tab */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left Column (8 cols): Interactive Workspace */}
        <div className="lg:col-span-8 space-y-6">
          {/* TAB 1: GUIDE & OBJECTIVES */}
          {activeTab === 'guide' && (
            <div className="bg-[#10101c] border border-[#212133] rounded-2xl p-6 space-y-6 shadow-xl">
              <div>
                <h3 className="text-lg font-bold text-white flex items-center gap-2">
                  <BookOpen className="w-5 h-5 text-cyan-400" />
                  Learning Objectives
                </h3>
                <ul className="mt-3 space-y-2 text-xs text-gray-300">
                  {metadata?.learning_objectives.map((obj, i) => (
                    <li key={i} className="flex items-start gap-2">
                      <span className="text-cyan-400 font-bold">✓</span>
                      <span>{obj}</span>
                    </li>
                  ))}
                </ul>
              </div>

              {metadata?.small_angle_approximation_note && (
                <div className="p-4 bg-amber-500/10 border border-amber-500/30 rounded-xl space-y-1">
                  <span className="text-xs font-bold text-amber-400 uppercase tracking-wider flex items-center gap-1.5">
                    <Info className="w-4 h-4" />
                    Crucial Principle: Small-Angle Approximation
                  </span>
                  <p className="text-xs text-amber-200/90 leading-relaxed">
                    {metadata.small_angle_approximation_note}
                  </p>
                </div>
              )}

              <div>
                <h3 className="text-sm font-bold text-white uppercase tracking-wider">Governing Equations</h3>
                <div className="mt-2 grid grid-cols-1 md:grid-cols-2 gap-3">
                  {metadata?.governing_equations.map((eq, i) => (
                    <div key={i} className="p-3 bg-black/40 border border-white/5 rounded-xl text-xs font-mono text-cyan-300">
                      {eq}
                    </div>
                  ))}
                </div>
              </div>

              <div>
                <h3 className="text-sm font-bold text-white uppercase tracking-wider">Instructions & Procedure</h3>
                <ol className="mt-2 space-y-2 text-xs text-gray-300 list-decimal list-inside leading-relaxed">
                  {metadata?.instructions.map((ins, i) => (
                    <li key={i}>{ins}</li>
                  ))}
                </ol>
              </div>

              <button
                onClick={() => setActiveTab('setup')}
                className="w-full py-3 bg-gradient-to-r from-cyan-500 to-blue-600 text-white font-bold rounded-xl text-xs flex items-center justify-center gap-2 hover:opacity-95 transition-all shadow-lg shadow-cyan-500/20"
              >
                Proceed to Setup Parameters <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          )}

          {/* TAB 2: SETUP PARAMETERS */}
          {activeTab === 'setup' && (
            <div className="bg-[#10101c] border border-[#212133] rounded-2xl p-6 space-y-6 shadow-xl">
              <h3 className="text-lg font-bold text-white flex items-center gap-2">
                <Sliders className="w-5 h-5 text-cyan-400" />
                Configure Pendulum Parameters
              </h3>

              <div className="space-y-5">
                {/* Length */}
                <div className="space-y-2">
                  <div className="flex justify-between text-xs font-bold">
                    <span>String Length L (m)</span>
                    <span className="text-cyan-400 font-mono">{length.toFixed(2)} m</span>
                  </div>
                  <input
                    type="range"
                    min="0.1"
                    max="5.0"
                    step="0.05"
                    value={length}
                    onChange={(e) => setLength(parseFloat(e.target.value))}
                    className="w-full accent-cyan-400"
                  />
                  <div className="flex justify-between text-[10px] text-gray-500 font-mono">
                    <span>0.1 m</span>
                    <span>2.5 m</span>
                    <span>5.0 m</span>
                  </div>
                </div>

                {/* Gravity Presets */}
                <div className="space-y-2">
                  <div className="flex justify-between text-xs font-bold">
                    <span>Gravitational Acceleration g (m/s²)</span>
                    <span className="text-cyan-400 font-mono">{gravity.toFixed(2)} m/s²</span>
                  </div>
                  <div className="grid grid-cols-4 gap-2">
                    {[
                      { name: 'Earth', val: 9.81 },
                      { name: 'Moon', val: 1.62 },
                      { name: 'Mars', val: 3.72 },
                      { name: 'Jupiter', val: 24.79 },
                    ].map((gPreset) => (
                      <button
                        key={gPreset.name}
                        onClick={() => setGravity(gPreset.val)}
                        className={`py-2 text-[11px] font-bold rounded-lg border transition-all ${
                          Math.abs(gravity - gPreset.val) < 0.05
                            ? 'bg-cyan-500/20 border-cyan-400 text-cyan-300'
                            : 'bg-white/5 border-white/10 text-gray-400 hover:text-white'
                        }`}
                      >
                        {gPreset.name} ({gPreset.val})
                      </button>
                    ))}
                  </div>
                </div>

                {/* Angle */}
                <div className="space-y-2">
                  <div className="flex justify-between text-xs font-bold">
                    <span>Initial Release Angle θ₀ (degrees)</span>
                    <span
                      className={`font-mono ${
                        angleDeg > 15 ? 'text-amber-400' : 'text-emerald-400'
                      }`}
                    >
                      {angleDeg.toFixed(1)}° {angleDeg <= 15 ? '(Small Angle)' : '(Non-linear)'}
                    </span>
                  </div>
                  <input
                    type="range"
                    min="2"
                    max="60"
                    step="1"
                    value={angleDeg}
                    onChange={(e) => setAngleDeg(parseFloat(e.target.value))}
                    className="w-full accent-cyan-400"
                  />
                </div>

                {/* Mass */}
                <div className="space-y-2">
                  <div className="flex justify-between text-xs font-bold">
                    <span>Bob Mass m (kg)</span>
                    <span className="text-gray-400 font-mono">{mass.toFixed(2)} kg (Zero effect on period)</span>
                  </div>
                  <input
                    type="range"
                    min="0.1"
                    max="10.0"
                    step="0.1"
                    value={mass}
                    onChange={(e) => setMass(parseFloat(e.target.value))}
                    className="w-full accent-cyan-400"
                  />
                </div>

                {/* Damping / Air Resistance */}
                <div className="space-y-2">
                  <div className="flex justify-between text-xs font-bold">
                    <span>Air Resistance / Damping γ (1/s)</span>
                    <span className="text-gray-400 font-mono">{damping.toFixed(2)} 1/s</span>
                  </div>
                  <input
                    type="range"
                    min="0.0"
                    max="1.0"
                    step="0.05"
                    value={damping}
                    onChange={(e) => setDamping(parseFloat(e.target.value))}
                    className="w-full accent-cyan-400"
                  />
                </div>
              </div>

              {/* Theoretical Summary Box */}
              <div className="p-4 bg-cyan-950/20 border border-cyan-500/30 rounded-xl space-y-2">
                <div className="flex justify-between items-center">
                  <span className="text-[10px] font-extrabold uppercase tracking-wider text-cyan-400">
                    Computed Theoretical Baseline
                  </span>
                  {calculating && (
                    <span className="text-[10px] text-cyan-300 animate-pulse">Syncing theoretical model...</span>
                  )}
                </div>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-center">
                  <div className="p-2 bg-black/40 rounded-lg">
                    <span className="text-[10px] text-gray-400 block">Period T₀</span>
                    <span className="text-sm font-bold text-white font-mono">{theoreticalPeriod.toFixed(3)}s</span>
                  </div>
                  <div className="p-2 bg-black/40 rounded-lg">
                    <span className="text-[10px] text-gray-400 block">Frequency f</span>
                    <span className="text-sm font-bold text-white font-mono">{(1 / theoreticalPeriod).toFixed(3)} Hz</span>
                  </div>
                  <div className="p-2 bg-black/40 rounded-lg">
                    <span className="text-[10px] text-gray-400 block">Angular Speed ω</span>
                    <span className="text-sm font-bold text-white font-mono">{Math.sqrt(gravity / length).toFixed(2)} rad/s</span>
                  </div>
                  <div className="p-2 bg-black/40 rounded-lg">
                    <span className="text-[10px] text-gray-400 block">Formula</span>
                    <span className="text-[11px] font-bold text-cyan-400 font-mono">2π√(L/g)</span>
                  </div>
                </div>
              </div>

              <button
                onClick={() => setActiveTab('measure')}
                className="w-full py-3 bg-gradient-to-r from-cyan-500 to-blue-600 text-white font-bold rounded-xl text-xs flex items-center justify-center gap-2 hover:opacity-95 transition-all shadow-lg shadow-cyan-500/20"
              >
                Proceed to Record Measurements <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          )}

          {/* TAB 3: RECORD MEASUREMENTS */}
          {activeTab === 'measure' && (
            <div className="bg-[#10101c] border border-[#212133] rounded-2xl p-6 space-y-6 shadow-xl">
              <div className="flex justify-between items-center">
                <h3 className="text-lg font-bold text-white flex items-center gap-2">
                  <Clock className="w-5 h-5 text-cyan-400" />
                  Measurement Collection System
                </h3>
                <div className="flex gap-2">
                  <button
                    onClick={() => setMeasurementMode('manual')}
                    className={`px-3 py-1.5 text-xs font-bold rounded-lg border transition-all ${
                      measurementMode === 'manual'
                        ? 'bg-cyan-500/20 border-cyan-400 text-cyan-300'
                        : 'bg-white/5 border-white/10 text-gray-400'
                    }`}
                  >
                    Manual Stopwatch
                  </button>
                  <button
                    onClick={() => setMeasurementMode('cv_derived')}
                    className={`px-3 py-1.5 text-xs font-bold rounded-lg border transition-all ${
                      measurementMode === 'cv_derived'
                        ? 'bg-cyan-500/20 border-cyan-400 text-cyan-300'
                        : 'bg-white/5 border-white/10 text-gray-400'
                    }`}
                  >
                    Webcam CV Tracking
                  </button>
                </div>
              </div>

              {/* Mode A: Manual Stopwatch */}
              {measurementMode === 'manual' ? (
                <div className="space-y-6">
                  <div className="p-6 bg-black/40 border border-white/5 rounded-2xl flex flex-col items-center justify-center space-y-4">
                    <span className="text-xs text-gray-400 font-mono">OSCILLATION STOPWATCH</span>
                    <span className="text-4xl font-mono font-bold text-cyan-400">{stopwatchTime.toFixed(3)}s</span>
                    <div className="flex gap-3">
                      <button
                        onClick={() => setStopwatchRunning(!stopwatchRunning)}
                        className={`px-6 py-2.5 rounded-xl font-bold text-xs flex items-center gap-2 ${
                          stopwatchRunning ? 'bg-amber-600 text-white' : 'bg-emerald-600 text-white'
                        }`}
                      >
                        {stopwatchRunning ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
                        {stopwatchRunning ? 'Stop' : 'Start'}
                      </button>
                      <button
                        onClick={handleAddStopwatchTrial}
                        disabled={stopwatchTime <= 0.1}
                        className="px-5 py-2.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-40 text-white rounded-xl text-xs font-bold flex items-center gap-2"
                      >
                        <ListPlus className="w-4 h-4" /> Record Trial
                      </button>
                      <button
                        onClick={() => {
                          setStopwatchTime(0);
                          setStopwatchRunning(false);
                        }}
                        className="p-2.5 bg-white/5 hover:bg-white/10 border border-white/10 rounded-xl text-gray-400"
                      >
                        <RotateCcw className="w-4 h-4" />
                      </button>
                    </div>
                  </div>

                  {/* Recorded Trials List */}
                  <div>
                    <div className="flex justify-between items-center text-xs font-bold mb-3">
                      <span>Recorded Period Trials ({manualTrials.length})</span>
                      <button
                        onClick={() => setManualTrials([])}
                        className="text-red-400 hover:text-red-300 flex items-center gap-1 text-[11px]"
                      >
                        <Trash2 className="w-3.5 h-3.5" /> Clear All
                      </button>
                    </div>
                    {manualTrials.length === 0 ? (
                      <p className="text-xs text-gray-500 italic p-4 border border-dashed border-white/10 rounded-xl text-center">
                        No trials recorded yet. Use the stopwatch above or add presets below.
                      </p>
                    ) : (
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                        {manualTrials.map((t, idx) => (
                          <div
                            key={idx}
                            className="p-2.5 bg-white/5 border border-white/10 rounded-xl flex justify-between items-center text-xs font-mono"
                          >
                            <span className="text-gray-400">Trial #{idx + 1}</span>
                            <span className="font-bold text-cyan-300">{t.toFixed(3)}s</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              ) : (
                /* Mode B: CV Webcam Tracking */
                <div className="p-6 bg-black/40 border border-white/5 rounded-2xl text-center space-y-4">
                  <Video className="w-10 h-10 text-cyan-400 mx-auto" />
                  <h4 className="text-sm font-bold text-white">Live Computer Vision Pendulum Tracker</h4>
                  <p className="text-xs text-gray-400 max-w-md mx-auto">
                    The OpenCV tracker extracts bob oscillation cycles from camera zero-crossings without treating individual frames as independent points.
                  </p>
                  <button
                    onClick={() => navigate('/dashboard/experiments/active')}
                    className="px-5 py-2.5 bg-gradient-to-r from-cyan-500 to-blue-600 text-white font-bold rounded-xl text-xs inline-flex items-center gap-2"
                  >
                    Open Live Webcam Stream <ArrowRight className="w-4 h-4" />
                  </button>
                </div>
              )}

              <button
                onClick={handleComputeResults}
                disabled={measuring || manualTrials.length === 0}
                className="w-full py-3.5 bg-gradient-to-r from-emerald-500 to-teal-600 hover:from-emerald-400 hover:to-teal-500 disabled:opacity-40 text-white font-bold rounded-xl text-xs flex items-center justify-center gap-2 shadow-lg shadow-emerald-500/20 transition-all"
              >
                {measuring ? 'Processing Measurements...' : 'Compute Results & Scientific Error Analysis'}
                <Activity className="w-4 h-4" />
              </button>
            </div>
          )}

          {/* TAB 4: GRAPHS & ANALYSIS */}
          {activeTab === 'results' && (
            <div className="bg-[#10101c] border border-[#212133] rounded-2xl p-6 space-y-6 shadow-xl">
              <div className="flex justify-between items-center">
                <h3 className="text-lg font-bold text-white flex items-center gap-2">
                  <Activity className="w-5 h-5 text-cyan-400" />
                  Experimental vs Theoretical Results
                </h3>
                <span className="px-3 py-1 bg-cyan-500/10 border border-cyan-500/30 text-cyan-400 text-xs font-bold rounded-lg font-mono">
                  Error: {experimentResult?.error_analysis?.percentage_error?.toFixed(2) ?? '0.00'}%
                </span>
              </div>

              {/* KPI Grid */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <div className="p-3 bg-white/5 border border-white/10 rounded-xl text-center">
                  <span className="text-[10px] text-gray-400 uppercase font-mono block">Theoretical Period</span>
                  <span className="text-lg font-extrabold text-white font-mono">
                    {theoreticalPeriod.toFixed(3)}s
                  </span>
                </div>
                <div className="p-3 bg-white/5 border border-white/10 rounded-xl text-center">
                  <span className="text-[10px] text-gray-400 uppercase font-mono block">Experimental Period</span>
                  <span className="text-lg font-extrabold text-cyan-400 font-mono">
                    {experimentResult?.experimental_value?.toFixed(3) ?? theoreticalPeriod.toFixed(3)}s
                  </span>
                </div>
                <div className="p-3 bg-white/5 border border-white/10 rounded-xl text-center">
                  <span className="text-[10px] text-gray-400 uppercase font-mono block">Standard Error SE</span>
                  <span className="text-lg font-extrabold text-gray-300 font-mono">
                    ±{experimentResult?.error_analysis?.standard_error_of_mean?.toFixed(3) ?? '0.015'}s
                  </span>
                </div>
                <div className="p-3 bg-white/5 border border-white/10 rounded-xl text-center">
                  <span className="text-[10px] text-gray-400 uppercase font-mono block">Percentage Error</span>
                  <span className="text-lg font-extrabold text-emerald-400 font-mono">
                    {experimentResult?.error_analysis?.percentage_error?.toFixed(2) ?? '0.00'}%
                  </span>
                </div>
              </div>

              {/* Position vs Time Graph */}
              <div className="p-4 bg-black/40 border border-white/5 rounded-2xl space-y-2">
                <div className="flex justify-between items-center text-xs font-bold">
                  <span>Position vs Time (Displacement in Meters)</span>
                  <span className="text-[10px] font-mono text-gray-500">SI: Time (s), Arc (m)</span>
                </div>
                <div className="h-60 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={theoreticalData?.theoretical_series || []}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#22223a" />
                      <XAxis dataKey="time" stroke="#6b7280" tick={{ fontSize: 10 }} />
                      <YAxis stroke="#6b7280" tick={{ fontSize: 10 }} />
                      <Tooltip contentStyle={{ backgroundColor: '#111827', borderColor: '#374151', fontSize: '11px' }} />
                      <Legend wrapperStyle={{ fontSize: '11px' }} />
                      <Line type="monotone" dataKey="position" stroke="#06b6d4" strokeWidth={2} name="Theoretical x(t)" dot={false} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </div>

              {/* Energy Conservation Graph */}
              <div className="p-4 bg-black/40 border border-white/5 rounded-2xl space-y-2">
                <div className="flex justify-between items-center text-xs font-bold">
                  <span>Mechanical Energy Exchange (Joules)</span>
                  <span className="text-[10px] font-mono text-gray-500">PE (Red) vs KE (Blue)</span>
                </div>
                <div className="h-48 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={theoreticalData?.theoretical_series || []}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#22223a" />
                      <XAxis dataKey="time" stroke="#6b7280" tick={{ fontSize: 10 }} />
                      <YAxis stroke="#6b7280" tick={{ fontSize: 10 }} />
                      <Tooltip contentStyle={{ backgroundColor: '#111827', borderColor: '#374151', fontSize: '11px' }} />
                      <Area type="monotone" dataKey="potential_energy" stroke="#ef4444" fill="#ef4444" fillOpacity={0.2} name="Potential Energy" />
                      <Area type="monotone" dataKey="kinetic_energy" stroke="#3b82f6" fill="#3b82f6" fillOpacity={0.2} name="Kinetic Energy" />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              </div>

              {/* Scientific Verdict */}
              {experimentResult?.error_analysis?.scientific_verdict && (
                <div className="p-4 bg-emerald-500/10 border border-emerald-500/30 rounded-xl space-y-1">
                  <span className="text-xs font-bold text-emerald-400 flex items-center gap-1.5">
                    <Check className="w-4 h-4" />
                    Scientific Conclusion
                  </span>
                  <p className="text-xs text-emerald-200/90 leading-relaxed">
                    {experimentResult.error_analysis.scientific_verdict}
                  </p>
                </div>
              )}

              <button
                onClick={handleExplainResults}
                disabled={explaining}
                className="w-full py-3.5 bg-gradient-to-r from-purple-500 to-indigo-600 hover:from-purple-400 hover:to-indigo-500 text-white font-bold rounded-xl text-xs flex items-center justify-center gap-2 shadow-lg shadow-purple-500/20 transition-all"
              >
                <Brain className="w-4 h-4" />
                {explaining ? 'Consulting Professor Nova...' : 'Ask AI Tutor to Explain Results'}
              </button>
            </div>
          )}

          {/* TAB 5: AI TUTOR EXPLANATION */}
          {activeTab === 'tutor' && (
            <div className="bg-[#10101c] border border-[#212133] rounded-2xl p-6 space-y-6 shadow-xl">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-full bg-gradient-to-tr from-purple-500 to-cyan-400 flex items-center justify-center font-bold text-white shadow-lg">
                  PN
                </div>
                <div>
                  <h3 className="text-sm font-bold text-white">Professor Nova's Analysis</h3>
                  <span className="text-[11px] text-cyan-400 font-mono">Pedagogical Physics Assessment</span>
                </div>
              </div>

              {tutorExplanation ? (
                <div className="space-y-4 text-xs leading-relaxed text-gray-300">
                  <div className="p-4 bg-white/5 border border-white/10 rounded-xl space-y-1.5">
                    <span className="text-xs font-bold text-cyan-300 uppercase tracking-wider block">
                      What This Experiment Demonstrates
                    </span>
                    <p>{tutorExplanation.what_it_demonstrates}</p>
                  </div>

                  <div className="p-4 bg-white/5 border border-white/10 rounded-xl space-y-1.5">
                    <span className="text-xs font-bold text-amber-300 uppercase tracking-wider block">
                      Why Observed Results Differ from Theory
                    </span>
                    <p className="whitespace-pre-line">{tutorExplanation.why_observed_differs_from_theory}</p>
                  </div>

                  <div className="p-4 bg-white/5 border border-white/10 rounded-xl space-y-1.5">
                    <span className="text-xs font-bold text-purple-300 uppercase tracking-wider block">
                      Parameter Sensitivity
                    </span>
                    <p className="whitespace-pre-line">{tutorExplanation.parameter_sensitivity}</p>
                  </div>

                  <div className="p-4 bg-white/5 border border-white/10 rounded-xl space-y-1.5">
                    <span className="text-xs font-bold text-emerald-300 uppercase tracking-wider block">
                      Graph Interpretation
                    </span>
                    <p>{tutorExplanation.graph_interpretation}</p>
                  </div>

                  {tutorExplanation.student_question_answer && (
                    <div className="p-4 bg-cyan-950/20 border border-cyan-500/30 rounded-xl space-y-1.5">
                      <span className="text-xs font-bold text-cyan-300 uppercase tracking-wider block">
                        Direct Answer to Your Question
                      </span>
                      <p>{tutorExplanation.student_question_answer}</p>
                    </div>
                  )}
                </div>
              ) : (
                <div className="p-6 text-center border border-dashed border-white/10 rounded-xl space-y-3">
                  <p className="text-xs text-gray-400">
                    No explanation generated yet. Click below to consult Professor Nova using your actual experimental data.
                  </p>
                  <button
                    onClick={handleExplainResults}
                    disabled={explaining}
                    className="px-5 py-2.5 bg-gradient-to-r from-purple-500 to-indigo-600 text-white font-bold rounded-xl text-xs inline-flex items-center gap-2"
                  >
                    <Sparkles className="w-4 h-4" />
                    {explaining ? 'Analyzing...' : 'Generate Explanation'}
                  </button>
                </div>
              )}

              {/* Student Followup Question Input */}
              <div className="flex gap-2 pt-2">
                <input
                  type="text"
                  placeholder="Ask a question about your experiment results..."
                  value={tutorQuestion}
                  onChange={(e) => setTutorQuestion(e.target.value)}
                  className="flex-1 bg-black/40 border border-white/10 rounded-xl px-4 py-2.5 text-xs text-white focus:outline-none focus:border-cyan-400"
                />
                <button
                  onClick={handleExplainResults}
                  disabled={explaining || !tutorQuestion.trim()}
                  className="px-4 py-2.5 bg-cyan-500 hover:bg-cyan-400 disabled:opacity-40 text-black font-bold rounded-xl text-xs"
                >
                  Ask
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Right Column (4 cols): Animated Simulation Bob + Physical Parameters */}
        <div className="lg:col-span-4 space-y-6">
          {/* Animated Canvas / Mini Visualizer */}
          <div className="bg-[#10101c] border border-[#212133] rounded-2xl p-5 space-y-4 shadow-xl text-left">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-white flex items-center gap-2">
                <Atom className="w-4 h-4 text-cyan-400" />
                <span>Interactive Model</span>
              </span>
              <span className="flex items-center gap-1.5 text-[10px] font-mono">
                {simPlaying ? (
                  <span className="flex items-center gap-1.5 text-emerald-400">
                    <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                    Live 60 FPS
                  </span>
                ) : (
                  <span className="flex items-center gap-1 text-amber-400">
                    <Pause className="w-2.5 h-2.5" />
                    Paused
                  </span>
                )}
              </span>
            </div>

            {/* Simulation Controls Bar */}
            <div className="flex items-center justify-between bg-white/[0.03] border border-white/5 p-2 rounded-xl text-xs">
              <div className="flex items-center gap-1.5">
                <button
                  onClick={() => setSimPlaying(!simPlaying)}
                  className={`px-3 py-1.5 rounded-lg font-bold flex items-center gap-1.5 transition-all ${
                    simPlaying
                      ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 hover:bg-cyan-500/30'
                      : 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 hover:bg-emerald-500/30'
                  }`}
                  title={simPlaying ? 'Pause Simulation' : 'Resume Simulation'}
                >
                  {simPlaying ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5 fill-current" />}
                  <span>{simPlaying ? 'Pause' : 'Play'}</span>
                </button>
                <button
                  onClick={() => setSimTime(0)}
                  className="p-1.5 rounded-lg bg-white/5 hover:bg-white/10 text-gray-400 hover:text-white transition-colors border border-white/5"
                  title="Reset to initial state (t = 0)"
                >
                  <RotateCcw className="w-3.5 h-3.5" />
                </button>
              </div>

              {/* Speed Buttons */}
              <div className="flex items-center gap-1 bg-black/40 p-0.5 rounded-lg border border-white/5">
                {[0.5, 1.0, 2.0].map((s) => (
                  <button
                    key={s}
                    onClick={() => setSimSpeed(s)}
                    className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold transition-all ${
                      simSpeed === s
                        ? 'bg-cyan-500 text-black shadow-sm'
                        : 'text-gray-400 hover:text-white'
                    }`}
                  >
                    {s}x
                  </button>
                ))}
              </div>
            </div>

            {/* Dynamic Visualizer SVG tailored to expId */}
            <div className="h-64 bg-black/60 border border-white/5 rounded-xl flex items-center justify-center relative overflow-hidden select-none">
              {/* Background Cartesian grid overlay */}
              <div className="absolute inset-0 opacity-[0.07] pointer-events-none" style={{
                backgroundImage: 'linear-gradient(rgba(255,255,255,0.4) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.4) 1px, transparent 1px)',
                backgroundSize: '20px 20px'
              }} />

              {/* Experiment 1: Pendulum */}
              {(expId === 'pendulum' || !['projectile_motion', 'free_fall', 'circular_motion', 'harmonic_motion', 'collision_momentum'].includes(expId)) && (() => {
                const effL = Math.max(0.2, length);
                const effG = Math.max(0.5, gravity);
                const omega = Math.sqrt(effG / effL);
                const theta0Rad = (Math.max(2, angleDeg) * Math.PI) / 180;
                const decay = Math.exp(-damping * 0.05 * simTime);
                const currentRad = theta0Rad * Math.cos(omega * simTime) * decay;
                const currentDeg = (currentRad * 180) / Math.PI;
                const omegaCurrent = -theta0Rad * omega * Math.sin(omega * simTime) * decay;
                const velocity = effL * omegaCurrent;

                const rodLen = 145;
                const bx = 100 + rodLen * Math.sin(currentRad);
                const by = 25 + rodLen * Math.cos(currentRad);

                const maxDeg = Math.max(2, angleDeg);
                const arcRad = (maxDeg * Math.PI) / 180;
                const leftArcX = 100 - rodLen * Math.sin(arcRad);
                const leftArcY = 25 + rodLen * Math.cos(arcRad);
                const rightArcX = 100 + rodLen * Math.sin(arcRad);
                const rightArcY = 25 + rodLen * Math.cos(arcRad);

                return (
                  <svg className="w-full h-full" viewBox="0 0 200 240">
                    {/* Fixed ceiling mount */}
                    <rect x="70" y="18" width="60" height="7" fill="#475569" rx="2" />
                    <circle cx="100" cy="25" r="5" fill="#38bdf8" stroke="#ffffff" strokeWidth="1" />

                    {/* Equilibrium vertical dashed line */}
                    <line x1="100" y1="25" x2="100" y2="210" stroke="#334155" strokeDasharray="3 3" />

                    {/* Amplitude arc trajectory guideline */}
                    <path
                      d={`M ${leftArcX} ${leftArcY} A ${rodLen} ${rodLen} 0 0 0 ${rightArcX} ${rightArcY}`}
                      fill="none"
                      stroke="#06b6d4"
                      strokeOpacity="0.25"
                      strokeWidth="1.5"
                      strokeDasharray="2 3"
                    />

                    {/* Swinging Pendulum Rod */}
                    <line
                      x1="100"
                      y1="25"
                      x2={bx}
                      y2={by}
                      stroke="#06b6d4"
                      strokeWidth="3"
                      strokeLinecap="round"
                    />

                    {/* Velocity vector tangent arrow */}
                    {Math.abs(velocity) > 0.05 && (
                      <line
                        x1={bx}
                        y1={by}
                        x2={bx + Math.cos(currentRad) * velocity * 12}
                        y2={by - Math.sin(currentRad) * velocity * 12}
                        stroke="#10b981"
                        strokeWidth="2.5"
                        strokeLinecap="round"
                      />
                    )}

                    {/* Glowing Bob with mass label */}
                    <g className="cursor-pointer" onClick={() => setSimTime(t => t + 0.5)}>
                      <circle cx={bx} cy={by} r="16" fill="rgba(239, 68, 68, 0.25)" className="animate-ping" style={{ animationDuration: '3s' }} />
                      <circle cx={bx} cy={by} r="14" fill="#ef4444" stroke="#ffffff" strokeWidth="2" filter="drop-shadow(0 0 8px rgba(239,68,68,0.7))" />
                      <text x={bx} y={by + 4} textAnchor="middle" fill="#ffffff" fontSize="9" fontWeight="bold" pointerEvents="none">
                        {mass.toFixed(1)}k
                      </text>
                    </g>

                    {/* Angle arc indicator near pivot */}
                    <path
                      d={`M 100 50 A 25 25 0 0 ${currentRad > 0 ? 1 : 0} ${100 + 25 * Math.sin(currentRad)} ${25 + 25 * Math.cos(currentRad)}`}
                      fill="none"
                      stroke="#f59e0b"
                      strokeWidth="1.5"
                    />
                    <text x="100" y="230" textAnchor="middle" fill="#94a3b8" fontSize="10" fontFamily="monospace">
                      θ(t) = {currentDeg.toFixed(1)}° • v = {Math.abs(velocity).toFixed(2)} m/s
                    </text>
                  </svg>
                );
              })()}

              {/* Experiment 2: Projectile Motion */}
              {expId === 'projectile_motion' && (() => {
                const v0 = 16;
                const effG = Math.max(0.5, gravity);
                const thetaRad = (Math.min(80, Math.max(15, angleDeg)) * Math.PI) / 180;
                const tFlight = (2 * v0 * Math.sin(thetaRad)) / effG;
                const range = (v0 * v0 * Math.sin(2 * thetaRad)) / effG;
                const maxHeight = (v0 * v0 * Math.sin(thetaRad) * Math.sin(thetaRad)) / (2 * effG);

                const cycle = tFlight + 0.8;
                const tCur = simTime % cycle;
                const isFlying = tCur <= tFlight;
                const tEval = isFlying ? tCur : tFlight;

                const curX = v0 * Math.cos(thetaRad) * tEval;
                const curY = Math.max(0, v0 * Math.sin(thetaRad) * tEval - 0.5 * effG * tEval * tEval);

                // Map to SVG coordinates (x: 25 to 175, y: 195 down to 40)
                const sx = 25 + (curX / range) * 150;
                const sy = 195 - (curY / (maxHeight * 1.15)) * 140;

                // Build full trajectory arc path
                const points = [];
                for (let i = 0; i <= 30; i++) {
                  const tSample = (i / 30) * tFlight;
                  const xs = 25 + ((v0 * Math.cos(thetaRad) * tSample) / range) * 150;
                  const ys = 195 - ((v0 * Math.sin(thetaRad) * tSample - 0.5 * effG * tSample * tSample) / (maxHeight * 1.15)) * 140;
                  points.push(`${i === 0 ? 'M' : 'L'} ${xs.toFixed(1)} ${ys.toFixed(1)}`);
                }

                return (
                  <svg className="w-full h-full" viewBox="0 0 200 240">
                    {/* Ground line */}
                    <line x1="15" y1="195" x2="185" y2="195" stroke="#475569" strokeWidth="2" />

                    {/* Launch Cannon at bottom left */}
                    <circle cx="25" cy="195" r="8" fill="#38bdf8" />
                    <line x1="25" y1="195" x2={25 + 16 * Math.cos(thetaRad)} y2={195 - 16 * Math.sin(thetaRad)} stroke="#0284c7" strokeWidth="5" strokeLinecap="round" />

                    {/* Full Parabolic Trajectory Path */}
                    <path d={points.join(' ')} fill="none" stroke="#06b6d4" strokeWidth="2" strokeDasharray="3 3" opacity="0.6" />

                    {/* Projectile ball */}
                    <circle cx={sx} cy={sy} r="9" fill="#f59e0b" stroke="#ffffff" strokeWidth="1.5" filter="drop-shadow(0 0 6px #f59e0b)" />

                    {/* Landing impact wave */}
                    {!isFlying && (
                      <circle cx="175" cy="195" r="14" fill="none" stroke="#f59e0b" strokeWidth="2" opacity="0.8" className="animate-ping" />
                    )}

                    <text x="100" y="225" textAnchor="middle" fill="#94a3b8" fontSize="10" fontFamily="monospace">
                      x = {curX.toFixed(1)}m • y = {curY.toFixed(1)}m • t = {tEval.toFixed(2)}s
                    </text>
                  </svg>
                );
              })()}

              {/* Experiment 3: Free Fall */}
              {expId === 'free_fall' && (() => {
                const effG = Math.max(0.5, gravity);
                const hTotal = 20;
                const tFall = Math.sqrt((2 * hTotal) / effG);
                const cycle = tFall + 0.8;
                const tCur = simTime % cycle;
                const isDropping = tCur <= tFall;
                const tEval = isDropping ? tCur : tFall;

                const yDrop = 0.5 * effG * tEval * tEval;
                const vInstant = effG * tEval;
                const sy = 40 + (yDrop / hTotal) * 145;

                return (
                  <svg className="w-full h-full" viewBox="0 0 200 240">
                    {/* Top release tower */}
                    <rect x="75" y="25" width="50" height="15" fill="#475569" rx="3" />
                    <text x="100" y="36" textAnchor="middle" fill="#e2e8f0" fontSize="8" fontWeight="bold">RELEASE</text>

                    {/* Ground plate */}
                    <rect x="50" y="195" width="100" height="8" fill="#334155" rx="2" />
                    <line x1="20" y1="203" x2="180" y2="203" stroke="#1e293b" strokeWidth="2" />

                    {/* Vertical guideline */}
                    <line x1="100" y1="40" x2="100" y2="195" stroke="#334155" strokeDasharray="3 3" />

                    {/* Velocity arrow growing downwards */}
                    {isDropping && (
                      <line x1="100" y1={sy} x2="100" y2={sy + Math.min(30, vInstant * 1.5)} stroke="#10b981" strokeWidth="2" strokeLinecap="round" />
                    )}

                    {/* Falling Ball */}
                    <circle cx="100" cy={sy} r="12" fill="#ef4444" stroke="#ffffff" strokeWidth="1.5" filter="drop-shadow(0 0 8px rgba(239,68,68,0.7))" />
                    <text x="100" y={sy + 3} textAnchor="middle" fill="#ffffff" fontSize="8" fontWeight="bold">m</text>

                    {/* Impact flash */}
                    {!isDropping && (
                      <ellipse cx="100" cy="195" rx="22" ry="5" fill="#f59e0b" opacity="0.6" className="animate-pulse" />
                    )}

                    <text x="100" y="225" textAnchor="middle" fill="#94a3b8" fontSize="10" fontFamily="monospace">
                      Drop: {yDrop.toFixed(1)}m • v = {vInstant.toFixed(1)} m/s
                    </text>
                  </svg>
                );
              })()}

              {/* Experiment 4: Uniform Circular Motion */}
              {expId === 'circular_motion' && (() => {
                const effR = 55;
                const effG = Math.max(0.5, gravity);
                const omega = Math.sqrt(effG / Math.max(0.2, length)) * 1.3;
                const angleCur = omega * simTime;
                const bx = 100 + effR * Math.cos(angleCur);
                const by = 110 + effR * Math.sin(angleCur);
                const vx = -Math.sin(angleCur) * 22;
                const vy = Math.cos(angleCur) * 22;

                return (
                  <svg className="w-full h-full" viewBox="0 0 200 240">
                    {/* Orbit Ring */}
                    <circle cx="100" cy="110" r={effR} fill="none" stroke="#06b6d4" strokeWidth="1.5" strokeDasharray="3 3" opacity="0.5" />

                    {/* Tether Radius */}
                    <line x1="100" y1="110" x2={bx} y2={by} stroke="#38bdf8" strokeWidth="2" />

                    {/* Center Pivot */}
                    <circle cx="100" cy="110" r="5" fill="#e2e8f0" stroke="#0284c7" strokeWidth="2" />

                    {/* Tangential Velocity Vector Arrow */}
                    <line x1={bx} y1={by} x2={bx + vx} y2={by + vy} stroke="#10b981" strokeWidth="2.5" strokeLinecap="round" />

                    {/* Centripetal Acceleration Arrow (Inwards) */}
                    <line x1={bx} y1={by} x2={bx - Math.cos(angleCur) * 18} y2={by - Math.sin(angleCur) * 18} stroke="#f59e0b" strokeWidth="2" strokeLinecap="round" />

                    {/* Orbiting Bob */}
                    <circle cx={bx} cy={by} r="12" fill="#8b5cf6" stroke="#ffffff" strokeWidth="1.5" filter="drop-shadow(0 0 8px #8b5cf6)" />
                    <text x={bx} y={by + 3} textAnchor="middle" fill="#ffffff" fontSize="8" fontWeight="bold">m</text>

                    <text x="100" y="225" textAnchor="middle" fill="#94a3b8" fontSize="10" fontFamily="monospace">
                      ω = {omega.toFixed(2)} rad/s • v = {(omega * length).toFixed(2)} m/s
                    </text>
                  </svg>
                );
              })()}

              {/* Experiment 5: Simple Harmonic Motion (Spring-Mass) */}
              {expId === 'harmonic_motion' && (() => {
                const effG = Math.max(0.5, gravity);
                const omega = Math.sqrt(effG / Math.max(0.2, length)) * 1.4;
                const amplitude = 32;
                const dy = amplitude * Math.cos(omega * simTime) * Math.exp(-damping * 0.04 * simTime);
                const massY = 120 + dy;

                // Build spring zigzag points from y=25 to y=massY-15
                const springTop = 25;
                const springBottom = massY - 14;
                const numCoils = 9;
                const coilStep = (springBottom - springTop) / numCoils;
                const springPoints = [`M 100 ${springTop}`];
                for (let i = 1; i < numCoils; i++) {
                  const cx = i % 2 === 1 ? 115 : 85;
                  const cy = springTop + i * coilStep;
                  springPoints.push(`L ${cx} ${cy.toFixed(1)}`);
                }
                springPoints.push(`L 100 ${springBottom.toFixed(1)}`);

                return (
                  <svg className="w-full h-full" viewBox="0 0 200 240">
                    {/* Fixed Ceiling */}
                    <rect x="70" y="18" width="60" height="7" fill="#475569" rx="2" />

                    {/* Equilibrium Reference Line */}
                    <line x1="40" y1="120" x2="160" y2="120" stroke="#334155" strokeDasharray="3 3" />
                    <text x="165" y="123" fill="#64748b" fontSize="8" fontFamily="monospace">y=0</text>

                    {/* Elastic Spring Coil */}
                    <path d={springPoints.join(' ')} fill="none" stroke="#06b6d4" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />

                    {/* Mass Block */}
                    <rect x="80" y={massY - 14} width="40" height="28" fill="#3b82f6" stroke="#ffffff" strokeWidth="2" rx="4" filter="drop-shadow(0 0 8px rgba(59,130,246,0.6))" />
                    <text x="100" y={massY + 3} textAnchor="middle" fill="#ffffff" fontSize="10" fontWeight="bold">
                      {mass.toFixed(1)} kg
                    </text>

                    {/* Restoring Force arrow F = -ky */}
                    <line x1="135" y1="120" x2="135" y2={120 - dy * 0.7} stroke="#f59e0b" strokeWidth="2" strokeLinecap="round" />

                    <text x="100" y="225" textAnchor="middle" fill="#94a3b8" fontSize="10" fontFamily="monospace">
                      Δy = {dy.toFixed(1)}px • F = {(-dy * 0.2).toFixed(1)}N
                    </text>
                  </svg>
                );
              })()}

              {/* Experiment 6: Collision and Linear Momentum */}
              {expId === 'collision_momentum' && (() => {
                const cycle = 4.0;
                const tCur = simTime % cycle;
                // Approach 0 to 1.8s, Collide at 1.8 to 2.0s, Rebound 2.0 to 4.0s
                let c1x = 40;
                let c2x = 160;
                if (tCur < 1.8) {
                  c1x = 35 + (tCur / 1.8) * 45; // 35 -> 80
                  c2x = 165 - (tCur / 1.8) * 45; // 165 -> 120
                } else if (tCur < 2.0) {
                  c1x = 80;
                  c2x = 120;
                } else {
                  const tReb = (tCur - 2.0) / 2.0;
                  c1x = 80 - tReb * 45; // 80 -> 35
                  c2x = 120 + tReb * 45; // 120 -> 165
                }

                return (
                  <svg className="w-full h-full" viewBox="0 0 200 240">
                    {/* Air Track */}
                    <rect x="20" y="130" width="160" height="8" fill="#334155" rx="3" />
                    <line x1="20" y1="140" x2="180" y2="140" stroke="#1e293b" strokeWidth="2" />

                    {/* Cart 1 */}
                    <rect x={c1x - 20} y="105" width="36" height="24" fill="#06b6d4" stroke="#ffffff" strokeWidth="1.5" rx="3" />
                    <text x={c1x - 2} y="120" textAnchor="middle" fill="#ffffff" fontSize="9" fontWeight="bold">m₁</text>

                    {/* Cart 2 */}
                    <rect x={c2x - 16} y="105" width="36" height="24" fill="#ec4899" stroke="#ffffff" strokeWidth="1.5" rx="3" />
                    <text x={c2x + 2} y="120" textAnchor="middle" fill="#ffffff" fontSize="9" fontWeight="bold">m₂</text>

                    {/* Collision Spark when touching */}
                    {tCur >= 1.7 && tCur <= 2.1 && (
                      <circle cx="100" cy="117" r="12" fill="#f59e0b" opacity="0.8" className="animate-ping" />
                    )}

                    <text x="100" y="225" textAnchor="middle" fill="#94a3b8" fontSize="10" fontFamily="monospace">
                      p₁ + p₂ = {(mass * 1.5).toFixed(2)} kg•m/s (Conserved)
                    </text>
                  </svg>
                );
              })()}
            </div>

            {/* Quick Metrics Badge List */}
            <div className="space-y-2 text-xs">
              <div className="flex justify-between p-2 bg-white/5 rounded-lg">
                <span className="text-gray-400">Length L</span>
                <span className="font-mono text-cyan-300 font-bold">{length.toFixed(2)} m</span>
              </div>
              <div className="flex justify-between p-2 bg-white/5 rounded-lg">
                <span className="text-gray-400">Local Gravity g</span>
                <span className="font-mono text-cyan-300 font-bold">{gravity.toFixed(2)} m/s²</span>
              </div>
              <div className="flex justify-between p-2 bg-white/5 rounded-lg">
                <span className="text-gray-400">Release Angle θ₀</span>
                <span className="font-mono text-cyan-300 font-bold">{angleDeg}°</span>
              </div>
              <div className="flex justify-between p-2 bg-white/5 rounded-lg">
                <span className="text-gray-400">Mass m</span>
                <span className="font-mono text-cyan-300 font-bold">{mass.toFixed(1)} kg</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

