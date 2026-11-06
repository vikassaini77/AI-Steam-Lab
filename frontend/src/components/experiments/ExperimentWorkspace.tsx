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
  time_series?: TimeSeriesPoint[];
  [key: string]: unknown;
}

interface TutorExplanation {
  explanation?: string;
  phenomenon_demonstrated?: string;
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
          <div className="bg-[#10101c] border border-[#212133] rounded-2xl p-5 space-y-4 shadow-xl">
            <span className="text-xs font-bold text-white flex items-center justify-between">
              <span>Interactive Model</span>
              <span className="text-[10px] text-cyan-400 font-mono">Real-time Simulation</span>
            </span>

            {/* Pendulum Visualizer SVG */}
            <div className="h-64 bg-black/50 border border-white/5 rounded-xl flex items-center justify-center relative overflow-hidden">
              <svg className="w-full h-full" viewBox="0 0 200 240">
                {/* Pivot point */}
                <circle cx="100" cy="20" r="4" fill="#94a3b8" />
                <rect x="80" y="16" width="40" height="4" fill="#64748b" rx="2" />

                {/* Equilibrium vertical dashed line */}
                <line x1="100" y1="20" x2="100" y2="210" stroke="#334155" strokeDasharray="3 3" />

                {/* Pendulum Rod */}
                {(() => {
                  const rad = (angleDeg * Math.PI) / 180;
                  const rodLen = 160;
                  const bx = 100 + rodLen * Math.sin(rad);
                  const by = 20 + rodLen * Math.cos(rad);
                  return (
                    <g>
                      <line x1="100" y1="20" x2={bx} y2={by} stroke="#06b6d4" strokeWidth="2.5" />
                      <circle cx={bx} cy={by} r="14" fill="#ef4444" stroke="#ffffff" strokeWidth="1.5" />
                      <text x={bx} y={by + 4} textAnchor="middle" fill="#ffffff" fontSize="9" fontWeight="bold">
                        m
                      </text>
                    </g>
                  );
                })()}
              </svg>
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

