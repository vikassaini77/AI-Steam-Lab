import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { useNavigate } from "react-router-dom";
import { CheckCircle2, Zap } from "lucide-react";
import { getApiBaseUrl, getAuthHeaders } from "../../lib/api";

interface UserHistoryItem {
  id?: string;
  experiment_type?: string;
  type?: string;
  created_at?: string;
}

interface QuestDef {
  expId: string;
  title: string;
  reward: string;
  difficulty: 'Beginner' | 'Intermediate' | 'Hard' | 'Advanced';
  category: string;
  badge: string;
  desc: string;
}

const QUEST_DEFINITIONS: QuestDef[] = [
  {
    expId: 'pendulum',
    title: 'Pendulum Period Quest',
    reward: '+150 XP',
    difficulty: 'Beginner',
    category: 'Kinematics',
    badge: '⏱️ Period Pioneer',
    desc: 'Accurately map the period (T) of the pendulum bob by modifying lengths in real-time camera calibrations.',
  },
  {
    expId: 'free_fall',
    title: 'Gravity Constant Proof',
    reward: '+120 XP',
    difficulty: 'Beginner',
    category: 'Gravitation',
    badge: '🌌 Gravity Conqueror',
    desc: 'Verify gravitational acceleration (9.8 m/s²) on camera visualizers using string angle and drop timing tracking.',
  },
  {
    expId: 'projectile_motion',
    title: 'Ballistic Trajectory Test',
    reward: '+100 XP',
    difficulty: 'Intermediate',
    category: 'Mechanics',
    badge: '⚡ Ballistic Scout',
    desc: 'Map initial launch speed and parabolic trajectory to predict impact distance with zero fabricated numbers.',
  },
  {
    expId: 'circular_motion',
    title: 'Centripetal Force Exploration',
    reward: '+200 XP',
    difficulty: 'Intermediate',
    category: 'Dynamics',
    badge: '🔄 Centripetal Sage',
    desc: 'Measure centripetal acceleration and verify the rotational frequency equations under steady radial motion.',
  },
  {
    expId: 'harmonic_motion',
    title: 'Harmonic Motion Explorer',
    reward: '+220 XP',
    difficulty: 'Hard',
    category: 'Oscillations',
    badge: '🌀 Harmonic Emperor',
    desc: 'Calibrate simple harmonic damping effects in spring-mass systems and evaluate conservation of mechanical energy.',
  },
  {
    expId: 'collision_momentum',
    title: 'Momentum Conservation Trial',
    reward: '+300 XP',
    difficulty: 'Advanced',
    category: 'Momentum',
    badge: '💥 Collision Master',
    desc: 'Verify the law of conservation of momentum before and after one-dimensional elastic and inelastic collisions.',
  },
];

function ChallengesPage() {
  const navigate = useNavigate();
  const [history, setHistory] = useState<UserHistoryItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    let isMounted = true;
    const fetchHistory = async () => {
      try {
        const apiBase = getApiBaseUrl();
        const headers = await getAuthHeaders();
        const res = await fetch(`${apiBase}/api/experiments/history`, { headers });
        if (res.ok) {
          const data = await res.json();
          if (isMounted) {
            setHistory(data.history || []);
          }
        }
      } catch (err) {
        console.warn("Failed to load user history for challenges:", err);
      } finally {
        if (isMounted) setLoading(false);
      }
    };
    fetchHistory();
    return () => { isMounted = false; };
  }, []);

  const completedExpTypes = new Set(
    history.map(h => (h.experiment_type || h.type || '').toLowerCase()).filter(Boolean)
  );

  const completedCount = QUEST_DEFINITIONS.filter(q => completedExpTypes.has(q.expId)).length;

  return (
    <div className="p-6 relative z-10 max-w-6xl mx-auto space-y-6 pt-2">
      {/* Header Summary */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-white/5 pb-4">
        <div>
          <h2 className="text-2xl font-bold text-white flex items-center gap-2">
            <Zap className="w-6 h-6 text-cyan-400" />
            Laboratory Challenges & Quests
          </h2>
          <p className="text-gray-400 text-xs mt-1">Complete scientific calibration tasks to earn XP and unlock badges</p>
        </div>
        <div className="px-4 py-2 bg-cyan-500/10 border border-cyan-500/20 rounded-xl text-cyan-400 text-xs font-bold self-start sm:self-auto">
          {loading ? 'Checking...' : `${completedCount} of ${QUEST_DEFINITIONS.length} Quests Mastered`}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {QUEST_DEFINITIONS.map((q, idx) => {
          const isCompleted = completedExpTypes.has(q.expId);
          return (
            <motion.div
              key={q.expId}
              initial={{ opacity: 0, y: 15 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: idx * 0.05 }}
              whileHover={{ y: -4, border: '1px solid rgba(6, 182, 212, 0.4)' }}
              className={`p-5 rounded-2xl border backdrop-blur-sm flex flex-col justify-between ${
                isCompleted
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
                  <span className="text-xs font-bold text-gray-400">{q.badge}</span>
                </div>
                <h3 className="text-lg font-bold text-white mt-3 flex items-center gap-2">
                  {q.title}
                  {isCompleted && <CheckCircle2 className="w-5 h-5 text-green-400" />}
                </h3>
                <p className="text-xs text-gray-400 mt-2 leading-relaxed">{q.desc}</p>
              </div>

              <div className="flex justify-between items-center mt-6 pt-4 border-t border-white/5">
                <span className="text-cyan-400 font-extrabold text-sm">{q.reward}</span>
                <motion.button
                  whileHover={{ scale: 1.05 }}
                  whileTap={{ scale: 0.95 }}
                  onClick={() => navigate(`/dashboard/experiments/${q.expId}`)}
                  className={`px-4 py-2 text-xs font-semibold rounded-lg transition-all ${
                    isCompleted
                      ? 'bg-green-500/20 text-green-400 hover:bg-green-500/30'
                      : 'bg-gradient-to-r from-cyan-500 to-blue-600 text-white shadow-lg shadow-cyan-500/10'
                  }`}
                >
                  {isCompleted ? 'Rerun Lab' : 'Launch Lab'}
                </motion.button>
              </div>
            </motion.div>
          );
        })}
      </div>
    </div>
  );
}

export default ChallengesPage;
