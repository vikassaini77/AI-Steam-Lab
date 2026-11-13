import { motion } from 'framer-motion';
import { useState, useEffect } from 'react';
import {
  Trophy,
  Star,
  Flame,
  Target,
  Zap,
  Award,
  TrendingUp,
  Lock,
  CheckCircle2,
} from 'lucide-react';
import { useUserStore } from '../../store/useUserStore';
import { getApiBaseUrl, getAuthHeaders } from '../../lib/api';

interface GamificationPanelProps {
  view: 'insights' | 'progress';
}

interface LeaderboardUser {
  id: string | number;
  rank: number;
  name: string;
  xp: number;
  badges: number;
}

interface RecentExperimentItem {
  id?: string;
  name?: string;
  title?: string;
  status?: string;
}

export default function GamificationPanel({ view }: GamificationPanelProps) {
  const { xp: currentXP, level, dailyStreak, completedLabs, aiInteractions } = useUserStore();
  const [leaderboard, setLeaderboard] = useState<LeaderboardUser[]>([]);
  const [recentExperiments, setRecentExperiments] = useState<RecentExperimentItem[]>([]);

  const xpForNextLevel = Math.max(250, level * 250);
  const progress = Math.min(100, Math.round((currentXP / xpForNextLevel) * 100));

  useEffect(() => {
    const fetchData = async () => {
      try {
        const API_URL = getApiBaseUrl();
        const headers = await getAuthHeaders();
        
        // Fetch real leaderboard
        const lbRes = await fetch(`${API_URL}/api/gamification/leaderboard`);
        if (lbRes.ok) {
          const lbData = await lbRes.json();
          if (Array.isArray(lbData)) {
            setLeaderboard(lbData.slice(0, 5));
          }
        }

        // Fetch real experiment history
        const expRes = await fetch(`${API_URL}/api/experiments/history`, { headers });
        if (expRes.ok) {
          const expData = await expRes.json();
          const list = Array.isArray(expData) ? expData : (expData.experiments || expData.history || []);
          setRecentExperiments(list.slice(0, 4));
        }
      } catch (err) {
        console.warn('Could not sync gamification panel data:', err);
      }
    };

    fetchData();
  }, []);

  const achievements = [
    {
      id: 1,
      name: 'First Steps',
      description: 'Complete your first experiment',
      icon: Star,
      unlocked: completedLabs > 0,
      xp: 100,
      color: 'from-yellow-500 to-orange-500',
    },
    {
      id: 2,
      name: 'Physics Apprentice',
      description: 'Analyze 3 physics experiments',
      icon: Target,
      unlocked: completedLabs >= 3,
      xp: 250,
      color: 'from-cyan-500 to-blue-500',
    },
    {
      id: 3,
      name: 'Kinematics Master',
      description: 'Complete 6 laboratory modules',
      icon: Award,
      unlocked: completedLabs >= 6,
      xp: 500,
      color: 'from-violet-500 to-purple-500',
    },
    {
      id: 4,
      name: 'AI Collaborator',
      description: 'Have 10 interactive STEM tutoring queries',
      icon: Trophy,
      unlocked: aiInteractions >= 10,
      xp: 300,
      color: 'from-green-500 to-emerald-500',
    },
    {
      id: 5,
      name: 'Streak Pioneer',
      description: 'Maintain a 3-day active streak',
      icon: Flame,
      unlocked: dailyStreak >= 3,
      xp: 200,
      color: 'from-orange-500 to-red-500',
    },
  ];

  const daysOfWeek = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
  const todayIdx = (new Date().getDay() + 6) % 7; // Monday = 0

  return (
    <div className="p-4 space-y-4 text-left">
      {/* Level & XP Header */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        className="bg-gradient-to-br from-cyan-500/20 to-blue-500/20 rounded-xl p-4 border border-cyan-500/30"
      >
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-3">
            <div className="relative">
              <div className="w-16 h-16 rounded-full bg-gradient-to-r from-cyan-500 to-blue-500 flex items-center justify-center">
                <span className="text-2xl font-bold text-white">{level}</span>
              </div>
              <motion.div
                animate={{ rotate: 360 }}
                transition={{ duration: 3, repeat: Infinity, ease: 'linear' }}
                className="absolute -top-1 -right-1 w-6 h-6 bg-yellow-500 rounded-full flex items-center justify-center"
              >
                <Star className="w-4 h-4 text-white" />
              </motion.div>
            </div>
            <div>
              <p className="text-white font-semibold">Level {level}</p>
              <p className="text-gray-400 text-sm">
                {level >= 5 ? 'Senior Researcher' : level >= 2 ? 'Lab Apprentice' : 'Junior Scientist'}
              </p>
            </div>
          </div>
          <div className="text-right">
            <p className="text-cyan-400 font-semibold">{currentXP.toLocaleString()} XP</p>
            <p className="text-gray-500 text-xs">/{xpForNextLevel.toLocaleString()} XP</p>
          </div>
        </div>

        {/* XP Progress bar */}
        <div className="h-3 bg-white/10 rounded-full overflow-hidden">
          <motion.div
            initial={{ width: 0 }}
            animate={{ width: `${progress}%` }}
            transition={{ duration: 1, ease: 'easeOut' }}
            className="h-full bg-gradient-to-r from-cyan-400 to-blue-500 rounded-full relative"
          >
            <motion.div
              animate={{ x: ['0%', '100%'] }}
              transition={{ duration: 1, repeat: Infinity }}
              className="absolute inset-0 bg-gradient-to-r from-transparent via-white/20 to-transparent"
            />
          </motion.div>
        </div>
        <p className="text-xs text-gray-500 mt-2 text-center">
          {Math.max(0, xpForNextLevel - currentXP).toLocaleString()} XP to Level {level + 1}
        </p>
      </motion.div>

      {view === 'insights' ? (
        <>
          {/* Streak Calendar */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="bg-white/5 rounded-xl p-4 border border-white/10"
          >
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <Flame className="w-5 h-5 text-orange-500" />
                <span className="text-white font-semibold">Learning Streak</span>
              </div>
              <span className="text-orange-400 font-bold">{dailyStreak} {dailyStreak === 1 ? 'day' : 'days'}</span>
            </div>
            <div className="flex justify-between">
              {daysOfWeek.map((day, index) => {
                const isActive = index <= todayIdx && dailyStreak > (todayIdx - index);
                return (
                  <motion.div
                    key={day}
                    className="text-center"
                    initial={{ scale: 0.8, opacity: 0 }}
                    animate={{ scale: 1, opacity: 1 }}
                    transition={{ delay: index * 0.05 }}
                  >
                    <div
                      className={`w-10 h-10 rounded-lg flex items-center justify-center mb-1 ${
                        isActive
                          ? 'bg-gradient-to-r from-orange-500 to-red-500 text-white'
                          : 'bg-white/5 border border-white/10 text-gray-500'
                      }`}
                    >
                      {isActive ? (
                        <Flame className="w-5 h-5 text-white" />
                      ) : (
                        <span className="text-xs">{index + 1}</span>
                      )}
                    </div>
                    <span className="text-xs text-gray-500">{day}</span>
                  </motion.div>
                );
              })}
            </div>
          </motion.div>

          {/* Recent Activity */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="bg-white/5 rounded-xl p-4 border border-white/10"
          >
            <div className="flex items-center gap-2 mb-3">
              <TrendingUp className="w-5 h-5 text-cyan-400" />
              <span className="text-white font-semibold">Recent Activity</span>
            </div>
            <div className="space-y-3">
              {recentExperiments.length > 0 ? (
                recentExperiments.map((exp: RecentExperimentItem, index: number) => (
                  <motion.div
                    key={exp.id || index}
                    initial={{ x: -10, opacity: 0 }}
                    animate={{ x: 0, opacity: 1 }}
                    transition={{ delay: index * 0.1 }}
                    className="flex items-start gap-3 pb-3 border-b border-white/5 last:border-0 last:pb-0"
                  >
                    <div className="w-8 h-8 rounded-lg bg-cyan-500/20 flex items-center justify-center flex-shrink-0">
                      <Zap className="w-4 h-4 text-cyan-400" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-white truncate">{exp.title || exp.name || 'Laboratory Simulation'}</p>
                      <p className="text-xs text-gray-500">{exp.status === 'completed' ? 'Completed • Earned XP' : 'Analyzed run'}</p>
                    </div>
                  </motion.div>
                ))
              ) : (
                <div className="py-4 text-center text-xs text-gray-500">
                  No experiment runs recorded yet. Complete experiments to log activity!
                </div>
              )}
            </div>
          </motion.div>
        </>
      ) : (
        <>
          {/* Achievements Grid */}
          <div className="bg-white/5 rounded-xl p-4 border border-white/10">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <Trophy className="w-5 h-5 text-yellow-500" />
                <span className="text-white font-semibold">Achievements</span>
              </div>
              <span className="text-gray-400 text-sm">
                {achievements.filter((a) => a.unlocked).length}/{achievements.length}
              </span>
            </div>

            <div className="grid grid-cols-1 gap-3">
              {achievements.map((achievement) => {
                const IconComponent = achievement.icon;
                return (
                  <motion.div
                    key={achievement.id}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    className={`p-3 rounded-xl border flex items-center gap-3.5 transition-all ${
                      achievement.unlocked
                        ? 'bg-white/5 border-white/10 hover:border-cyan-500/30'
                        : 'bg-white/[0.01] border-white/5 opacity-50'
                    }`}
                  >
                    <div
                      className={`w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0 ${
                        achievement.unlocked
                          ? `bg-gradient-to-r ${achievement.color} text-white shadow-lg`
                          : 'bg-white/5 text-gray-500'
                      }`}
                    >
                      <IconComponent className="w-5 h-5" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between">
                        <h4 className="text-white font-semibold text-xs truncate">{achievement.name}</h4>
                        <span className="text-[10px] font-bold text-cyan-400">+{achievement.xp} XP</span>
                      </div>
                      <p className="text-[11px] text-gray-400 mt-0.5">{achievement.description}</p>
                    </div>
                    {achievement.unlocked ? (
                      <CheckCircle2 className="w-4 h-4 text-green-400 flex-shrink-0" />
                    ) : (
                      <Lock className="w-4 h-4 text-gray-500 flex-shrink-0" />
                    )}
                  </motion.div>
                );
              })}
            </div>
          </div>

          {/* Leaderboard Preview */}
          <div className="bg-white/5 rounded-xl p-4 border border-white/10">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <Award className="w-5 h-5 text-cyan-400" />
                <span className="text-white font-semibold">Global Leaderboard</span>
              </div>
            </div>

            <div className="space-y-2">
              {leaderboard.length > 0 ? (
                leaderboard.map((user, index) => (
                  <motion.div
                    key={user.id}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: index * 0.05 }}
                    className="flex items-center gap-3 p-2 rounded-lg hover:bg-white/5 transition-colors"
                  >
                    <div
                      className={`w-7 h-7 rounded-full flex items-center justify-center font-bold text-xs ${
                        user.rank === 1
                          ? 'bg-yellow-500 text-yellow-900'
                          : user.rank === 2
                          ? 'bg-gray-300 text-gray-700'
                          : user.rank === 3
                          ? 'bg-amber-700 text-amber-100'
                          : 'bg-white/5 text-gray-400'
                      }`}
                    >
                      {user.rank}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-white font-medium text-xs truncate">{user.name}</p>
                      <p className="text-[10px] text-gray-400">{user.xp.toLocaleString()} XP</p>
                    </div>
                  </motion.div>
                ))
              ) : (
                <div className="py-4 text-center text-xs text-gray-500">
                  Leaderboard rankings will appear as students complete laboratories.
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
