import React, { useState, useEffect, useRef, Suspense, lazy } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Link, useNavigate } from "react-router-dom";
import { AreaChart, Area, ResponsiveContainer, LineChart, Line, YAxis, XAxis } from "recharts";
import { Zap, Award, Trophy, Flame, Camera, Bot, Play, Pause, ArrowRight, Activity, CheckCircle2, Atom, Clock, Lock, Check, BookOpen, FlaskConical, Settings, Target, Brain, Star, Sparkles, RefreshCw, Sliders } from "lucide-react";
import { pushNotification } from "../../lib/notificationStore";
import { useUserStore } from "../../store/useUserStore";
import { usePhysicsStore } from "../../store/usePhysicsStore";

// -------------------------------------------------------------
// Component: DashboardHome
// -------------------------------------------------------------
function DashboardHome({ session }: { session: any }) {
  const navigate = useNavigate();
  const user = session?.user;
  const fullName = user?.user_metadata?.full_name || 'Student';

  const stats = [
    { label: 'Total XP', value: '2,450 XP', icon: Zap, color: 'text-cyan-400', bg: 'bg-cyan-500/10' },
    { label: 'Daily Streak', value: '5 Days', icon: Flame, color: 'text-orange-400', bg: 'bg-orange-500/10' },
    { label: 'Completed Labs', value: '12 Labs', icon: Camera, color: 'text-green-400', bg: 'bg-green-500/10' },
    { label: 'AI Interactions', value: '47 Ask', icon: Bot, color: 'text-violet-400', bg: 'bg-violet-500/10' }
  ];

  const recentActivities = [
    { type: 'xp', text: 'Earned 150 XP for pendulum analysis', time: '2 mins ago' },
    { type: 'badge', text: 'Unlocked "Week Warrior" achievement badge', time: '1 hour ago' },
    { type: 'lab', text: 'Completed Simple Harmonic Motion calibration', time: '3 hours ago' },
    { type: 'chat', text: 'Reviewed kinetic energy formulas with AI tutor', time: '5 hours ago' }
  ];

  const dailyQuests = [
    { title: 'Pendulum Period Quest', reward: '+300 XP', xp: 300, difficulty: 'Intermediate', duration: '10m' },
    { title: 'Gravity Constant Proof', reward: '+500 XP', xp: 500, difficulty: 'Advanced', duration: '15m' },
    { title: 'Mechanical Energy Test', reward: '+200 XP', xp: 200, difficulty: 'Beginner', duration: '5m' }
  ];

  const handleQuestComplete = (quest: { title: string; xp: number; reward: string }) => {
    pushNotification(`⚡ +${quest.xp} XP earned! You completed "${quest.title}"`, 'xp');
  };

  return (
    <div className="p-6 space-y-8 relative z-10 max-w-7xl mx-auto">
      {/* Welcome Banner */}
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 bg-gradient-to-r from-cyan-900/20 via-blue-900/10 to-transparent p-6 rounded-2xl border border-cyan-500/20 backdrop-blur-md"
      >
        <div>
          <h1 className="text-3xl font-extrabold text-white flex items-center gap-3">
            Welcome Back, {fullName}!
            <motion.span
              animate={{ rotate: [0, 20, 0] }}
              transition={{ repeat: Infinity, duration: 2, repeatDelay: 1 }}
            >
              👋
            </motion.span>
          </h1>
          <p className="text-gray-400 text-sm mt-1">
            Junior Scientist • Level 12 • 550 XP to Level 13
          </p>
        </div>
        <motion.button
          whileHover={{ scale: 1.05, boxShadow: '0 0 25px rgba(6, 182, 212, 0.4)' }}
          whileTap={{ scale: 0.95 }}
          onClick={() => navigate('/dashboard/experiments')}
          className="px-6 py-3 bg-gradient-to-r from-cyan-500 to-blue-600 text-white rounded-xl font-bold flex items-center gap-2"
        >
          <Play className="w-5 h-5 fill-current" />
          Launch AI Lab
        </motion.button>
      </motion.div>

      {/* Grid Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {stats.map((stat, i) => (
          <motion.div
            key={stat.label}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.1 }}
            whileHover={{ y: -4, scale: 1.02 }}
            className="p-5 bg-white/5 rounded-2xl border border-white/10 backdrop-blur-sm flex items-center gap-4"
          >
            <div className={`w-12 h-12 rounded-xl ${stat.bg} flex items-center justify-center`}>
              <stat.icon className={`w-6 h-6 ${stat.color}`} />
            </div>
            <div>
              <p className="text-xs text-gray-500 font-semibold">{stat.label}</p>
              <h3 className="text-xl font-bold text-white mt-0.5">{stat.value}</h3>
            </div>
          </motion.div>
        ))}
      </div>

      {/* Workspace Focus Banner */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <motion.div
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          className="lg:col-span-2 bg-gradient-to-br from-cyan-500/10 to-blue-500/5 rounded-2xl border border-cyan-500/20 p-6 flex flex-col justify-between"
        >
          <div>
            <span className="px-3 py-1 bg-cyan-500/20 text-cyan-400 text-xs font-bold rounded-full border border-cyan-500/30">
              Interactive Lab
            </span>
            <h2 className="text-2xl font-extrabold text-white mt-4 mb-2">
              Pendulum Motion & Energy conservation
            </h2>
            <p className="text-gray-300 text-sm leading-relaxed max-w-xl">
              Turn your webcam into an advanced sensor array. Track kinetic energy values, map gravity constraints, and review laws of motion in real-time.
            </p>
          </div>
          <div className="flex items-center justify-between gap-4 mt-8 pt-4 border-t border-white/5">
            <span className="text-xs text-gray-400 flex items-center gap-1.5">
              <Clock className="w-4 h-4 text-cyan-400" />
              Recent Calibration: Today at 3:12 PM
            </span>
            <Link
              to="/dashboard/experiments"
              className="text-cyan-400 text-sm font-bold flex items-center gap-1 group hover:text-cyan-300 transition-colors"
            >
              Resume Experiment
              <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
            </Link>
          </div>
        </motion.div>

        {/* Level XP Card */}
        <motion.div
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          className="bg-white/5 rounded-2xl border border-white/10 p-6 flex flex-col justify-between backdrop-blur-sm"
        >
          <div>
            <h3 className="text-lg font-bold text-white mb-1 flex items-center gap-2">
              <Award className="w-5 h-5 text-yellow-400" />
              Level Progression
            </h3>
            <p className="text-xs text-gray-500">Keep running experiments to unlock Level 13.</p>
          </div>

          <div className="my-6 space-y-3">
            <div className="flex justify-between items-baseline">
              <span className="text-xs text-cyan-400 font-bold">2,450 XP</span>
              <span className="text-xs text-gray-500 font-bold">3,000 XP</span>
            </div>
            <div className="h-3 bg-white/10 rounded-full overflow-hidden relative">
              <motion.div
                initial={{ width: 0 }}
                animate={{ width: `${(2450/3000)*100}%` }}
                className="h-full bg-gradient-to-r from-cyan-400 to-blue-500 rounded-full"
              />
            </div>
            <p className="text-xs text-center text-gray-400">
              Only <strong>550 XP</strong> left for Level 13 upgrade
            </p>
          </div>

          <Link
            to="/dashboard/achievements"
            className="w-full py-3 bg-white/5 hover:bg-white/10 border border-white/10 rounded-xl text-center text-sm font-semibold text-white transition-colors block"
          >
            View Achievements
          </Link>
        </motion.div>
      </div>

      {/* Rows: Activities vs Quests */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recent Activities */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="bg-white/5 rounded-2xl border border-white/10 p-6 backdrop-blur-sm"
        >
          <h3 className="text-lg font-bold text-white mb-4 flex items-center gap-2">
            <Activity className="w-5 h-5 text-cyan-400" />
            Recent Activity
          </h3>
          <div className="space-y-4">
            {recentActivities.map((act, idx) => (
              <div key={idx} className="flex gap-4 items-start border-b border-white/5 pb-3 last:border-0 last:pb-0">
                <div className="w-8 h-8 rounded-lg bg-white/5 border border-white/10 flex items-center justify-center flex-shrink-0">
                  {act.type === 'xp' && <Zap className="w-4 h-4 text-cyan-400" />}
                  {act.type === 'badge' && <Trophy className="w-4 h-4 text-yellow-400" />}
                  {act.type === 'lab' && <Camera className="w-4 h-4 text-green-400" />}
                  {act.type === 'chat' && <Bot className="w-4 h-4 text-violet-400" />}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-gray-200 font-medium truncate">{act.text}</p>
                  <span className="text-xs text-gray-500">{act.time}</span>
                </div>
              </div>
            ))}
          </div>
        </motion.div>

        {/* Daily challenges */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="bg-white/5 rounded-2xl border border-white/10 p-6 backdrop-blur-sm"
        >
          <div className="flex justify-between items-center mb-4">
            <h3 className="text-lg font-bold text-white flex items-center gap-2">
              <Trophy className="w-5 h-5 text-yellow-400" />
              Daily Challenges
            </h3>
            <Link to="/dashboard/challenges" className="text-xs text-cyan-400 font-semibold hover:underline">
              View All Quests
            </Link>
          </div>
          <div className="space-y-3">
            {dailyQuests.map((quest, idx) => (
              <div
                key={idx}
                onClick={() => handleQuestComplete(quest)}
                className="p-3 bg-white/5 rounded-xl border border-white/5 flex items-center justify-between hover:bg-white/10 hover:border-cyan-500/20 transition-all cursor-pointer group"
              >
                <div>
                  <h4 className="text-sm font-semibold text-white group-hover:text-cyan-300 transition-colors">{quest.title}</h4>
                  <div className="flex gap-2 mt-1">
                    <span className="px-1.5 py-0.5 bg-cyan-500/10 text-cyan-400 text-[10px] rounded border border-cyan-500/20">
                      {quest.difficulty}
                    </span>
                    <span className="text-[10px] text-gray-500 flex items-center gap-1">
                      <Clock className="w-3 h-3" />
                      {quest.duration}
                    </span>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-sm font-extrabold text-cyan-400">{quest.reward}</span>
                  <span className="text-[10px] text-gray-600 group-hover:text-cyan-500 transition-colors font-bold">Start →</span>
                </div>
              </div>
            ))}
          </div>
        </motion.div>
      </div>
    </div>
  );
}


export default DashboardHome;
