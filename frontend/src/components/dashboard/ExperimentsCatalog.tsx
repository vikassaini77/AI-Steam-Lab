import React, { useState, useEffect, useRef, Suspense, lazy } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Link, useNavigate } from "react-router-dom";
import { AreaChart, Area, ResponsiveContainer, LineChart, Line, YAxis, XAxis } from "recharts";
import { Zap, Award, Trophy, Flame, Camera, Bot, Play, Pause, ArrowRight, Activity, CheckCircle2, Atom, Clock, Lock, Check, BookOpen, FlaskConical, Settings, Target, Brain, Star, Sparkles, RefreshCw, Sliders } from "lucide-react";
import { pushNotification } from "../../lib/notificationStore";
import { useUserStore } from "../../store/useUserStore";
import { usePhysicsStore } from "../../store/usePhysicsStore";

function ExperimentsCatalog() {
  const navigate = useNavigate();
  const [activeFilter, setActiveFilter] = useState('All');
  const [searchQuery, setSearchQuery] = useState('');

  const categories = ['All', 'Physics', 'Chemistry', 'Mathematics', 'Engineering'];

  const experiments = [
    {
      subject: 'Physics',
      tier: 'Beginner',
      title: 'Projectile Motion Analysis',
      desc: 'Track objects in free fall and analyze their trajectory using AI vision.',
      time: '15 min',
      xp: '100 XP',
      progress: 100,
      status: 'Review',
      locked: false
    },
    {
      subject: 'Chemistry',
      tier: 'Intermediate',
      title: 'Chemical Reaction Detection',
      desc: 'Use color analysis to detect and classify chemical reactions in real-time.',
      time: '25 min',
      xp: '200 XP',
      progress: 65,
      status: 'Continue',
      locked: false
    },
    {
      subject: 'Physics',
      tier: 'Beginner',
      title: 'Pendulum Period Measurement',
      desc: 'Measure pendulum oscillation periods and verify the relationship with length.',
      time: '20 min',
      xp: '150 XP',
      progress: 0,
      status: 'Start',
      locked: false
    },
    {
      subject: 'Mathematics',
      tier: 'Intermediate',
      title: 'Geometric Shape Recognition',
      desc: 'Train AI to recognize and calculate properties of geometric shapes.',
      time: '30 min',
      xp: '250 XP',
      progress: 0,
      status: 'Start',
      locked: false
    },
    {
      subject: 'Engineering',
      tier: 'Advanced',
      title: 'Bridge Stress Analysis',
      desc: 'Build structures and analyze stress points using computer vision.',
      time: '45 min',
      xp: '400 XP',
      progress: 0,
      status: 'Locked',
      locked: true,
      unlockLevel: 25
    },
    {
      subject: 'Physics',
      tier: 'Advanced',
      title: 'Wave Interference Patterns',
      desc: 'Visualize and analyze wave interference using water ripples.',
      time: '35 min',
      xp: '350 XP',
      progress: 0,
      status: 'Start',
      locked: false
    }
  ];

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
            {cat}
          </button>
        ))}
      </div>

      {/* Card Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mt-6">
        {filtered.map((exp, idx) => (
          <motion.div
            key={exp.title}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: idx * 0.05 }}
            whileHover={{ y: -4, border: '1px solid rgba(6, 182, 212, 0.4)' }}
            className={`p-6 rounded-2xl border backdrop-blur-sm flex flex-col justify-between min-h-[320px] ${
              exp.locked
                ? 'bg-white/2 border-white/5 opacity-50'
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
                    : exp.subject === 'Mathematics'
                    ? 'text-purple-400 bg-purple-500/10 border-purple-500/20'
                    : 'text-orange-400 bg-orange-500/10 border-orange-500/20'
                }`}>
                  {exp.subject}
                </span>

                <span className={`px-2 py-0.5 text-xs font-semibold rounded border flex items-center gap-1 ${
                  exp.tier === 'Beginner'
                    ? 'text-green-400 bg-green-500/10 border-green-500/20'
                    : exp.tier === 'Intermediate'
                    ? 'text-yellow-400 bg-yellow-500/10 border-yellow-500/20'
                    : 'text-red-400 bg-red-500/10 border-red-500/20'
                }`}>
                  {exp.tier}
                  {exp.progress === 100 && exp.tier === 'Beginner' && '✓'}
                </span>
              </div>

              {/* Title & Description */}
              <h3 className="text-xl font-bold text-white mt-4">{exp.title}</h3>
              <p className="text-xs text-gray-400 mt-2 leading-relaxed h-12 overflow-hidden">
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

              {/* Button */}
              {exp.locked ? (
                <div className="w-full py-3 bg-white/2 border border-white/5 rounded-xl text-center text-xs font-bold text-gray-500 flex items-center justify-center gap-2 cursor-not-allowed">
                  <Lock className="w-4 h-4" />
                  Unlock at Level {exp.unlockLevel}
                </div>
              ) : exp.status === 'Review' ? (
                <motion.button
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                  onClick={() => navigate('/dashboard/experiments/active')}
                  className="w-full py-3 bg-green-950/20 hover:bg-green-900/30 border border-green-500/30 hover:border-green-400/50 rounded-xl text-center text-xs font-bold text-green-400 transition-all flex items-center justify-center gap-2"
                >
                  <Check className="w-4 h-4" />
                  Review Experiment
                </motion.button>
              ) : exp.status === 'Continue' ? (
                <motion.button
                  whileHover={{ scale: 1.02, boxShadow: '0 0 25px rgba(6, 182, 212, 0.3)' }}
                  whileTap={{ scale: 0.98 }}
                  onClick={() => navigate('/dashboard/experiments/active')}
                  className="w-full py-3 bg-gradient-to-r from-cyan-500 to-blue-600 text-white rounded-xl text-center text-xs font-bold transition-all flex items-center justify-center gap-2"
                >
                  <Play className="w-4 h-4 fill-current" />
                  Continue
                </motion.button>
              ) : (
                <motion.button
                  whileHover={{ scale: 1.02, backgroundColor: 'rgba(255,255,255,0.1)' }}
                  whileTap={{ scale: 0.98 }}
                  onClick={() => navigate('/dashboard/experiments/active')}
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

// -------------------------------------------------------------

export default ExperimentsCatalog;
