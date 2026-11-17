import { useState, useEffect, useMemo } from "react";
import { motion } from "framer-motion";
import { Zap, Flame, Atom, Lock, Target, Brain, Star, Trophy, Sparkles } from "lucide-react";
import { UserAvatar } from "./DashboardLayout";
import { getApiBaseUrl, getAuthHeaders } from "../../lib/api";
import { useUserStore } from "../../store/useUserStore";

interface LeaderboardUser {
  user_id?: string;
  rank: number;
  xp: number;
  display_name?: string;
  name?: string;
  username?: string;
  avatar_url?: string;
  badge?: string;
  level?: number;
  isCurrentUser?: boolean;
  isUser?: boolean;
  streak?: string | number;
  [key: string]: unknown;
}

interface UserExperimentRecord {
  id?: string;
  experiment_type?: string;
  type?: string;
  created_at?: string;
  timestamp?: number;
}

interface BadgeDef {
  id: string;
  title: string;
  desc: string;
  tag: 'Common' | 'Uncommon' | 'Rare' | 'Epic';
  xpReward: number;
  icon: React.ComponentType<{ className?: string }>;
  evaluator: (history: UserExperimentRecord[], xp: number, level: number) => {
    unlocked: boolean;
    progress: number;
    maxProgress: number;
    unlockedDate?: string;
  };
}

const safeExpType = (h?: UserExperimentRecord | null): string => {
  if (!h) return '';
  const raw = h.experiment_type ?? h.type ?? '';
  return String(raw).toLowerCase().trim();
};

const formatUnlockDate = (dateVal?: string | number): string => {
  if (!dateVal) return "Recently unlocked";
  try {
    const d = typeof dateVal === 'number' ? new Date(dateVal * 1000) : new Date(dateVal);
    if (isNaN(d.getTime())) return "Recently unlocked";
    return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
  } catch {
    return "Recently unlocked";
  }
};

const BADGE_CATALOG: BadgeDef[] = [
  {
    id: "first_steps",
    title: "First Steps",
    desc: "Complete your first scientific laboratory experiment",
    tag: "Common",
    xpReward: 50,
    icon: Target,
    evaluator: (history) => {
      const valid = Array.isArray(history) ? history.filter(Boolean) : [];
      const unlocked = valid.length >= 1;
      const firstExp = valid[0];
      const dateStr = firstExp?.created_at ? formatUnlockDate(firstExp.created_at) : (unlocked ? "Recently unlocked" : undefined);
      return {
        unlocked,
        progress: Math.min(1, valid.length),
        maxProgress: 1,
        unlockedDate: dateStr,
      };
    },
  },
  {
    id: "gravity_pioneer",
    title: "Gravity Pioneer",
    desc: "Perform a Pendulum or Free Fall experiment verifying acceleration g",
    tag: "Common",
    xpReward: 100,
    icon: Atom,
    evaluator: (history) => {
      const valid = Array.isArray(history) ? history.filter(Boolean) : [];
      const match = valid.find(h => {
        const t = safeExpType(h);
        return t.includes('pendulum') || t.includes('free_fall');
      });
      const unlocked = !!match;
      return {
        unlocked,
        progress: unlocked ? 1 : 0,
        maxProgress: 1,
        unlockedDate: match?.created_at ? formatUnlockDate(match.created_at) : (unlocked ? "Recently unlocked" : undefined),
      };
    },
  },
  {
    id: "curious_mind",
    title: "Curious Mind",
    desc: "Complete 3 distinct laboratory experiments across STEM topics",
    tag: "Uncommon",
    xpReward: 150,
    icon: Brain,
    evaluator: (history) => {
      const valid = Array.isArray(history) ? history.filter(Boolean) : [];
      const count = valid.length;
      const unlocked = count >= 3;
      const thirdExp = valid[2];
      return {
        unlocked,
        progress: Math.min(3, count),
        maxProgress: 3,
        unlockedDate: thirdExp?.created_at ? formatUnlockDate(thirdExp.created_at) : (unlocked ? "Recently unlocked" : undefined),
      };
    },
  },
  {
    id: "harmonic_explorer",
    title: "Harmonic Explorer",
    desc: "Run a Simple Harmonic Motion or Circular Motion investigation",
    tag: "Uncommon",
    xpReward: 200,
    icon: Flame,
    evaluator: (history) => {
      const valid = Array.isArray(history) ? history.filter(Boolean) : [];
      const match = valid.find(h => {
        const t = safeExpType(h);
        return t.includes('harmonic') || t.includes('circular');
      });
      const unlocked = !!match;
      return {
        unlocked,
        progress: unlocked ? 1 : 0,
        maxProgress: 1,
        unlockedDate: match?.created_at ? formatUnlockDate(match.created_at) : (unlocked ? "Recently unlocked" : undefined),
      };
    },
  },
  {
    id: "momentum_champion",
    title: "Momentum Champion",
    desc: "Verify conservation of linear momentum in collision experiments",
    tag: "Rare",
    xpReward: 250,
    icon: Zap,
    evaluator: (history) => {
      const valid = Array.isArray(history) ? history.filter(Boolean) : [];
      const match = valid.find(h => {
        const t = safeExpType(h);
        return t.includes('collision');
      });
      const unlocked = !!match;
      return {
        unlocked,
        progress: unlocked ? 1 : 0,
        maxProgress: 1,
        unlockedDate: match?.created_at ? formatUnlockDate(match.created_at) : (unlocked ? "Recently unlocked" : undefined),
      };
    },
  },
  {
    id: "xp_trailblazer",
    title: "XP Trailblazer",
    desc: "Accumulate at least 500 total XP across STEM experiments",
    tag: "Rare",
    xpReward: 300,
    icon: Star,
    evaluator: (_history, xp) => {
      const val = Number(xp) || 0;
      const unlocked = val >= 500;
      return {
        unlocked,
        progress: Math.min(500, Math.max(0, val)),
        maxProgress: 500,
        unlockedDate: unlocked ? "Achieved" : undefined,
      };
    },
  },
  {
    id: "laboratory_scholar",
    title: "Laboratory Scholar",
    desc: "Advance to Level 3 or higher in the NeuroLab AI curriculum",
    tag: "Rare",
    xpReward: 350,
    icon: Sparkles,
    evaluator: (_history, _xp, level) => {
      const val = Number(level) || 1;
      const unlocked = val >= 3;
      return {
        unlocked,
        progress: Math.min(3, Math.max(1, val)),
        maxProgress: 3,
        unlockedDate: unlocked ? "Achieved" : undefined,
      };
    },
  },
  {
    id: "grand_physicist",
    title: "Grand Physicist",
    desc: "Master all 6 interactive physics experiment engines",
    tag: "Epic",
    xpReward: 500,
    icon: Trophy,
    evaluator: (history) => {
      const valid = Array.isArray(history) ? history.filter(Boolean) : [];
      const uniqueTypes = new Set(
        valid.map(safeExpType).filter(Boolean)
      );
      const unlocked = uniqueTypes.size >= 6;
      return {
        unlocked,
        progress: Math.min(6, uniqueTypes.size),
        maxProgress: 6,
        unlockedDate: unlocked ? "Achieved" : undefined,
      };
    },
  },
];

function AchievementsPage() {
  const [activeTab, setActiveTab] = useState<'badges' | 'leaderboard'>('badges');
  const [history, setHistory] = useState<UserExperimentRecord[]>([]);
  const [searchQuery, setSearchQuery] = useState('');

  const { xp: storedXp, level: storedLevel } = useUserStore();
  const currentXp = Math.max(0, storedXp || 0);
  const currentLevel = Math.max(1, storedLevel || Math.floor(currentXp / 1000) + 1);

  // Leaderboard states
  const [leaderboardUsers, setLeaderboardUsers] = useState<LeaderboardUser[]>([]);
  const [loadingLeaderboard, setLoadingLeaderboard] = useState(true);
  const [currentUserId, setCurrentUserId] = useState<string | null>(null);

  // Load user session & real experiment history
  useEffect(() => {
    let isMounted = true;
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

    const fetchHistory = async () => {
      // 1. Read locally cached experiments from browser storage
      const localList: UserExperimentRecord[] = [];
      try {
        const cached = localStorage.getItem('local_stem_db');
        if (cached) {
          const store = JSON.parse(cached);
          if (Array.isArray(store?.experiments)) {
            for (const item of store.experiments) {
              if (item && typeof item === 'object') {
                localList.push({
                  id: item.id || `local_${Math.random().toString(36).substr(2, 9)}`,
                  experiment_type: item.experimentType || item.experiment_type || item.type,
                  type: item.type || item.experimentType || item.experiment_type,
                  created_at: item.date || item.created_at,
                });
              }
            }
          }
        }
      } catch (localErr) {
        console.warn('Failed reading local experiment database for achievements:', localErr);
      }

      // 2. Query cloud server
      let serverList: UserExperimentRecord[] = [];
      try {
        const apiBase = getApiBaseUrl();
        const headers = await getAuthHeaders();
        const res = await fetch(`${apiBase}/api/experiments/history`, { headers });
        if (res.ok) {
          const data = await res.json();
          const rawArray = Array.isArray(data) ? data : Array.isArray(data?.history) ? data.history : [];
          serverList = (rawArray as UserExperimentRecord[]).filter(Boolean).map((item) => ({
            id: item.id,
            experiment_type: item.experiment_type || item.type,
            type: item.type || item.experiment_type,
            created_at: item.created_at || (item.timestamp ? new Date(item.timestamp * 1000).toISOString() : undefined),
          }));
        }
      } catch (err) {
        console.warn("Failed to fetch experiment history for achievements:", err);
      }

      // 3. Deduplicate
      const idMap = new Map<string, UserExperimentRecord>();
      localList.forEach((exp, idx) => {
        idMap.set(exp.id || `local_${idx}`, exp);
      });
      serverList.forEach((exp, idx) => {
        idMap.set(exp.id || `server_${idx}`, exp);
      });

      if (isMounted) {
        setHistory(Array.from(idMap.values()));
      }
    };

    fetchHistory();

    const handleGlobalSearch = (e: Event) => {
      setSearchQuery((e as CustomEvent).detail || '');
    };
    window.addEventListener('dashboard-search', handleGlobalSearch);
    return () => {
      isMounted = false;
      window.removeEventListener('dashboard-search', handleGlobalSearch);
    };
  }, []);

  // Fetch real leaderboard
  useEffect(() => {
    let isMounted = true;
    const fetchLeaderboard = async () => {
      try {
        setLoadingLeaderboard(true);
        const API_URL = getApiBaseUrl();
        const response = await fetch(`${API_URL}/api/gamification/leaderboard`);
        if (response.ok) {
          const data = await response.json();
          const rawList: LeaderboardUser[] = Array.isArray(data) ? data : Array.isArray(data?.leaderboard) ? data.leaderboard : [];
          const enrichedData = rawList.filter(Boolean).map((user: LeaderboardUser) => {
            const userXp = Number(user.xp) || 0;
            const userLvl = Math.max(1, Math.floor(userXp / 1000) + (userXp > 0 ? 1 : 0));
            let badgeStr = '🔬 Lab Novice';
            if (user.rank === 1) badgeStr = '🏆 Top Scholar';
            else if (user.rank === 2) badgeStr = '⭐ Gravity Sage';
            else if (user.rank === 3) badgeStr = '⚡ Electro Pro';
            else if (user.rank <= 10) badgeStr = '🔥 Rising Star';
            
            return {
              ...user,
              xp: userXp,
              level: user.level || userLvl,
              badge: user.badge || badgeStr,
              isUser: user.user_id === currentUserId
            };
          });
          if (isMounted) {
            setLeaderboardUsers(enrichedData);
          }
        }
      } catch (error) {
        console.error("Failed to fetch leaderboard:", error);
      } finally {
        if (isMounted) setLoadingLeaderboard(false);
      }
    };
    
    if (activeTab === 'leaderboard') {
      fetchLeaderboard();
    }
    return () => { isMounted = false; };
  }, [activeTab, currentUserId]);

  // Compute authentic unlocked vs locked badges
  const { unlockedBadges, lockedBadges, totalUnlockedXp, rarestBadgeTitle } = useMemo(() => {
    const unlocked: Array<BadgeDef & { date?: string }> = [];
    const locked: Array<BadgeDef & { progress: number; maxProgress: number }> = [];
    let xpSum = 0;
    let rarest: string = "Keep Exploring!";

    for (const b of BADGE_CATALOG) {
      const res = b.evaluator(history, currentXp, currentLevel);
      if (res.unlocked) {
        unlocked.push({ ...b, date: res.unlockedDate || "Unlocked" });
        xpSum += b.xpReward;
        rarest = b.title;
      } else {
        locked.push({ ...b, progress: res.progress, maxProgress: res.maxProgress });
      }
    }

    return {
      unlockedBadges: unlocked,
      lockedBadges: locked,
      totalUnlockedXp: xpSum,
      rarestBadgeTitle: rarest,
    };
  }, [history, currentXp, currentLevel]);

  // Filtered lists
  const filteredUnlocked = useMemo(() => {
    return unlockedBadges.filter(b =>
      b.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      b.desc.toLowerCase().includes(searchQuery.toLowerCase())
    );
  }, [unlockedBadges, searchQuery]);

  const filteredLocked = useMemo(() => {
    return lockedBadges.filter(b =>
      b.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      b.desc.toLowerCase().includes(searchQuery.toLowerCase())
    );
  }, [lockedBadges, searchQuery]);

  // Current user's leaderboard rank
  const currentUserEntry = leaderboardUsers.find(u => u.isUser);
  const currentUserRankStr = currentUserEntry ? `#${currentUserEntry.rank}` : 'Unranked';

  return (
    <div className="p-6 relative z-10 max-w-7xl mx-auto space-y-6 pt-2">

      {/* Tabs and Real XP Indicator */}
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
          <span>{currentXp.toLocaleString()} XP • Level {currentLevel}</span>
        </div>
      </div>

      {activeTab === 'badges' ? (
        <div className="space-y-8">
          {/* Authentic Metrics Row */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className="py-8 px-6 bg-[#12121a] border border-[#22222f] rounded-2xl flex flex-col justify-center items-center text-center shadow-xl"
            >
              <h3 className="text-4xl font-extrabold text-white tracking-tight">
                {unlockedBadges.length}/{BADGE_CATALOG.length}
              </h3>
              <span className="text-[11px] text-gray-500 mt-2 font-semibold uppercase tracking-wider">Achievements Unlocked</span>
            </motion.div>

            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.05 }}
              className="py-8 px-6 bg-[#12121a] border border-[#22222f] rounded-2xl flex flex-col justify-center items-center text-center shadow-xl"
            >
              <h3 className="text-4xl font-extrabold text-amber-500 tracking-tight">
                {totalUnlockedXp.toLocaleString()}
              </h3>
              <span className="text-[11px] text-gray-500 mt-2 font-semibold uppercase tracking-wider">XP from Achievements</span>
            </motion.div>

            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 }}
              className="py-8 px-6 bg-[#12121a] border border-[#22222f] rounded-2xl flex flex-col justify-center items-center text-center shadow-xl"
            >
              <h3 className="text-4xl font-extrabold text-cyan-400 tracking-tight">
                {Math.round((unlockedBadges.length / BADGE_CATALOG.length) * 100)}%
              </h3>
              <span className="text-[11px] text-gray-500 mt-2 font-semibold uppercase tracking-wider">Completion Rate</span>
            </motion.div>

            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.15 }}
              className="py-8 px-6 bg-[#12121a] border border-[#22222f] rounded-2xl flex flex-col justify-center items-center text-center shadow-xl"
            >
              <h3 className="text-2xl font-black bg-gradient-to-r from-purple-400 via-pink-400 to-pink-500 bg-clip-text text-transparent tracking-tight truncate max-w-full">
                {rarestBadgeTitle}
              </h3>
              <span className="text-[11px] text-gray-500 mt-3 font-semibold uppercase tracking-wider">Latest Achievement</span>
            </motion.div>
          </div>

          {/* Unlocked Badges Section */}
          <div className="space-y-4">
            <div className="flex items-center gap-2 text-green-400 font-bold text-sm tracking-wide uppercase">
              <span className="flex items-center justify-center w-5 h-5 rounded-full bg-green-500/10 border border-green-500/20 text-[10px]">✓</span>
              <span>Unlocked ({unlockedBadges.length})</span>
            </div>

            {unlockedBadges.length === 0 ? (
              <div className="p-8 text-center bg-[#12121a] border border-[#22222f] rounded-2xl space-y-2">
                <span className="text-3xl">🎯</span>
                <h4 className="text-white font-bold text-sm">No badges unlocked yet</h4>
                <p className="text-gray-400 text-xs">Run your first experiment in the Lab to earn the "First Steps" badge!</p>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {filteredUnlocked.map((badge, idx) => (
                  <motion.div
                    key={badge.id}
                    initial={{ opacity: 0, y: 15 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: idx * 0.05 }}
                    whileHover={{ y: -3, border: "1px solid rgba(16, 185, 129, 0.2)", backgroundColor: "#151522" }}
                    className="p-6 bg-[#12121a] border border-[#22222f] rounded-2xl flex flex-col justify-between min-h-[150px] shadow-lg transition-all"
                  >
                    <div className="flex justify-between items-start gap-4">
                      <div className="flex gap-4">
                        <div className={`w-12 h-12 rounded-xl flex items-center justify-center flex-shrink-0 ${
                          badge.tag === "Epic" ? "bg-purple-500/15 border border-purple-500/30 text-purple-400" :
                          badge.tag === "Rare" ? "bg-blue-500/15 border border-blue-500/30 text-blue-400" :
                          badge.tag === "Uncommon" ? "bg-emerald-500/15 border border-emerald-500/30 text-emerald-400" :
                          "bg-cyan-500/15 border border-cyan-500/30 text-cyan-400"
                        }`}>
                          <badge.icon className="w-5 h-5" />
                        </div>
                        <div>
                          <h4 className="text-base font-bold text-white tracking-wide">{badge.title}</h4>
                          <p className="text-xs text-gray-400 mt-1 leading-relaxed">{badge.desc}</p>
                        </div>
                      </div>
                      <span className="text-xs font-bold text-yellow-500 flex items-center gap-1 flex-shrink-0 self-start mt-0.5">
                        <Star className="w-3.5 h-3.5 fill-current text-yellow-500" />
                        +{badge.xpReward} XP
                      </span>
                    </div>
                    
                    <div className="flex justify-between items-center mt-4 pt-3 border-t border-white/5">
                      <span className={`px-2 py-0.5 text-[10px] font-bold rounded-md border ${
                        badge.tag === "Epic" ? "bg-purple-950/40 text-purple-400 border-purple-500/20" :
                        badge.tag === "Rare" ? "bg-blue-950/40 text-blue-400 border-blue-500/20" :
                        badge.tag === "Uncommon" ? "bg-emerald-950/40 text-emerald-400 border-emerald-500/20" :
                        "bg-cyan-950/40 text-cyan-400 border-cyan-500/20"
                      }`}>
                        {badge.tag}
                      </span>
                      <span className="text-[10px] text-gray-500 font-medium">
                        {badge.date}
                      </span>
                    </div>
                  </motion.div>
                ))}
              </div>
            )}
          </div>

          {/* In Progress / Locked Section */}
          <div className="space-y-4">
            <div className="flex items-center gap-2 text-gray-500 font-bold text-sm tracking-wide uppercase">
              <span className="flex items-center justify-center w-5 h-5 rounded-full bg-white/5 border border-white/10 text-[10px]">🔒</span>
              <span>In Progress ({lockedBadges.length})</span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {filteredLocked.map((badge, idx) => {
                const pct = Math.min(100, Math.max(0, (badge.progress / badge.maxProgress) * 100));
                return (
                  <motion.div
                    key={badge.id}
                    initial={{ opacity: 0, y: 15 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: idx * 0.05 }}
                    className="p-6 bg-[#12121a]/60 border border-[#22222f]/80 rounded-2xl flex flex-col justify-between min-h-[170px] shadow-lg"
                  >
                    <div className="flex justify-between items-start gap-4">
                      <div className="flex gap-4">
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
                          style={{ width: `${pct}%` }}
                        />
                      </div>

                      <div className="flex justify-between items-center pt-2">
                        <span className={`px-2 py-0.5 text-[10px] font-bold rounded-md border ${
                          badge.tag === "Epic" ? "bg-purple-950/40 text-purple-400 border-purple-500/20" :
                          badge.tag === "Rare" ? "bg-blue-950/40 text-blue-400 border-blue-500/20" :
                          "bg-zinc-800 text-gray-400 border-white/10"
                        }`}>
                          {badge.tag}
                        </span>
                        <span className="text-xs font-bold text-gray-500 flex items-center gap-1.5">
                          <Star className="w-3.5 h-3.5 fill-current text-gray-600" />
                          +{badge.xpReward} XP
                        </span>
                      </div>
                    </div>
                  </motion.div>
                );
              })}
            </div>
          </div>
        </div>
      ) : (
        /* Global Leaderboard Tab */
        <div className="space-y-8">
          {loadingLeaderboard ? (
            <div className="text-center py-12 text-gray-400">Loading Leaderboard...</div>
          ) : leaderboardUsers.length === 0 ? (
            <div className="p-12 text-center bg-[#12121a] border border-[#22222f] rounded-2xl space-y-3">
              <Trophy className="w-12 h-12 text-yellow-500/40 mx-auto" />
              <h3 className="text-lg font-bold text-white">Leaderboard Open</h3>
              <p className="text-gray-400 text-xs">Run experiments and earn XP to take the #1 spot on the podium!</p>
            </div>
          ) : (
            <>
              {/* Top Podium Grid (Only renders available positions) */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6 items-end mt-8">
                {/* 2nd Place */}
                {leaderboardUsers[1] && (
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
                      <div className="w-full h-full rounded-full bg-[#12121a] flex items-center justify-center text-white font-black text-xl overflow-hidden">
                        {leaderboardUsers[1]?.isUser ? <UserAvatar className="w-full h-full object-cover" /> : leaderboardUsers[1]?.name?.substring(0, 2).toUpperCase() || '-'}
                      </div>
                    </div>
                    <h3 className="text-lg font-bold text-white mt-3">{leaderboardUsers[1]?.isUser ? 'You' : (leaderboardUsers[1]?.name || 'Student')}</h3>
                    <p className="text-xs text-gray-400">{leaderboardUsers[1]?.badge || '⭐ Gravity Sage'} • Level {leaderboardUsers[1]?.level || 1}</p>
                    <div className="mt-4 px-4 py-1.5 bg-gray-500/10 border border-gray-500/20 rounded-xl text-gray-300 font-extrabold text-sm">
                      {(leaderboardUsers[1]?.xp || 0).toLocaleString()} XP
                    </div>
                  </motion.div>
                )}

                {/* 1st Place */}
                {leaderboardUsers[0] && (
                  <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    whileHover={{ y: -5 }}
                    className="order-1 md:order-2 p-8 bg-gradient-to-t from-[#12121a] to-[#201c1c] border border-yellow-500/30 rounded-2xl flex flex-col items-center text-center relative shadow-2xl min-h-[260px] md:scale-105 z-10"
                  >
                    <div className="absolute -top-8 w-16 h-16 rounded-full bg-gradient-to-tr from-yellow-500 to-amber-300 border-4 border-[#0b0b14] flex items-center justify-center text-yellow-950 font-black text-xl shadow-lg">
                      👑
                    </div>
                    <div className="w-20 h-20 rounded-full bg-gradient-to-tr from-yellow-500 to-amber-300 p-0.5 shadow-lg mt-2">
                      <div className="w-full h-full rounded-full bg-[#12121a] flex items-center justify-center text-white font-black text-2xl overflow-hidden">
                        {leaderboardUsers[0]?.isUser ? <UserAvatar className="w-full h-full object-cover" /> : leaderboardUsers[0]?.name?.substring(0, 2).toUpperCase() || '-'}
                      </div>
                    </div>
                    <h3 className="text-xl font-black text-white mt-3 flex items-center gap-1.5">
                      {leaderboardUsers[0]?.isUser ? 'You' : (leaderboardUsers[0]?.name || 'Student')}
                    </h3>
                    <p className="text-xs text-yellow-400 font-semibold">{leaderboardUsers[0]?.badge || '🏆 Top Scholar'} • Level {leaderboardUsers[0]?.level || 1}</p>
                    <div className="mt-4 px-5 py-2 bg-yellow-500/10 border border-yellow-500/20 rounded-xl text-yellow-400 font-extrabold text-base shadow-lg shadow-yellow-500/5">
                      {(leaderboardUsers[0]?.xp || 0).toLocaleString()} XP
                    </div>
                  </motion.div>
                )}

                {/* 3rd Place */}
                {leaderboardUsers[2] && (
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
                      <div className="w-full h-full rounded-full bg-[#12121a] flex items-center justify-center text-white font-black text-xl overflow-hidden">
                        {leaderboardUsers[2]?.isUser ? <UserAvatar className="w-full h-full object-cover" /> : leaderboardUsers[2]?.name?.substring(0, 2).toUpperCase() || '-'}
                      </div>
                    </div>
                    <h3 className="text-lg font-bold text-white mt-3">{leaderboardUsers[2]?.isUser ? 'You' : (leaderboardUsers[2]?.name || 'Student')}</h3>
                    <p className="text-xs text-gray-400">{leaderboardUsers[2]?.badge || '⚡ Electro Pro'} • Level {leaderboardUsers[2]?.level || 1}</p>
                    <div className="mt-4 px-4 py-1.5 bg-orange-500/10 border border-orange-500/20 rounded-xl text-orange-400 font-extrabold text-sm">
                      {(leaderboardUsers[2]?.xp || 0).toLocaleString()} XP
                    </div>
                  </motion.div>
                )}
              </div>

              {/* Leaderboard Table List (for users rank 4+) */}
              {leaderboardUsers.length > 3 && (
                <div className="bg-[#12121a] border border-[#22222f] rounded-2xl overflow-hidden shadow-2xl">
                  <div className="p-5 border-b border-white/5 bg-white/[0.01] flex justify-between items-center">
                    <div>
                      <h3 className="text-white font-bold text-base">Top Contenders</h3>
                      <p className="text-gray-500 text-xs mt-0.5">Performance ranking of junior and senior scientists this week</p>
                    </div>
                    <span className="text-xs text-cyan-400 font-bold bg-cyan-500/10 border border-cyan-500/20 px-3 py-1 rounded-full">
                      Your Rank: {currentUserRankStr}
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
                          <div className="w-8 h-8 rounded-full bg-[#1b1b26] border border-white/5 flex items-center justify-center font-bold text-gray-400 text-sm">
                            {user.rank}
                          </div>

                          <div className={`w-10 h-10 rounded-full flex items-center justify-center text-white font-extrabold text-sm shadow-md overflow-hidden ${
                            user.isUser
                              ? 'bg-gradient-to-tr from-cyan-500 to-blue-600'
                              : 'bg-[#1b1b26] border border-white/10 text-gray-300'
                          }`}>
                            {user.isUser ? (
                              <UserAvatar className="w-full h-full object-cover rounded-full" />
                            ) : (
                              (user.name || user.username || 'Student').charAt(0).toUpperCase()
                            )}
                          </div>

                          <div>
                            <h4 className="text-sm font-bold text-white flex items-center gap-2">
                              {user.name || user.username || 'Student'}
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
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}

export default AchievementsPage;
