import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { useNavigate } from "react-router-dom";
import { Zap, Play, Clock, Check, Sparkles, Camera } from "lucide-react";
import { getApiBaseUrl, getAuthHeaders } from "../../lib/api";

interface HistoryRecord {
  experiment_id?: string;
  exp_id?: string;
  type?: string;
  title?: string;
  status?: string;
  completed?: boolean;
  trials?: unknown[];
  accuracy?: number;
}

interface ExperimentItem {
  id: string;
  subject: string;
  tier: 'Beginner' | 'Intermediate' | 'Advanced';
  title: string;
  desc: string;
  time: string;
  xp: string;
  progress: number;
  status: 'Start' | 'Continue' | 'Review';
  locked: boolean;
  roadmap?: boolean;
}

const INITIAL_EXPERIMENTS: ExperimentItem[] = [
  {
    id: 'pendulum',
    subject: 'Mechanics',
    tier: 'Beginner',
    title: 'Simple Pendulum Oscillation',
    desc: 'Measure pendulum oscillation periods, evaluate small-angle approximations, and quantify error against Newtonian dynamics.',
    time: '20 min',
    xp: '150 XP',
    progress: 0,
    status: 'Start',
    locked: false
  },
  {
    id: 'projectile_motion',
    subject: 'Kinematics',
    tier: 'Beginner',
    title: 'Projectile Motion Analysis',
    desc: 'Calculate kinematic ballistic trajectories, verify launch velocities and ranges, and analyze parabolic flight.',
    time: '15 min',
    xp: '100 XP',
    progress: 0,
    status: 'Start',
    locked: false
  },
  {
    id: 'free_fall',
    subject: 'Kinematics',
    tier: 'Beginner',
    title: 'Free Fall & Gravity Verification',
    desc: 'Measure gravitational acceleration g via drop times, analyze quadratic position-time curves, and examine air resistance.',
    time: '15 min',
    xp: '120 XP',
    progress: 0,
    status: 'Start',
    locked: false
  },
  {
    id: 'circular_motion',
    subject: 'Dynamics',
    tier: 'Intermediate',
    title: 'Uniform Circular Motion',
    desc: 'Compute centripetal acceleration, angular frequencies, and verify centripetal force requirements across planetary gravities.',
    time: '25 min',
    xp: '200 XP',
    progress: 0,
    status: 'Start',
    locked: false
  },
  {
    id: 'harmonic_motion',
    subject: 'Mechanics',
    tier: 'Intermediate',
    title: 'Simple Harmonic Motion (Spring-Mass)',
    desc: "Investigate Hooke's law restoring force, natural frequencies, and mechanical energy oscillations between kinetic and elastic.",
    time: '25 min',
    xp: '220 XP',
    progress: 0,
    status: 'Start',
    locked: false
  },
  {
    id: 'collision_momentum',
    subject: 'Dynamics',
    tier: 'Advanced',
    title: 'Collision and Linear Momentum',
    desc: 'Test 1D elastic and inelastic collisions, verify conservation of momentum, and evaluate coefficient of restitution.',
    time: '30 min',
    xp: '300 XP',
    progress: 0,
    status: 'Start',
    locked: false
  }
];

function ExperimentsCatalog() {
  const navigate = useNavigate();
  const [activeFilter, setActiveFilter] = useState('All');
  const [searchQuery, setSearchQuery] = useState('');
  const [experiments, setExperiments] = useState<ExperimentItem[]>(INITIAL_EXPERIMENTS);

  const categories = ['All', 'Kinematics', 'Dynamics', 'Mechanics'];

  useEffect(() => {
    const fetchHistoryAndSync = async () => {
      try {
        const headers = await getAuthHeaders();
        const API_URL = getApiBaseUrl();
        const res = await fetch(`${API_URL}/api/experiments/history`, { headers });
        if (res.ok) {
          const data = await res.json();
          const historyList: HistoryRecord[] = Array.isArray(data)
            ? data
            : (data.experiments || data.history || []);

          setExperiments(prev =>
            prev.map(exp => {
              if (exp.roadmap) return exp;

              const match = historyList.find(
                (h: HistoryRecord) =>
                  h.experiment_id === exp.id ||
                  h.exp_id === exp.id ||
                  h.type === exp.id ||
                  (h.title && h.title.toLowerCase().includes(exp.id.replace('_', ' ')))
              );

              if (match) {
                const isCompleted =
                  match.status === 'completed' ||
                  match.completed === true ||
                  (match.trials && match.trials.length > 0) ||
                  (match.accuracy !== undefined && match.accuracy > 0);

                if (isCompleted) {
                  return { ...exp, progress: 100, status: 'Review' };
                }
                return { ...exp, progress: 50, status: 'Continue' };
              }

              return { ...exp, progress: 0, status: 'Start' };
            })
          );
        }
      } catch (err) {
        console.warn("Could not sync user experiment progress:", err);
      }
    };

    fetchHistoryAndSync();
  }, []);

  const handleLaunchExperiment = (exp: ExperimentItem) => {
    if (exp.locked || exp.roadmap) return;
    navigate(`/dashboard/experiments/${exp.id}`);
  };

  const filtered = experiments.filter((exp) => {
    const matchesFilter = activeFilter === 'All' || exp.subject === activeFilter;
    const matchesSearch = exp.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      exp.desc.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesFilter && matchesSearch;
  });

  useEffect(() => {
    const handleGlobalSearch = (e: Event) => {
      setSearchQuery((e as CustomEvent).detail);
    };
    window.addEventListener('dashboard-search', handleGlobalSearch);
    return () => window.removeEventListener('dashboard-search', handleGlobalSearch);
  }, []);

  return (
    <div className="p-6 relative z-10 max-w-7xl mx-auto space-y-6 pt-2">

      {/* Live Webcam Lab Launch Banner */}
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        className="p-5 rounded-2xl bg-gradient-to-r from-cyan-950/60 via-blue-950/40 to-purple-950/30 border border-cyan-500/30 backdrop-blur-md flex flex-col md:flex-row items-start md:items-center justify-between gap-4 shadow-xl"
      >
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-cyan-500/15 border border-cyan-500/30 flex items-center justify-center text-cyan-400 shrink-0">
            <Camera className="w-6 h-6 animate-pulse" />
          </div>
          <div>
            <h3 className="text-base font-black text-white flex items-center gap-2">
              Live Webcam Vision Lab
              <span className="px-2 py-0.5 text-[9px] font-bold rounded-full bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 tracking-wider">
                AI COMPUTER VISION
              </span>
            </h3>
            <p className="text-xs text-gray-300 mt-0.5 max-w-xl">
              Turn on your device camera or upload a video to track physical pendulum bobs and motion kinematics with sub-pixel CV precision.
            </p>
          </div>
        </div>
        <button
          onClick={() => navigate('/dashboard/experiments/active')}
          className="px-5 py-2.5 bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-white font-bold rounded-xl text-xs shadow-lg shadow-cyan-500/25 hover:shadow-cyan-500/40 transition-all flex items-center gap-2 shrink-0"
        >
          <Camera className="w-4 h-4" />
          <span>Launch Camera Lab 📹</span>
        </button>
      </motion.div>

      {/* Filter Pill Row */}
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm text-gray-400 mr-2">Filter by:</span>
        {categories.map((cat) => (
          <button
            key={cat}
            onClick={() => setActiveFilter(cat)}
            className={`px-4 py-2.5 text-sm rounded-full font-medium transition-all ${
              activeFilter === cat
                ? 'bg-gradient-to-r from-cyan-500 to-blue-600 text-white shadow-lg shadow-cyan-500/20'
                : 'bg-white/5 border border-white/10 text-gray-300 hover:bg-white/10'
            }`}
          >
            {cat} {cat === 'Physics' && '(6 Labs)'} {cat === 'Chemistry' && '(Roadmap)'} {cat === 'Engineering' && '(Roadmap)'}
          </button>
        ))}
      </div>

      {/* Card Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mt-6">
        {filtered.map((exp, idx) => (
          <motion.div
            key={exp.id}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: idx * 0.05 }}
            whileHover={!exp.locked ? { y: -4, border: '1px solid rgba(6, 182, 212, 0.4)' } : {}}
            className={`p-6 rounded-2xl border backdrop-blur-sm flex flex-col justify-between min-h-[320px] ${
              exp.locked
                ? 'bg-white/[0.02] border-white/5 opacity-70'
                : 'bg-white/5 border-white/10'
            }`}
          >
            {/* Subject and Tier Tags */}
            <div>
              <div className="flex justify-between items-center">
                <span className={`px-2.5 py-0.5 text-xs font-semibold rounded border ${
                  exp.subject === 'Physics'
                    ? 'text-blue-400 bg-blue-500/10 border-blue-500/20'
                    : exp.subject === 'Chemistry'
                    ? 'text-green-400 bg-green-500/10 border-green-500/20'
                    : 'text-orange-400 bg-orange-500/10 border-orange-500/20'
                }`}>
                  {exp.subject}
                </span>

                <div className="flex items-center gap-1.5">
                  {exp.roadmap && (
                    <span className="px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider rounded border border-purple-500/30 bg-purple-500/10 text-purple-300 flex items-center gap-1">
                      <Sparkles className="w-2.5 h-2.5" />
                      In Development
                    </span>
                  )}
                  <span className={`px-2 py-0.5 text-xs font-semibold rounded border flex items-center gap-1 ${
                    exp.tier === 'Beginner'
                      ? 'text-green-400 bg-green-500/10 border-green-500/20'
                      : exp.tier === 'Intermediate'
                      ? 'text-yellow-400 bg-yellow-500/10 border-yellow-500/20'
                      : 'text-red-400 bg-red-500/10 border-red-500/20'
                  }`}>
                    {exp.tier}
                    {exp.progress === 100 && ' ✓'}
                  </span>
                </div>
              </div>

              {/* Title & Description */}
              <h3 className="text-xl font-bold text-white mt-4">{exp.title}</h3>
              <p className="text-xs text-gray-400 mt-2 leading-relaxed min-h-[3rem] line-clamp-3">
                {exp.desc}
              </p>

              {/* Meta information */}
              <div className="flex gap-4 mt-4 text-xs text-gray-500">
                <span className="flex items-center gap-1.5">
                  <Clock className="w-4 h-4" />
                  {exp.time}
                </span>
                <span className="flex items-center gap-1.5">
                  <Zap className="w-4 h-4 text-cyan-400" />
                  {exp.xp}
                </span>
              </div>
            </div>

            {/* Progress & Action Bottom Grid */}
            <div className="mt-6 pt-4 border-t border-white/5 space-y-4">
              {/* Progress Bar */}
              {!exp.roadmap ? (
                <div className="space-y-1.5">
                  <div className="flex justify-between text-[11px] font-bold">
                    <span className="text-gray-500">Progress</span>
                    <span className="text-white">{exp.progress}%</span>
                  </div>
                  <div className="h-1.5 bg-white/10 rounded-full overflow-hidden">
                    <motion.div
                      initial={{ width: 0 }}
                      animate={{ width: `${exp.progress}%` }}
                      className="h-full bg-gradient-to-r from-cyan-400 to-blue-500 rounded-full"
                    />
                  </div>
                </div>
              ) : (
                <div className="text-[11px] text-gray-500 italic py-1">
                  Scheduled for upcoming curriculum release
                </div>
              )}

              {/* Button */}
              {exp.status === 'Review' ? (
                <motion.button
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                  onClick={() => handleLaunchExperiment(exp)}
                  className="w-full py-3 bg-green-950/20 hover:bg-green-900/30 border border-green-500/30 hover:border-green-400/50 rounded-xl text-center text-xs font-bold text-green-400 transition-all flex items-center justify-center gap-2"
                >
                  <Check className="w-4 h-4" />
                  Review Experiment
                </motion.button>
              ) : exp.status === 'Continue' ? (
                <motion.button
                  whileHover={{ scale: 1.02, boxShadow: '0 0 25px rgba(6, 182, 212, 0.3)' }}
                  whileTap={{ scale: 0.98 }}
                  onClick={() => handleLaunchExperiment(exp)}
                  className="w-full py-3 bg-gradient-to-r from-cyan-500 to-blue-600 text-white rounded-xl text-center text-xs font-bold transition-all flex items-center justify-center gap-2 shadow-lg shadow-cyan-500/20"
                >
                  <Play className="w-4 h-4 fill-current" />
                  Continue Lab
                </motion.button>
              ) : (
                <motion.button
                  whileHover={{ scale: 1.02, backgroundColor: 'rgba(255,255,255,0.1)' }}
                  whileTap={{ scale: 0.98 }}
                  onClick={() => handleLaunchExperiment(exp)}
                  className="w-full py-3 bg-white/5 border border-white/10 hover:border-cyan-500/30 text-white rounded-xl text-center text-xs font-bold transition-all flex items-center justify-center gap-2"
                >
                  <Play className="w-4 h-4 fill-current" />
                  Start Experiment
                </motion.button>
              )}
            </div>
          </motion.div>
        ))}
      </div>
    </div>
  );
}

export default ExperimentsCatalog;
