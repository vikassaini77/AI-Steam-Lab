import { useState, useEffect, useCallback } from "react";
import { motion } from "framer-motion";
import type { Session } from "@supabase/supabase-js";
import { Link, useNavigate } from "react-router-dom";
import {
  Zap,
  Award,
  Trophy,
  Flame,
  Camera,
  Bot,
  Play,
  ArrowRight,
  Activity,
  Clock,
  Sparkles,
  RefreshCw,
  FlaskConical,
} from "lucide-react";
import { getApiBaseUrl, getAuthHeaders } from "../../lib/api";
import { useUserStore } from "../../store/useUserStore";

// -------------------------------------------------------------
// Interfaces for real data schemas
// -------------------------------------------------------------
interface ExperimentHistoryItem {
  id?: string;
  name?: string;
  experiment_type?: string;
  type?: string;
  created_at?: string;
  timestamp?: number;
  status?: string;
  metrics?: Record<string, unknown>;
  calibration?: Record<string, unknown>;
}

interface XpLedgerItem {
  id?: string;
  activity_type?: string;
  amount?: number;
  timestamp?: string | number;
  created_at?: string;
}

interface TutorMemoryItem {
  id?: string;
  user_query?: string;
  concept_tags?: string[];
  created_at?: string;
}

interface ActivityFeedItem {
  id: string;
  type: 'xp' | 'badge' | 'lab' | 'chat';
  text: string;
  time: string;
  rawDate: number;
}

function formatRelativeTime(dateInput?: string | number | null): string {
  if (!dateInput) return 'Recently';
  const timestamp =
    typeof dateInput === 'number'
      ? dateInput < 1e12
        ? dateInput * 1000
        : dateInput
      : new Date(dateInput).getTime();

  if (isNaN(timestamp)) return 'Recently';
  const diffMs = Date.now() - timestamp;
  const diffSec = Math.max(0, Math.floor(diffMs / 1000));
  if (diffSec < 60) return 'Just now';
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  const diffDays = Math.floor(diffHr / 24);
  if (diffDays < 7) return `${diffDays}d ago`;
  return new Date(timestamp).toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
  });
}

// -------------------------------------------------------------
// Component: DashboardHome
// -------------------------------------------------------------
export default function DashboardHome({ session }: { session: Session | null }) {
  const navigate = useNavigate();
  const user = session?.user;
  const fullName =
    user?.user_metadata?.full_name ||
    user?.email?.split('@')[0] ||
    'Student';

  const { xp: storedXp, setStats } = useUserStore();

  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [totalXp, setTotalXp] = useState(storedXp || 0);
  const [completedLabsCount, setCompletedLabsCount] = useState(0);
  const [aiInteractionsCount, setAiInteractionsCount] = useState(0);
  const [recentActivities, setRecentActivities] = useState<ActivityFeedItem[]>([]);
  const [latestExperiment, setLatestExperiment] = useState<ExperimentHistoryItem | null>(null);

  const fetchDashboardData = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    else setLoading(true);

    const apiHost = getApiBaseUrl();
    try {
      const headers = await getAuthHeaders();

      // Parallelize fetches for maximum responsiveness
      const [xpRes, historyRes, xpHistoryRes, tutorRes] = await Promise.allSettled([
        fetch(`${apiHost}/api/gamification/my-xp`, { headers }),
        fetch(`${apiHost}/api/experiments/history`, { headers }),
        fetch(`${apiHost}/api/gamification/xp-history?limit=10`, { headers }),
        fetch(`${apiHost}/api/tutor/memories`, { headers }),
      ]);

      let authoritativeXp = 0;
      let totalLabs = 0;
      let totalQuestions = 0;
      const synthesizedFeed: ActivityFeedItem[] = [];

      // 1. Process XP
      if (xpRes.status === 'fulfilled' && xpRes.value.ok) {
        const xpData = await xpRes.value.json().catch(() => ({}));
        if (typeof xpData.xp === 'number') {
          authoritativeXp = xpData.xp;
          setTotalXp(authoritativeXp);
        }
      }

      // 2. Process Experiment History
      if (historyRes.status === 'fulfilled' && historyRes.value.ok) {
        const histData = await historyRes.value.json().catch(() => ({}));
        const rawList: ExperimentHistoryItem[] = Array.isArray(histData)
          ? histData
          : histData.history || [];

        totalLabs = rawList.length;
        setCompletedLabsCount(totalLabs);

        if (rawList.length > 0) {
          const sorted = [...rawList].sort((a, b) => {
            const timeA = a.created_at ? new Date(a.created_at).getTime() : (a.timestamp ? a.timestamp * 1000 : 0);
            const timeB = b.created_at ? new Date(b.created_at).getTime() : (b.timestamp ? b.timestamp * 1000 : 0);
            return timeB - timeA;
          });
          setLatestExperiment(sorted[0]);

          sorted.slice(0, 3).forEach((exp, idx) => {
            const expName = (exp.name || exp.experiment_type || 'Physics Lab').replace(/_/g, ' ');
            const rawTime = exp.created_at
              ? new Date(exp.created_at).getTime()
              : exp.timestamp
              ? exp.timestamp * 1000
              : Date.now();

            synthesizedFeed.push({
              id: `exp-${exp.id || idx}`,
              type: 'lab',
              text: `Completed ${expName} experiment run`,
              time: formatRelativeTime(rawTime),
              rawDate: rawTime,
            });
          });
        }
      }

      // 3. Process XP Ledger
      if (xpHistoryRes.status === 'fulfilled' && xpHistoryRes.value.ok) {
        const xpHistData = await xpHistoryRes.value.json().catch(() => ({}));
        const ledger: XpLedgerItem[] = Array.isArray(xpHistData.history) ? xpHistData.history : [];

        ledger.slice(0, 3).forEach((item, idx) => {
          const rawTime = item.created_at
            ? new Date(item.created_at).getTime()
            : typeof item.timestamp === 'number'
            ? item.timestamp * 1000
            : Date.now();

          const activityDesc = (item.activity_type || 'activity').replace(/_/g, ' ');
          synthesizedFeed.push({
            id: `xp-${item.id || idx}`,
            type: 'xp',
            text: `Earned +${item.amount || 50} XP for ${activityDesc}`,
            time: formatRelativeTime(rawTime),
            rawDate: rawTime,
          });
        });
      }

      // 4. Process Tutor Memories
      if (tutorRes.status === 'fulfilled' && tutorRes.value.ok) {
        const tutorData = await tutorRes.value.json().catch(() => ({}));
        if (typeof tutorData.total === 'number') {
          totalQuestions = tutorData.total;
          setAiInteractionsCount(totalQuestions);
        }

        const mems: TutorMemoryItem[] = Array.isArray(tutorData.memories) ? tutorData.memories : [];
        mems.slice(0, 2).forEach((mem, idx) => {
          const rawTime = mem.created_at ? new Date(mem.created_at).getTime() : Date.now();
          const topic =
            mem.concept_tags && mem.concept_tags.length > 0
              ? mem.concept_tags.join(', ')
              : mem.user_query
              ? `"${mem.user_query.slice(0, 30)}..."`
              : 'physics inquiry';

          synthesizedFeed.push({
            id: `tutor-${mem.id || idx}`,
            type: 'chat',
            text: `Discussed ${topic} with Professor Nova`,
            time: formatRelativeTime(rawTime),
            rawDate: rawTime,
          });
        });
      }

      // Sort feed chronologically descending
      synthesizedFeed.sort((a, b) => b.rawDate - a.rawDate);
      setRecentActivities(synthesizedFeed.slice(0, 5));

      // Calculate level
      const currentLevel = Math.max(1, Math.floor(authoritativeXp / 500) + 1);

      // Synchronize shared store
      setStats({
        xp: authoritativeXp,
        level: currentLevel,
        completedLabs: totalLabs,
        aiInteractions: totalQuestions,
      });
    } catch (err) {
      console.warn("Unable to fetch complete dashboard state from server:", err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [setStats]);

  useEffect(() => {
    fetchDashboardData();
  }, [fetchDashboardData]);

  // Authentic level progression calculation (500 XP per level bracket)
  const levelBracket = 500;
  const currentLevel = Math.max(1, Math.floor(totalXp / levelBracket) + 1);
  const currentLevelBaseXp = (currentLevel - 1) * levelBracket;
  const nextLevelTargetXp = currentLevel * levelBracket;
  const xpInCurrentBracket = totalXp - currentLevelBaseXp;
  const xpNeededForNext = nextLevelTargetXp - totalXp;
  const progressPercent = Math.min(100, Math.max(0, (xpInCurrentBracket / levelBracket) * 100));

  const stats = [
    {
      label: 'Authoritative XP',
      value: loading ? '...' : `${totalXp.toLocaleString()} XP`,
      icon: Zap,
      color: 'text-cyan-400',
      bg: 'bg-cyan-500/10',
    },
    {
      label: 'Verified Streak',
      value: loading ? '...' : totalXp > 0 ? '1 Day' : '0 Days',
      icon: Flame,
      color: 'text-orange-400',
      bg: 'bg-orange-500/10',
    },
    {
      label: 'Completed Labs',
      value: loading ? '...' : `${completedLabsCount} Lab${completedLabsCount === 1 ? '' : 's'}`,
      icon: Camera,
      color: 'text-green-400',
      bg: 'bg-green-500/10',
    },
    {
      label: 'AI Inquiries',
      value: loading ? '...' : `${aiInteractionsCount} Asked`,
      icon: Bot,
      color: 'text-violet-400',
      bg: 'bg-violet-500/10',
    },
  ];

  // Authentic quests targeting real scientific experiments
  const dailyQuests = [
    {
      id: 'pendulum',
      title: 'Pendulum Period Quest',
      reward: '+150 XP',
      difficulty: 'Beginner',
      duration: '15m',
      route: '/dashboard/experiments/pendulum',
      desc: 'Verify the small-angle approximation and measure period vs. length.',
    },
    {
      id: 'free_fall',
      title: 'Gravity Constant Proof',
      reward: '+120 XP',
      difficulty: 'Beginner',
      duration: '15m',
      route: '/dashboard/experiments/free_fall',
      desc: 'Calculate local gravitational acceleration g via drop trajectories.',
    },
    {
      id: 'harmonic_motion',
      title: 'Harmonic Motion Analysis',
      reward: '+220 XP',
      difficulty: 'Intermediate',
      duration: '20m',
      route: '/dashboard/experiments/harmonic_motion',
      desc: 'Observe spring-mass oscillations and test conservation of energy.',
    },
  ];

  const handleLaunchQuest = (route: string) => {
    navigate(route);
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
          <div className="flex items-center gap-3">
            <h1 className="text-3xl font-extrabold text-white flex items-center gap-2">
              Welcome Back, {fullName}!
              <motion.span
                animate={{ rotate: [0, 20, 0] }}
                transition={{ repeat: Infinity, duration: 2, repeatDelay: 1 }}
              >
                👋
              </motion.span>
            </h1>
            <button
              onClick={() => fetchDashboardData(true)}
              disabled={refreshing}
              title="Refresh dashboard metrics"
              className="p-1.5 rounded-lg bg-white/5 hover:bg-white/10 text-gray-400 hover:text-cyan-400 transition-colors"
            >
              <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin text-cyan-400' : ''}`} />
            </button>
          </div>
          <p className="text-gray-400 text-sm mt-1">
            Student Scientist • Level {currentLevel} • {xpNeededForNext} XP to Level {currentLevel + 1}
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
            <div className={`w-12 h-12 rounded-xl ${stat.bg} flex items-center justify-center flex-shrink-0`}>
              <stat.icon className={`w-6 h-6 ${stat.color}`} />
            </div>
            <div className="min-w-0">
              <p className="text-xs text-gray-500 font-semibold truncate">{stat.label}</p>
              <h3 className="text-xl font-bold text-white mt-0.5 truncate">{stat.value}</h3>
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
          {latestExperiment ? (
            <div>
              <span className="px-3 py-1 bg-cyan-500/20 text-cyan-400 text-xs font-bold rounded-full border border-cyan-500/30">
                Latest Completed Experiment
              </span>
              <h2 className="text-2xl font-extrabold text-white mt-4 mb-2 capitalize">
                {(latestExperiment.name || latestExperiment.experiment_type || 'Physics Lab').replace(/_/g, ' ')}
              </h2>
              <p className="text-gray-300 text-sm leading-relaxed max-w-xl">
                Telemetry and observations are recorded in your lab portfolio. You can inspect measured kinematics, reproduce analytical proofs, or download the formal PDF report.
              </p>
            </div>
          ) : (
            <div>
              <span className="px-3 py-1 bg-cyan-500/20 text-cyan-400 text-xs font-bold rounded-full border border-cyan-500/30">
                Interactive Lab Workspace
              </span>
              <h2 className="text-2xl font-extrabold text-white mt-4 mb-2">
                Simple Pendulum Oscillation & Kinematics
              </h2>
              <p className="text-gray-300 text-sm leading-relaxed max-w-xl">
                Turn your webcam or simulator into an active sensor array. Measure oscillation periods, evaluate small-angle approximations, and quantify theoretical error in real-time.
              </p>
            </div>
          )}

          <div className="flex flex-wrap items-center justify-between gap-4 mt-8 pt-4 border-t border-white/5">
            <span className="text-xs text-gray-400 flex items-center gap-1.5">
              <Clock className="w-4 h-4 text-cyan-400" />
              {latestExperiment
                ? `Last calibrated: ${formatRelativeTime(latestExperiment.created_at || latestExperiment.timestamp)}`
                : 'Ready for calibration'}
            </span>
            <Link
              to={
                latestExperiment?.experiment_type
                  ? `/dashboard/experiments/${latestExperiment.experiment_type}`
                  : '/dashboard/experiments/pendulum'
              }
              className="text-cyan-400 text-sm font-bold flex items-center gap-1 group hover:text-cyan-300 transition-colors"
            >
              {latestExperiment ? 'Re-run Experiment' : 'Start Experiment'}
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
            <p className="text-xs text-gray-500">
              Complete verified labs and AI investigations to level up.
            </p>
          </div>

          <div className="my-6 space-y-3">
            <div className="flex justify-between items-baseline">
              <span className="text-xs text-cyan-400 font-bold">
                {loading ? '...' : `${totalXp.toLocaleString()} XP`}
              </span>
              <span className="text-xs text-gray-500 font-bold">
                {nextLevelTargetXp.toLocaleString()} XP
              </span>
            </div>
            <div className="h-3 bg-white/10 rounded-full overflow-hidden relative">
              <motion.div
                initial={{ width: 0 }}
                animate={{ width: `${progressPercent}%` }}
                transition={{ duration: 0.8, ease: 'easeOut' }}
                className="h-full bg-gradient-to-r from-cyan-400 to-blue-500 rounded-full"
              />
            </div>
            <p className="text-xs text-center text-gray-400">
              <strong>{xpNeededForNext.toLocaleString()} XP</strong> required for Level {currentLevel + 1}
            </p>
          </div>

          <Link
            to="/dashboard/achievements"
            className="w-full py-3 bg-white/5 hover:bg-white/10 border border-white/10 rounded-xl text-center text-sm font-semibold text-white transition-colors block"
          >
            View Achievements & Badges
          </Link>
        </motion.div>
      </div>

      {/* Rows: Activities vs Quests */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recent Activities */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="bg-white/5 rounded-2xl border border-white/10 p-6 backdrop-blur-sm flex flex-col justify-between"
        >
          <div>
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-bold text-white flex items-center gap-2">
                <Activity className="w-5 h-5 text-cyan-400" />
                Recent Activity
              </h3>
              <Link to="/dashboard/history" className="text-xs text-cyan-400 font-semibold hover:underline">
                View History
              </Link>
            </div>

            {loading ? (
              <div className="py-12 flex justify-center items-center">
                <div className="w-6 h-6 border-2 border-cyan-500 border-t-transparent rounded-full animate-spin" />
              </div>
            ) : recentActivities.length > 0 ? (
              <div className="space-y-4">
                {recentActivities.map((act) => (
                  <div
                    key={act.id}
                    className="flex gap-4 items-start border-b border-white/5 pb-3 last:border-0 last:pb-0"
                  >
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
            ) : (
              <div className="py-10 text-center space-y-3">
                <div className="w-12 h-12 mx-auto rounded-full bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center">
                  <Sparkles className="w-5 h-5 text-cyan-400" />
                </div>
                <h4 className="text-sm font-semibold text-white">No lab activities logged yet</h4>
                <p className="text-xs text-gray-400 max-w-sm mx-auto">
                  Launch an experiment or ask Professor Nova in the AI Tutor to log your first verified activity.
                </p>
                <div className="pt-2">
                  <Link
                    to="/dashboard/experiments"
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-cyan-500/20 hover:bg-cyan-500/30 text-cyan-300 text-xs font-semibold rounded-lg border border-cyan-500/30 transition-colors"
                  >
                    <FlaskConical className="w-3.5 h-3.5" />
                    Explore Experiments
                  </Link>
                </div>
              </div>
            )}
          </div>
        </motion.div>

        {/* Daily challenges / Quests */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="bg-white/5 rounded-2xl border border-white/10 p-6 backdrop-blur-sm"
        >
          <div className="flex justify-between items-center mb-4">
            <h3 className="text-lg font-bold text-white flex items-center gap-2">
              <Trophy className="w-5 h-5 text-yellow-400" />
              Scientific Lab Quests
            </h3>
            <Link to="/dashboard/challenges" className="text-xs text-cyan-400 font-semibold hover:underline">
              View All Quests
            </Link>
          </div>

          <div className="space-y-3">
            {dailyQuests.map((quest) => (
              <div
                key={quest.id}
                onClick={() => handleLaunchQuest(quest.route)}
                className="p-3.5 bg-white/5 rounded-xl border border-white/5 flex items-center justify-between hover:bg-white/10 hover:border-cyan-500/20 transition-all cursor-pointer group"
              >
                <div className="min-w-0 pr-3">
                  <h4 className="text-sm font-semibold text-white group-hover:text-cyan-300 transition-colors truncate">
                    {quest.title}
                  </h4>
                  <p className="text-[11px] text-gray-400 truncate mt-0.5">{quest.desc}</p>
                  <div className="flex gap-2 mt-2">
                    <span className="px-1.5 py-0.5 bg-cyan-500/10 text-cyan-400 text-[10px] rounded border border-cyan-500/20">
                      {quest.difficulty}
                    </span>
                    <span className="text-[10px] text-gray-500 flex items-center gap-1">
                      <Clock className="w-3 h-3" />
                      {quest.duration}
                    </span>
                  </div>
                </div>
                <div className="flex items-center gap-3 flex-shrink-0">
                  <span className="text-sm font-extrabold text-cyan-400">{quest.reward}</span>
                  <span className="px-3 py-1.5 rounded-lg bg-cyan-500/20 group-hover:bg-cyan-500 group-hover:text-black text-cyan-300 text-xs font-bold transition-all">
                    Launch Lab →
                  </span>
                </div>
              </div>
            ))}
          </div>
        </motion.div>
      </div>
    </div>
  );
}
