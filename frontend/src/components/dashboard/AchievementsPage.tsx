import React, { useState, useEffect, useRef, Suspense, lazy } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Link, useNavigate } from "react-router-dom";
import { AreaChart, Area, ResponsiveContainer, LineChart, Line, YAxis, XAxis } from "recharts";
import { Zap, Award, Trophy, Flame, Camera, Bot, Play, Pause, ArrowRight, Activity, CheckCircle2, Atom, Clock, Lock, Check, BookOpen, FlaskConical, Settings, Target, Brain, Star, Sparkles, RefreshCw, Sliders } from "lucide-react";
import { pushNotification } from "../../lib/notificationStore";
import { useUserStore } from "../../store/useUserStore";
import { usePhysicsStore } from "../../store/usePhysicsStore";
import { UserAvatar } from "./DashboardLayout";

function AchievementsPage() {
  const [activeTab, setActiveTab] = useState<'badges' | 'leaderboard'>('badges');

  const unlockedBadges = [
    { title: "First Steps", desc: "Complete your first experiment", tag: "Common", date: "Unlocked 2024-01-15", xp: "50 XP", icon: Target },
    { title: "Curious Mind", desc: "Ask 10 questions to AI Tutor", tag: "Common", date: "Unlocked 2024-01-18", xp: "75 XP", icon: Brain },
    { title: "Physics Explorer", desc: "Complete 5 physics experiments", tag: "Uncommon", date: "Unlocked 2024-01-22", xp: "150 XP", icon: Atom },
    { title: "Week Warrior", desc: "Maintain a 7-day streak", tag: "Uncommon", date: "Unlocked 2024-01-25", xp: "200 XP", icon: Flame },
    { title: "Quick Learner", desc: "Complete an experiment in under 5 minutes", tag: "Rare", date: "Unlocked 2024-02-01", xp: "300 XP", icon: Zap },
    { title: "Chemistry Novice", desc: "Complete 3 chemistry experiments", tag: "Uncommon", date: "Unlocked 2024-02-05", xp: "150 XP", icon: FlaskConical }
  ];

  const lockedBadges = [
    { title: "Math Wizard", desc: "Complete all mathematics experiments", tag: "Rare", progress: 4, maxProgress: 8, xp: "350 XP" },
    { title: "Engineering Pro", desc: "Build 10 successful structures", tag: "Rare", progress: 3, maxProgress: 10, xp: "400 XP" },
    { title: "Month Master", desc: "Maintain a 30-day streak", tag: "Epic", progress: 14, maxProgress: 30, xp: "1000 XP" },
    { title: "Perfect Score", desc: "Get 100% on 5 quizzes in a row", tag: "Rare", progress: 2, maxProgress: 5, xp: "350 XP" },
    { title: "STEM Champion", desc: "Reach Level 50", tag: "Rare", progress: 23, maxProgress: 50, xp: "400 XP" },
    { title: "Knowledge Seeker", desc: "Ask 500 questions to AI Tutor", tag: "Rare", progress: 127, maxProgress: 500, xp: "350 XP" }
  ];

  const leaderboardUsers = [
    { rank: 1, name: 'Alex K.', xp: 15420, level: 24, badge: '🏆 Top Scholar' },
    { rank: 2, name: 'Sarah M.', xp: 14850, level: 22, badge: '⭐ Gravity Sage' },
    { rank: 3, name: 'James L.', xp: 13890, level: 21, badge: '⚡ Electro Pro' },
    { rank: 4, name: 'vikas', xp: 2450, level: 12, badge: '🔥 Junior Scientist', isUser: true },
    { rank: 5, name: 'Emily R.', xp: 2210, level: 11, badge: '🔬 Lab Novice' },
    { rank: 6, name: 'David B.', xp: 1980, level: 10, badge: '🧠 Logic Seeker' },
    { rank: 7, name: 'Chloe T.', xp: 1740, level: 9, badge: '📐 Shape Master' },
    { rank: 8, name: 'Daniel H.', xp: 1620, level: 8, badge: '⏱️ Friction Mage' },
    { rank: 9, name: 'Sophia W.', xp: 1450, level: 8, badge: '💫 Orbit Rookie' },
    { rank: 10, name: 'Oliver G.', xp: 1210, level: 7, badge: '💡 Ray Starter' }
  ];

  const [searchQuery, setSearchQuery] = useState('');

  useEffect(() => {
    const handleGlobalSearch = (e: Event) => {
      setSearchQuery((e as CustomEvent).detail);
    };
    window.addEventListener('dashboard-search', handleGlobalSearch);
    return () => window.removeEventListener('dashboard-search', handleGlobalSearch);
  }, []);

  const filteredUnlocked = unlockedBadges.filter(badge =>
    badge.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
    badge.desc.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const filteredLocked = lockedBadges.filter(badge =>
    badge.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
    badge.desc.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="p-6 relative z-10 max-w-7xl mx-auto space-y-6 pt-2">

      {/* Tabs and XP Indicator */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-white/5 pb-4">
        <div className="flex items-center bg-[#13131c] p-1 rounded-xl border border-white/5 self-start">
          <button
            onClick={() => setActiveTab('badges')}
            className={`px-4 py-2 text-xs font-bold rounded-lg transition-all ${
              activeTab === 'badges'
                ? 'bg-gradient-to-r from-cyan-500 to-blue-600 text-white shadow-lg shadow-cyan-500/20'
                : 'text-gray-400 hover:text-white'
            }`}
          >
            My Badges
          </button>
          <button
            onClick={() => setActiveTab('leaderboard')}
            className={`px-4 py-2 text-xs font-bold rounded-lg transition-all ${
              activeTab === 'leaderboard'
                ? 'bg-gradient-to-r from-cyan-500 to-blue-600 text-white shadow-lg shadow-cyan-500/20'
                : 'text-gray-400 hover:text-white'
            }`}
          >
            Global Leaderboard
          </button>
        </div>
        
        <div className="flex items-center gap-2 px-3 py-1.5 bg-cyan-500/10 border border-cyan-500/20 rounded-xl text-cyan-400 text-xs font-bold self-start sm:self-auto">
          <Zap className="w-3.5 h-3.5 fill-current" />
          <span>2,450 XP • Level 12</span>
        </div>
      </div>

      {activeTab === 'badges' ? (
        <div className="space-y-8">
          {/* Metrics Row */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className="py-8 px-6 bg-[#12121a] border border-[#22222f] rounded-2xl flex flex-col justify-center items-center text-center shadow-xl"
            >
              <h3 className="text-4xl font-extrabold text-white tracking-tight">6/12</h3>
              <span className="text-[11px] text-gray-500 mt-2 font-semibold uppercase tracking-wider">Achievements Unlocked</span>
            </motion.div>

            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.05 }}
              className="py-8 px-6 bg-[#12121a] border border-[#22222f] rounded-2xl flex flex-col justify-center items-center text-center shadow-xl"
            >
              <h3 className="text-4xl font-extrabold text-[#925] text-amber-500 tracking-tight">925</h3>
              <span className="text-[11px] text-gray-500 mt-2 font-semibold uppercase tracking-wider">XP from Achievements</span>
            </motion.div>

            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 }}
              className="py-8 px-6 bg-[#12121a] border border-[#22222f] rounded-2xl flex flex-col justify-center items-center text-center shadow-xl"
            >
              <h3 className="text-4xl font-extrabold text-cyan-400 tracking-tight">50%</h3>
              <span className="text-[11px] text-gray-500 mt-2 font-semibold uppercase tracking-wider">Completion Rate</span>
            </motion.div>

            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.15 }}
              className="py-8 px-6 bg-[#12121a] border border-[#22222f] rounded-2xl flex flex-col justify-center items-center text-center shadow-xl"
            >
              <h3 className="text-3xl font-black bg-gradient-to-r from-purple-400 via-pink-400 to-pink-500 bg-clip-text text-transparent tracking-tight">Quick Learner</h3>
              <span className="text-[11px] text-gray-500 mt-3 font-semibold uppercase tracking-wider">Rarest Unlocked</span>
            </motion.div>
          </div>

          {/* Unlocked (6) Section */}
          <div className="space-y-4">
            <div className="flex items-center gap-2 text-green-400 font-bold text-sm tracking-wide uppercase">
              <span className="flex items-center justify-center w-5 h-5 rounded-full bg-green-500/10 border border-green-500/20 text-[10px]">✓</span>
              <span>Unlocked (6)</span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {filteredUnlocked.map((badge, idx) => (
                <motion.div
                  key={badge.title}
                  initial={{ opacity: 0, y: 15 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: idx * 0.05 }}
                  whileHover={{ y: -3, border: "1px solid rgba(16, 185, 129, 0.2)", backgroundColor: "#151522" }}
                  className="p-6 bg-[#12121a] border border-[#22222f] rounded-2xl flex flex-col justify-between min-h-[150px] shadow-lg transition-all"
                >
                  <div className="flex justify-between items-start gap-4">
                    <div className="flex gap-4">
                      {/* Round circle icon container */}
                      <div className={`w-12 h-12 rounded-xl flex items-center justify-center flex-shrink-0 ${
                        badge.title === "First Steps" ? "bg-rose-500/15 border border-rose-500/30 text-rose-400" :
                        badge.title === "Curious Mind" ? "bg-amber-500/15 border border-amber-500/30 text-amber-400" :
                        badge.tag === "Uncommon" ? "bg-emerald-500/15 border border-emerald-500/30 text-emerald-400" :
                        badge.tag === "Rare" ? "bg-blue-500/15 border border-blue-500/30 text-blue-400" :
                        "bg-[#1c1c2b] text-gray-400"
                      }`}>
                        <badge.icon className="w-5 h-5" />
                      </div>
                      <div>
                        <h4 className="text-base font-bold text-white tracking-wide">{badge.title}</h4>
                        <p className="text-xs text-gray-400 mt-1 leading-relaxed">{badge.desc}</p>
                      </div>
                    </div>
                    {/* XP display */}
                    <span className="text-xs font-bold text-yellow-500 flex items-center gap-1 flex-shrink-0 self-start mt-0.5">
                      <Star className="w-3.5 h-3.5 fill-current text-yellow-500" />
                      {badge.xp}
                    </span>
                  </div>
                  
                  {/* Bottom section with Tag (if present) and Unlocked Date */}
                  <div className="flex justify-between items-center mt-4 pt-3 border-t border-white/5">
                    <div>
                      {/* Only show tag if it is not Common */}
                      {badge.tag && badge.tag !== "Common" && (
                        <span className={`px-2 py-0.5 text-[10px] font-bold rounded-md border ${
                          badge.tag === "Uncommon" ? "bg-emerald-955/40 text-emerald-400 border-emerald-500/20" :
                          badge.tag === "Rare" ? "bg-blue-955/40 text-blue-400 border-blue-500/20" :
                          "bg-purple-955/40 text-purple-400 border-purple-500/20"
                        }`}>
                          {badge.tag}
                        </span>
                      )}
                    </div>
                    <span className="text-[10px] text-gray-500 font-medium">
                      {badge.date}
                    </span>
                  </div>
                </motion.div>
              ))}
            </div>
          </div>

          {/* Locked (6) Section */}
          <div className="space-y-4">
            <div className="flex items-center gap-2 text-gray-500 font-bold text-sm tracking-wide uppercase">
              <span className="flex items-center justify-center w-5 h-5 rounded-full bg-white/5 border border-white/10 text-[10px]">🔒</span>
              <span>Locked (6)</span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {filteredLocked.map((badge, idx) => (
                <motion.div
                  key={badge.title}
                  initial={{ opacity: 0, y: 15 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: idx * 0.05 }}
                  className="p-6 bg-[#12121a]/60 border border-[#22222f]/80 rounded-2xl flex flex-col justify-between min-h-[170px] shadow-lg"
                >
                  <div className="flex justify-between items-start gap-4">
                    <div className="flex gap-4">
                      {/* Lock Circle Icon Container */}
                      <div className={`w-12 h-12 rounded-xl flex items-center justify-center flex-shrink-0 ${
                        badge.tag === "Epic" ? "bg-purple-950/20 border border-purple-500/20 text-purple-400/60" :
                        "bg-blue-950/20 border border-blue-500/20 text-blue-400/60"
                      }`}>
                        <Lock className="w-5 h-5" />
                      </div>
                      <div>
                        <h4 className="text-base font-bold text-white/90 tracking-wide">{badge.title}</h4>
                        <p className="text-xs text-gray-500 mt-1 leading-relaxed">{badge.desc}</p>
                      </div>
                    </div>
                  </div>

                  {/* Progress & Bar */}
                  <div className="mt-5 space-y-2">
                    <div className="flex justify-between text-[11px] font-bold text-gray-500">
                      <span>Progress</span>
                      <span>{badge.progress}/{badge.maxProgress}</span>
                    </div>
                    <div className="h-1.5 bg-[#1b1b26] rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all duration-500 ${
                          badge.tag === "Epic" ? "bg-gradient-to-r from-purple-500 to-pink-500" :
                          "bg-gradient-to-r from-blue-500 to-cyan-500"
                        }`}
                        style={{ width: `${(badge.progress / badge.maxProgress) * 105}%` }}
                      />
                    </div>

                    <div className="flex justify-between items-center pt-2">
                      <span className={`px-2 py-0.5 text-[10px] font-bold rounded-md border ${
                        badge.tag === "Epic" ? "bg-purple-955/40 text-purple-400 border-purple-500/20" :
                        "bg-blue-955/40 text-blue-400 border-blue-500/20"
                      }`}>
                        {badge.tag}
                      </span>
                      <span className="text-xs font-bold text-gray-500 flex items-center gap-1.5">
                        <Star className="w-3.5 h-3.5 fill-current text-gray-600" />
                        {badge.xp}
                      </span>
                    </div>
                  </div>
                </motion.div>
              ))}
            </div>
          </div>
        </div>
      ) : (
        /* Global Leaderboard Tab */
        <div className="space-y-8">
          {/* Top 3 Podium Grid */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 items-end mt-8">
            {/* 2nd Place */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 }}
              whileHover={{ y: -5 }}
              className="order-2 md:order-1 p-6 bg-gradient-to-t from-[#12121a] to-[#181826] border border-gray-500/20 rounded-2xl flex flex-col items-center text-center relative shadow-xl min-h-[220px]"
            >
              <div className="absolute -top-6 w-12 h-12 rounded-full bg-gradient-to-tr from-gray-400 to-gray-200 border-4 border-[#0b0b14] flex items-center justify-center text-white font-extrabold shadow-md">
                2
              </div>
              <div className="w-16 h-16 rounded-full bg-gradient-to-tr from-gray-400 to-gray-200 p-0.5 shadow-lg mt-4">
                <div className="w-full h-full rounded-full bg-[#12121a] flex items-center justify-center text-white font-black text-xl">
                  S
                </div>
              </div>
              <h3 className="text-lg font-bold text-white mt-3">Sarah M.</h3>
              <p className="text-xs text-gray-400">⭐ Gravity Sage • Level 22</p>
              <div className="mt-4 px-4 py-1.5 bg-gray-500/10 border border-gray-500/20 rounded-xl text-gray-300 font-extrabold text-sm">
                14,850 XP
              </div>
            </motion.div>

            {/* 1st Place */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              whileHover={{ y: -5 }}
              className="order-1 md:order-2 p-8 bg-gradient-to-t from-[#12121a] to-[#201c1c] border border-yellow-500/30 rounded-2xl flex flex-col items-center text-center relative shadow-2xl min-h-[260px] md:scale-105 z-10"
            >
              {/* Crown badge */}
              <div className="absolute -top-8 w-16 h-16 rounded-full bg-gradient-to-tr from-yellow-500 to-amber-300 border-4 border-[#0b0b14] flex items-center justify-center text-yellow-950 font-black text-xl shadow-lg animate-bounce">
                👑
              </div>
              <div className="w-20 h-20 rounded-full bg-gradient-to-tr from-yellow-500 to-amber-300 p-0.5 shadow-lg mt-2">
                <div className="w-full h-full rounded-full bg-[#12121a] flex items-center justify-center text-white font-black text-2xl">
                  A
                </div>
              </div>
              <h3 className="text-xl font-black text-white mt-3 flex items-center gap-1.5">
                Alex K.
              </h3>
              <p className="text-xs text-yellow-400 font-semibold">🏆 Top Scholar • Level 24</p>
              <div className="mt-4 px-5 py-2 bg-yellow-500/10 border border-yellow-500/20 rounded-xl text-yellow-400 font-extrabold text-base shadow-lg shadow-yellow-500/5">
                15,420 XP
              </div>
            </motion.div>

            {/* 3rd Place */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.15 }}
              whileHover={{ y: -5 }}
              className="order-3 p-6 bg-gradient-to-t from-[#12121a] to-[#181826] border border-orange-500/20 rounded-2xl flex flex-col items-center text-center relative shadow-xl min-h-[220px]"
            >
              <div className="absolute -top-6 w-12 h-12 rounded-full bg-gradient-to-tr from-orange-600 to-orange-400 border-4 border-[#0b0b14] flex items-center justify-center text-white font-extrabold shadow-md">
                3
              </div>
              <div className="w-16 h-16 rounded-full bg-gradient-to-tr from-orange-600 to-orange-400 p-0.5 shadow-lg mt-4">
                <div className="w-full h-full rounded-full bg-[#12121a] flex items-center justify-center text-white font-black text-xl">
                  J
                </div>
              </div>
              <h3 className="text-lg font-bold text-white mt-3">James L.</h3>
              <p className="text-xs text-gray-400">⚡ Electro Pro • Level 21</p>
              <div className="mt-4 px-4 py-1.5 bg-orange-500/10 border border-orange-500/20 rounded-xl text-orange-400 font-extrabold text-sm">
                13,890 XP
              </div>
            </motion.div>
          </div>

          {/* Leaderboard Table List */}
          <div className="bg-[#12121a] border border-[#22222f] rounded-2xl overflow-hidden shadow-2xl">
            <div className="p-5 border-b border-white/5 bg-white/[0.01] flex justify-between items-center">
              <div>
                <h3 className="text-white font-bold text-base">Top Contenders</h3>
                <p className="text-gray-500 text-xs mt-0.5">Performance ranking of junior and senior scientists this week</p>
              </div>
              <span className="text-xs text-cyan-400 font-bold bg-cyan-500/10 border border-cyan-500/20 px-3 py-1 rounded-full">
                Your Rank: #4
              </span>
            </div>

            <div className="divide-y divide-white/5">
              {leaderboardUsers.slice(3).map((user) => (
                <div
                  key={user.rank}
                  className={`p-4 flex items-center justify-between transition-all ${
                    user.isUser
                      ? 'bg-cyan-500/5 border-y border-cyan-500/20 shadow-inner'
                      : 'hover:bg-white/[0.02]'
                  }`}
                >
                  <div className="flex items-center gap-4">
                    {/* Rank Number */}
                    <div className="w-8 h-8 rounded-full bg-[#1b1b26] border border-white/5 flex items-center justify-center font-bold text-gray-400 text-sm">
                      {user.rank}
                    </div>

                    {/* Avatar with dynamic colors */}
                    <div className={`w-10 h-10 rounded-full flex items-center justify-center text-white font-extrabold text-sm shadow-md overflow-hidden ${
                      user.isUser
                        ? 'bg-gradient-to-tr from-cyan-500 to-blue-600'
                        : 'bg-[#1b1b26] border border-white/10 text-gray-300'
                    }`}>
                      {user.isUser ? (
                        <UserAvatar className="w-full h-full object-cover rounded-full" />
                      ) : (
                        user.name.charAt(0).toUpperCase()
                      )}
                    </div>

                    <div>
                      <h4 className="text-sm font-bold text-white flex items-center gap-2">
                        {user.name}
                        {user.isUser && (
                          <span className="px-1.5 py-0.5 bg-cyan-500 text-black text-[9px] font-black rounded-md uppercase tracking-wider shadow-md shadow-cyan-500/25">
                            YOU
                          </span>
                        )}
                      </h4>
                      <p className="text-[11px] text-gray-500 mt-0.5">{user.badge} • Level {user.level}</p>
                    </div>
                  </div>

                  <div className="text-right">
                    <span className="text-sm font-extrabold text-cyan-400">{user.xp.toLocaleString()} XP</span>
                    <p className="text-[10px] text-gray-500 font-medium">this week</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// -------------------------------------------------------------

export default AchievementsPage;
