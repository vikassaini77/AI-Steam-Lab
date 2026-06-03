import { motion } from 'framer-motion';
import { useState } from 'react';
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

interface GamificationPanelProps {
  view: 'insights' | 'progress';
}

const achievements = [
  {
    id: 1,
    name: 'First Steps',
    description: 'Complete your first experiment',
    icon: Star,
    unlocked: true,
    xp: 100,
    color: 'from-yellow-500 to-orange-500',
  },
  {
    id: 2,
    name: 'Physics Pro',
    description: 'Analyze 10 physics experiments',
    icon: Target,
    unlocked: true,
    xp: 250,
    color: 'from-cyan-500 to-blue-500',
  },
  {
    id: 3,
    name: 'Pendulum Master',
    description: 'Complete all pendulum challenges',
    icon: Award,
    unlocked: false,
    xp: 500,
    color: 'from-violet-500 to-purple-500',
  },
  {
    id: 4,
    name: 'AI Collaborator',
    description: 'Have 50 conversations with AI tutor',
    icon: Trophy,
    unlocked: false,
    xp: 300,
    color: 'from-green-500 to-emerald-500',
  },
  {
    id: 5,
    name: 'Week Warrior',
    description: 'Maintain a 7-day streak',
    icon: Flame,
    unlocked: true,
    xp: 200,
    color: 'from-orange-500 to-red-500',
  },
];

const streakData = [
  { day: 'Mon', completed: true },
  { day: 'Tue', completed: true },
  { day: 'Wed', completed: true },
  { day: 'Thu', completed: true },
  { day: 'Fri', completed: true },
  { day: 'Sat', completed: false },
  { day: 'Sun', completed: false },
];

const recentActivity = [
  { type: 'xp', text: 'Earned 150 XP for pendulum analysis', time: '2m ago' },
  { type: 'achievement', text: 'Unlocked "Week Warrior" badge', time: '1h ago' },
  { type: 'experiment', text: 'Completed Newton\'s Laws experiment', time: '3h ago' },
  { type: 'question', text: 'Asked AI tutor 5 questions', time: '5h ago' },
];

export default function GamificationPanel({ view }: GamificationPanelProps) {
  const [currentXP] = useState(2450);
  const [level] = useState(12);
  const [streak] = useState(5);
  const xpForNextLevel = 3000;
  const progress = (currentXP / xpForNextLevel) * 100;

  return (
    <div className="p-4 space-y-4">
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
              <p className="text-gray-400 text-sm">Junior Scientist</p>
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
          {(xpForNextLevel - currentXP).toLocaleString()} XP to Level {level + 1}
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
              <span className="text-orange-400 font-bold">{streak} days</span>
            </div>
            <div className="flex justify-between">
              {streakData.map((day, index) => (
                <motion.div
                  key={index}
                  className="text-center"
                  initial={{ scale: 0.8, opacity: 0 }}
                  animate={{ scale: 1, opacity: 1 }}
                  transition={{ delay: index * 0.1 }}
                >
                  <div
                    className={`w-10 h-10 rounded-lg flex items-center justify-center mb-1 ${
                      day.completed
                        ? 'bg-gradient-to-r from-orange-500 to-red-500'
                        : 'bg-white/5 border border-white/10'
                    }`}
                  >
                    {day.completed ? (
                      <Flame className="w-5 h-5 text-white" />
                    ) : (
                      <span className="text-xs text-gray-500">{index + 1}</span>
                    )}
                  </div>
                  <span className="text-xs text-gray-500">{day.day}</span>
                </motion.div>
              ))}
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
              {recentActivity.map((activity, index) => (
                <motion.div
                  key={index}
                  initial={{ x: -10, opacity: 0 }}
                  animate={{ x: 0, opacity: 1 }}
                  transition={{ delay: index * 0.1 }}
                  className="flex items-start gap-3 pb-3 border-b border-white/5 last:border-0 last:pb-0"
                >
                  <div
                    className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 ${
                      activity.type === 'xp'
                        ? 'bg-cyan-500/20'
                        : activity.type === 'achievement'
                        ? 'bg-yellow-500/20'
                        : activity.type === 'experiment'
                        ? 'bg-green-500/20'
                        : 'bg-violet-500/20'
                    }`}
                  >
                    {activity.type === 'xp' ? (
                      <Zap className="w-4 h-4 text-cyan-400" />
                    ) : activity.type === 'achievement' ? (
                      <Trophy className="w-4 h-4 text-yellow-400" />
                    ) : activity.type === 'experiment' ? (
                      <Target className="w-4 h-4 text-green-400" />
                    ) : (
                      <Star className="w-4 h-4 text-violet-400" />
                    )}
                  </div>
                  <div className="flex-1">
                    <p className="text-sm text-white">{activity.text}</p>
                    <p className="text-xs text-gray-500">{activity.time}</p>
                  </div>
                </motion.div>
              ))}
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
              {achievements.map((achievement, index) => (
                <motion.div
                  key={achievement.id}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: index * 0.1 }}
                  whileHover={{ scale: 1.02 }}
                  className={`relative p-3 rounded-xl border ${
                    achievement.unlocked
                      ? 'bg-gradient-to-r from-white/10 to-white/5 border-white/20'
                      : 'bg-white/5 border-white/10 opacity-60'
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <div
                      className={`w-12 h-12 rounded-xl flex items-center justify-center ${
                        achievement.unlocked
                          ? `bg-gradient-to-r ${achievement.color}`
                          : 'bg-gray-700'
                      }`}
                    >
                      {achievement.unlocked ? (
                        <achievement.icon className="w-6 h-6 text-white" />
                      ) : (
                        <Lock className="w-6 h-6 text-gray-500" />
                      )}
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <h4 className="text-white font-semibold">{achievement.name}</h4>
                        {achievement.unlocked && (
                          <CheckCircle2 className="w-4 h-4 text-green-400" />
                        )}
                      </div>
                      <p className="text-xs text-gray-400">{achievement.description}</p>
                      <p className="text-xs text-cyan-400 mt-1">+{achievement.xp} XP</p>
                    </div>
                  </div>
                </motion.div>
              ))}
            </div>
          </div>

          {/* Leaderboard Preview */}
          <div className="bg-white/5 rounded-xl p-4 border border-white/10">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <Award className="w-5 h-5 text-cyan-400" />
                <span className="text-white font-semibold">Weekly Leaderboard</span>
              </div>
              <span className="text-gray-400 text-sm">Your rank: #47</span>
            </div>

            <div className="space-y-2">
              {[
                { rank: 1, name: 'Alex K.', xp: 15420, avatar: 'A' },
                { rank: 2, name: 'Sarah M.', xp: 14850, avatar: 'S' },
                { rank: 3, name: 'James L.', xp: 13890, avatar: 'J' },
              ].map((user, index) => (
                <motion.div
                  key={user.rank}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ delay: index * 0.1 }}
                  className="flex items-center gap-3 p-2 rounded-lg hover:bg-white/5 transition-colors"
                >
                  <div
                    className={`w-8 h-8 rounded-full flex items-center justify-center font-bold ${
                      user.rank === 1
                        ? 'bg-yellow-500 text-yellow-900'
                        : user.rank === 2
                        ? 'bg-gray-300 text-gray-700'
                        : 'bg-orange-600 text-orange-100'
                    }`}
                  >
                    {user.rank}
                  </div>
                  <div className="w-8 h-8 rounded-full bg-gradient-to-r from-cyan-500 to-blue-500 flex items-center justify-center text-white text-sm font-semibold">
                    {user.avatar}
                  </div>
                  <div className="flex-1">
                    <p className="text-white font-medium">{user.name}</p>
                    <p className="text-xs text-gray-400">{user.xp.toLocaleString()} XP</p>
                  </div>
                </motion.div>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
