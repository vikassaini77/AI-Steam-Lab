import React, { useState, useEffect, useRef, Suspense, lazy } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Link, useNavigate } from "react-router-dom";
import { AreaChart, Area, ResponsiveContainer, LineChart, Line, YAxis, XAxis } from "recharts";
import { Zap, Award, Trophy, Flame, Camera, Bot, Play, Pause, ArrowRight, Activity, CheckCircle2, Atom, Clock, Lock, Check, BookOpen, FlaskConical, Settings, Target, Brain, Star, Sparkles, RefreshCw, Sliders } from "lucide-react";
import { pushNotification } from "../../lib/notificationStore";
import { useUserStore } from "../../store/useUserStore";
import { usePhysicsStore } from "../../store/usePhysicsStore";

function ChallengesPage() {
  const navigate = useNavigate();

  const quests = [
    {
      title: 'Pendulum Period Quest',
      reward: '+300 XP',
      difficulty: 'Intermediate',
      category: 'Physics',
      xp: 300,
      badge: '⏱️ Period Pioneer',
      desc: 'Accurately map the period (T) of the pendulum bob by modifying lengths in real-time camera calibrations.',
      completed: true
    },
    {
      title: 'Gravity Constant Proof',
      reward: '+500 XP',
      difficulty: 'Advanced',
      category: 'Gravitation',
      xp: 500,
      badge: '🌌 Gravity Conqueror',
      desc: 'Verify the earth acceleration limit (9.8 m/s²) on camera visualizers using string angle and amplitude tracking.',
      completed: false
    },
    {
      title: 'Mechanical Energy Test',
      reward: '+200 XP',
      difficulty: 'Beginner',
      category: 'Kinematics',
      xp: 200,
      badge: '⚡ Energy Sage',
      desc: 'Map the pendulum velocity at lowest oscillation coordinates and prove the mechanical energy conservation model.',
      completed: false
    },
    {
      title: 'Harmonic Motion Explorer',
      reward: '+600 XP',
      difficulty: 'Hard',
      category: 'Thermodynamics',
      xp: 600,
      badge: '🌀 Harmonic Emperor',
      desc: 'Calibrate simple harmonic damping effects in low-damping conditions and output the logarithmic ratio plots.',
      completed: false
    }
  ];

  return (
    <div className="p-6 relative z-10 max-w-6xl mx-auto space-y-6 pt-2">

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {quests.map((q, idx) => (
          <motion.div
            key={q.title}
            initial={{ opacity: 0, y: 15 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: idx * 0.1 }}
            whileHover={{ y: -4, border: '1px solid rgba(6, 182, 212, 0.4)' }}
            className={`p-5 rounded-2xl border backdrop-blur-sm flex flex-col justify-between ${
              q.completed
                ? 'bg-gradient-to-br from-green-500/5 to-white/5 border-green-500/20'
                : 'bg-white/5 border-white/10'
            }`}
          >
            <div>
              <div className="flex justify-between items-start gap-4">
                <span className={`px-2 py-0.5 text-[10px] font-bold rounded border ${
                  q.difficulty === 'Beginner'
                    ? 'bg-green-500/10 text-green-400 border-green-500/20'
                    : q.difficulty === 'Intermediate'
                    ? 'bg-cyan-500/10 text-cyan-400 border-cyan-500/20'
                    : 'bg-violet-500/10 text-violet-400 border-violet-500/20'
                }`}>
                  {q.difficulty}
                </span>
                <span className="text-xs font-bold text-gray-500">{q.badge}</span>
              </div>
              <h3 className="text-lg font-bold text-white mt-3 flex items-center gap-2">
                {q.title}
                {q.completed && <CheckCircle2 className="w-5 h-5 text-green-400" />}
              </h3>
              <p className="text-xs text-gray-400 mt-2 leading-relaxed">{q.desc}</p>
            </div>

            <div className="flex justify-between items-center mt-6 pt-4 border-t border-white/5">
              <span className="text-cyan-400 font-extrabold text-sm">{q.reward}</span>
              <motion.button
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                onClick={() => navigate('/dashboard/experiments')}
                className={`px-4 py-2 text-xs font-semibold rounded-lg ${
                  q.completed
                    ? 'bg-green-500/20 text-green-400 hover:bg-green-500/30'
                    : 'bg-gradient-to-r from-cyan-500 to-blue-600 text-white shadow-lg shadow-cyan-500/10'
                }`}
              >
                {q.completed ? 'Rerun Lab' : 'Launch Lab'}
              </motion.button>
            </div>
          </motion.div>
        ))}
      </div>
    </div>
  );
}

// -------------------------------------------------------------

export default ChallengesPage;
