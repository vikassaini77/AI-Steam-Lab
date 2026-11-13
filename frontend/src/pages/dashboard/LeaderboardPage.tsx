import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Trophy, Medal, Target, Crown, Sparkles } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { UserAvatar } from '../../components/dashboard/DashboardLayout';
import { getApiBaseUrl } from '../../lib/api';

interface LeaderboardEntry {
  id: string | number;
  user_id: string;
  name: string;
  rank: number;
  xp: number;
  avatar: string | null;
  badges: number;
}

export default function LeaderboardPage() {
  const navigate = useNavigate();
  const [leaderboard, setLeaderboard] = useState<LeaderboardEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [currentUserId, setCurrentUserId] = useState<string | null>(null);

  useEffect(() => {
    // Get current user id from session
    try {
      const stored = localStorage.getItem('neurolab_session');
      if (stored) {
        const session = JSON.parse(stored);
        if (session?.user?.id) {
          setCurrentUserId(session.user.id);
        }
      }
    } catch (e) {
      console.error(e);
    }

    const fetchLeaderboard = async () => {
      try {
        const API_URL = getApiBaseUrl();
        const response = await fetch(`${API_URL}/api/gamification/leaderboard`);
        if (response.ok) {
          const data = await response.json();
          setLeaderboard(Array.isArray(data) ? data : []);
        }
      } catch (error) {
        console.error("Failed to fetch leaderboard:", error);
      } finally {
        setLoading(false);
      }
    };
    fetchLeaderboard();
  }, []);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-gray-400">
        <div className="w-8 h-8 border-2 border-cyan-500 border-t-transparent rounded-full animate-spin mb-4" />
        <p className="text-sm">Loading Leaderboard...</p>
      </div>
    );
  }

  if (leaderboard.length === 0) {
    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-2xl font-bold text-white flex items-center gap-2">
            <Trophy className="w-6 h-6 text-yellow-400" />
            Global Leaderboard
          </h2>
          <p className="text-gray-400 text-sm mt-1">Compete with STEM students worldwide</p>
        </div>

        <div className="bg-[#0d0d20] border border-white/5 rounded-2xl p-12 text-center flex flex-col items-center justify-center max-w-lg mx-auto my-12">
          <div className="w-16 h-16 rounded-full bg-yellow-500/10 border border-yellow-500/20 flex items-center justify-center text-yellow-400 mb-4">
            <Crown className="w-8 h-8" />
          </div>
          <h3 className="text-xl font-bold text-white mb-2">Be the First on the Leaderboard!</h3>
          <p className="text-gray-400 text-sm mb-6 leading-relaxed">
            No student rankings have been established yet. Complete laboratory simulations, solve challenge quests, and claim your place at the top.
          </p>
          <button
            onClick={() => navigate('/dashboard/experiments')}
            className="px-6 py-2.5 rounded-xl bg-gradient-to-r from-cyan-500 to-indigo-600 text-white font-semibold text-sm hover:from-cyan-400 hover:to-indigo-500 transition-all shadow-lg shadow-cyan-500/25 flex items-center gap-2"
          >
            <Sparkles className="w-4 h-4" />
            Start an Experiment
          </button>
        </div>
      </div>
    );
  }

  const rank1 = leaderboard[0];
  const rank2 = leaderboard.length > 1 ? leaderboard[1] : null;
  const rank3 = leaderboard.length > 2 ? leaderboard[2] : null;

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

      {/* Top Podium - only renders actual users */}
      <div className="flex flex-col md:flex-row justify-center items-end gap-6 my-12 min-h-64">
        {/* Rank 2 */}
        {rank2 && (
          <motion.div 
            initial={{ opacity: 0, y: 50 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}
            className="flex flex-col items-center flex-1 order-2 md:order-1"
          >
            <div className="w-16 h-16 rounded-full border-4 border-gray-300 bg-gradient-to-tr from-gray-300 to-gray-500 flex items-center justify-center text-xl font-bold text-white shadow-lg shadow-gray-500/20 z-10 relative overflow-hidden">
              <Medal className="absolute -top-6 text-gray-300 w-8 h-8" />
              {rank2.user_id === currentUserId && currentUserId ? <UserAvatar className="w-full h-full" /> : (rank2.name ? rank2.name.substring(0, 2).toUpperCase() : 'U')}
            </div>
            <div className="bg-[#12122a] w-full md:w-32 h-32 mt-4 rounded-t-xl border-t border-x border-gray-400/30 flex flex-col items-center justify-center relative overflow-hidden px-2">
              <div className="absolute inset-0 bg-gradient-to-t from-gray-400/5 to-transparent pointer-events-none" />
              <span className="text-2xl font-black text-gray-300">#2</span>
              <p className="text-xs text-gray-300 font-semibold truncate max-w-[100px] mt-0.5">{rank2.name}</p>
              <span className="text-xs text-gray-400 font-semibold mt-1">{rank2.xp.toLocaleString()} XP</span>
            </div>
          </motion.div>
        )}

        {/* Rank 1 */}
        {rank1 && (
          <motion.div 
            initial={{ opacity: 0, y: 50 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}
            className="flex flex-col items-center flex-1 order-1 md:order-2 z-20"
          >
            <div className="w-20 h-20 rounded-full border-4 border-yellow-400 bg-gradient-to-tr from-yellow-400 to-amber-600 flex items-center justify-center text-2xl font-bold text-white shadow-2xl shadow-yellow-500/40 z-10 relative overflow-hidden">
              <Crown className="absolute -top-8 text-yellow-400 w-10 h-10 drop-shadow-[0_0_10px_rgba(250,204,21,0.8)]" />
              {rank1.user_id === currentUserId && currentUserId ? <UserAvatar className="w-full h-full" /> : (rank1.name ? rank1.name.substring(0, 2).toUpperCase() : 'U')}
            </div>
            <div className="bg-gradient-to-t from-yellow-500/10 to-[#1a1a3a] w-full md:w-36 h-40 mt-4 rounded-t-xl border-t-2 border-x-2 border-yellow-500/50 flex flex-col items-center justify-center relative overflow-hidden px-2">
              <div className="absolute inset-0 bg-yellow-400/5 pointer-events-none" />
              <span className="text-4xl font-black text-yellow-400 drop-shadow-md">#1</span>
              <p className="text-xs text-yellow-200 font-bold truncate max-w-[120px] mt-0.5">{rank1.name}</p>
              <span className="text-sm text-yellow-200 font-bold mt-1">{rank1.xp.toLocaleString()} XP</span>
            </div>
          </motion.div>
        )}

        {/* Rank 3 */}
        {rank3 && (
          <motion.div 
            initial={{ opacity: 0, y: 50 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 }}
            className="flex flex-col items-center flex-1 order-3 md:order-3"
          >
            <div className="w-16 h-16 rounded-full border-4 border-amber-700 bg-gradient-to-tr from-amber-600 to-amber-800 flex items-center justify-center text-xl font-bold text-white shadow-lg shadow-amber-700/20 z-10 relative overflow-hidden">
              <Medal className="absolute -top-6 text-amber-600 w-8 h-8" />
              {rank3.user_id === currentUserId && currentUserId ? <UserAvatar className="w-full h-full" /> : (rank3.name ? rank3.name.substring(0, 2).toUpperCase() : 'U')}
            </div>
            <div className="bg-[#12122a] w-full md:w-32 h-24 mt-4 rounded-t-xl border-t border-x border-amber-700/30 flex flex-col items-center justify-center relative overflow-hidden px-2">
              <div className="absolute inset-0 bg-gradient-to-t from-amber-600/5 to-transparent pointer-events-none" />
              <span className="text-2xl font-black text-amber-600">#3</span>
              <p className="text-xs text-gray-300 font-semibold truncate max-w-[100px] mt-0.5">{rank3.name}</p>
              <span className="text-xs text-gray-400 font-semibold mt-1">{rank3.xp.toLocaleString()} XP</span>
            </div>
          </motion.div>
        )}
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
          {leaderboard.map((user, idx) => (
            <motion.div
              key={user.id}
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: idx * 0.05 }}
              className={`grid grid-cols-12 gap-4 p-4 items-center transition-colors hover:bg-white/[0.02] ${
                user.user_id === currentUserId && currentUserId ? 'bg-cyan-500/10 border-l-4 border-cyan-500' : ''
              }`}
            >
              <div className="col-span-2 text-center font-bold text-gray-400">
                {user.rank}
              </div>
              <div className="col-span-5 flex items-center gap-3">
                <div className="w-8 h-8 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center text-xs font-bold text-white flex-shrink-0 overflow-hidden">
                  {user.user_id === currentUserId && currentUserId ? <UserAvatar className="w-full h-full" /> : (user.name ? user.name.substring(0, 2).toUpperCase() : 'U')}
                </div>
                <span className={`font-semibold text-sm ${user.user_id === currentUserId && currentUserId ? 'text-cyan-400' : 'text-gray-200'}`}>
                  {user.user_id === currentUserId && currentUserId ? 'You' : user.name}
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
