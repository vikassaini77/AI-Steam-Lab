import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Trophy, Medal, Star, Target, Crown } from 'lucide-react';
import { UserAvatar } from '../../components/dashboard/DashboardLayout';

const mockLeaderboard = [
  { id: 1, name: 'Sarah Chen', rank: 1, xp: 14500, avatar: null, badges: 42 },
  { id: 2, name: 'David Park', rank: 2, xp: 13200, avatar: null, badges: 38 },
  { id: 3, name: 'Elena Rodriguez', rank: 3, xp: 12850, avatar: null, badges: 35 },
  { id: 4, name: 'James Wilson', rank: 4, xp: 11400, avatar: null, badges: 31 },
  { id: 5, name: 'Aisha Patel', rank: 5, xp: 10900, avatar: null, badges: 29 },
  { id: 6, name: 'Marcus Johnson', rank: 6, xp: 9800, avatar: null, badges: 26 },
  { id: 7, name: 'Yuki Tanaka', rank: 7, xp: 9200, avatar: null, badges: 24 },
  { id: 8, name: 'Current User', rank: 8, xp: 8750, avatar: null, badges: 21 },
  { id: 9, name: 'Liam Smith', rank: 9, xp: 8100, avatar: null, badges: 19 },
  { id: 10, name: 'Emma Davis', rank: 10, xp: 7600, avatar: null, badges: 15 },
];

export default function LeaderboardPage() {
  const [currentUserRank, setCurrentUserRank] = useState(8);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-white flex items-center gap-2">
            <Trophy className="w-6 h-6 text-yellow-400" />
            Global Leaderboard
          </h2>
          <p className="text-gray-400 text-sm mt-1">Compete with STEM students worldwide</p>
        </div>
      </div>

      {/* Top 3 Podium */}
      <div className="flex flex-col md:flex-row justify-center items-end gap-6 my-12 h-64">
        {/* Rank 2 */}
        <motion.div 
          initial={{ opacity: 0, y: 50 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}
          className="flex flex-col items-center flex-1 order-2 md:order-1"
        >
          <div className="w-16 h-16 rounded-full border-4 border-gray-300 bg-gradient-to-tr from-gray-300 to-gray-500 flex items-center justify-center text-xl font-bold text-white shadow-lg shadow-gray-500/20 z-10 relative">
            <Medal className="absolute -top-6 text-gray-300 w-8 h-8" />
            DP
          </div>
          <div className="bg-[#12122a] w-full md:w-32 h-32 mt-4 rounded-t-xl border-t border-x border-gray-400/30 flex flex-col items-center justify-center relative overflow-hidden">
            <div className="absolute inset-0 bg-gradient-to-t from-gray-400/5 to-transparent pointer-events-none" />
            <span className="text-2xl font-black text-gray-300">#2</span>
            <span className="text-xs text-gray-400 font-semibold mt-1">13,200 XP</span>
          </div>
        </motion.div>

        {/* Rank 1 */}
        <motion.div 
          initial={{ opacity: 0, y: 50 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}
          className="flex flex-col items-center flex-1 order-1 md:order-2 z-20"
        >
          <div className="w-20 h-20 rounded-full border-4 border-yellow-400 bg-gradient-to-tr from-yellow-400 to-amber-600 flex items-center justify-center text-2xl font-bold text-white shadow-2xl shadow-yellow-500/40 z-10 relative">
            <Crown className="absolute -top-8 text-yellow-400 w-10 h-10 drop-shadow-[0_0_10px_rgba(250,204,21,0.8)]" />
            SC
          </div>
          <div className="bg-gradient-to-t from-yellow-500/10 to-[#1a1a3a] w-full md:w-36 h-40 mt-4 rounded-t-xl border-t-2 border-x-2 border-yellow-500/50 flex flex-col items-center justify-center relative overflow-hidden">
            <div className="absolute inset-0 bg-yellow-400/5 pointer-events-none" />
            <span className="text-4xl font-black text-yellow-400 drop-shadow-md">#1</span>
            <span className="text-sm text-yellow-200 font-bold mt-1">14,500 XP</span>
          </div>
        </motion.div>

        {/* Rank 3 */}
        <motion.div 
          initial={{ opacity: 0, y: 50 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 }}
          className="flex flex-col items-center flex-1 order-3 md:order-3"
        >
          <div className="w-16 h-16 rounded-full border-4 border-amber-700 bg-gradient-to-tr from-amber-600 to-amber-800 flex items-center justify-center text-xl font-bold text-white shadow-lg shadow-amber-700/20 z-10 relative">
            <Medal className="absolute -top-6 text-amber-600 w-8 h-8" />
            ER
          </div>
          <div className="bg-[#12122a] w-full md:w-32 h-24 mt-4 rounded-t-xl border-t border-x border-amber-700/30 flex flex-col items-center justify-center relative overflow-hidden">
            <div className="absolute inset-0 bg-gradient-to-t from-amber-600/5 to-transparent pointer-events-none" />
            <span className="text-2xl font-black text-amber-600">#3</span>
            <span className="text-xs text-gray-400 font-semibold mt-1">12,850 XP</span>
          </div>
        </motion.div>
      </div>

      {/* List */}
      <div className="bg-[#0d0d20] border border-white/5 rounded-2xl overflow-hidden shadow-xl">
        <div className="grid grid-cols-12 gap-4 p-4 border-b border-white/5 bg-white/[0.02] text-xs font-semibold text-gray-400 uppercase tracking-wider">
          <div className="col-span-2 text-center">Rank</div>
          <div className="col-span-5">Scientist</div>
          <div className="col-span-2 text-center">Badges</div>
          <div className="col-span-3 text-right">Total XP</div>
        </div>
        
        <div className="divide-y divide-white/5">
          {mockLeaderboard.map((user, idx) => (
            <motion.div
              key={user.id}
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: idx * 0.05 }}
              className={`grid grid-cols-12 gap-4 p-4 items-center transition-colors hover:bg-white/[0.02] ${
                user.name === 'Current User' ? 'bg-cyan-500/10 border-l-4 border-cyan-500' : ''
              }`}
            >
              <div className="col-span-2 text-center font-bold text-gray-400">
                {user.rank}
              </div>
              <div className="col-span-5 flex items-center gap-3">
                <div className="w-8 h-8 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center text-xs font-bold text-white flex-shrink-0">
                  {user.name === 'Current User' ? <UserAvatar className="w-8 h-8 rounded-full" /> : user.name.substring(0, 2).toUpperCase()}
                </div>
                <span className={`font-semibold text-sm ${user.name === 'Current User' ? 'text-cyan-400' : 'text-gray-200'}`}>
                  {user.name}
                </span>
              </div>
              <div className="col-span-2 flex items-center justify-center gap-1.5 text-gray-400">
                <Target className="w-3.5 h-3.5" />
                <span className="text-sm font-medium">{user.badges}</span>
              </div>
              <div className="col-span-3 flex items-center justify-end gap-1.5 text-right">
                <span className="font-bold text-sm text-white">{user.xp.toLocaleString()}</span>
                <span className="text-xs font-bold text-cyan-500">XP</span>
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </div>
  );
}
