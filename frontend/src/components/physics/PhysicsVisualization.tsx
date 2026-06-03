import { motion } from 'framer-motion';
import { useState, useEffect } from 'react';
import { AreaChart, Area, LineChart, Line, ResponsiveContainer } from 'recharts';

export default function PhysicsVisualization() {
  const [trajectoryData, setTrajectoryData] = useState<{ x: number; y: number }[]>([]);
  const [velocityData, setVelocityData] = useState<{ time: number; value: number }[]>([]);
  const [accelerationData, setAccelerationData] = useState<{ time: number; value: number }[]>([]);
  const [activeTab, setActiveTab] = useState<'trajectory' | 'velocity' | 'analysis'>('trajectory');

  useEffect(() => {
    // Generate simulated trajectory data
    const trajectory: { x: number; y: number }[] = [];
    const velocity: { time: number; value: number }[] = [];
    const acceleration: { time: number; value: number }[] = [];

    for (let i = 0; i < 50; i++) {
      const t = i / 10;
      const x = Math.sin(t * 2) * 100;
      const y = Math.cos(t * 2) * 50;
      trajectory.push({ x, y });

      velocity.push({
        time: t,
        value: Math.abs(Math.cos(t * 2)) * 5,
      });

      acceleration.push({
        time: t,
        value: -9.8 + Math.random() * 0.5,
      });
    }

    setTrajectoryData(trajectory);
    setVelocityData(velocity);
    setAccelerationData(acceleration);
  }, []);

  return (
    <div className="p-4">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-white">Physics Analysis</h3>
        <div className="flex gap-1 bg-white/5 rounded-lg p-1">
          {(['trajectory', 'velocity', 'analysis'] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`px-3 py-1.5 text-sm rounded-md transition-all ${
                activeTab === tab
                  ? 'bg-cyan-500/20 text-cyan-400 border border-cyan-500/30'
                  : 'text-gray-400 hover:text-white'
              }`}
            >
              {tab.charAt(0).toUpperCase() + tab.slice(1)}
            </button>
          ))}
        </div>
      </div>

      {/* Content */}
      <div className="space-y-4">
        {activeTab === 'trajectory' && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="bg-white/5 rounded-xl p-4 border border-white/10"
          >
            <h4 className="text-sm text-gray-400 mb-3">Motion Trajectory</h4>
            <div className="h-48 relative">
              {/* Grid */}
              <div
                className="absolute inset-0"
                style={{
                  backgroundImage: `
                    linear-gradient(rgba(255,255,255,0.03) 1px, transparent 1px),
                    linear-gradient(90deg, rgba(255,255,255,0.03) 1px, transparent 1px)
                  `,
                  backgroundSize: '20px 20px',
                }}
              />

              {/* Trajectory */}
              <svg className="absolute inset-0 w-full h-full">
                <defs>
                  <linearGradient id="trajectoryGradient" x1="0%" y1="0%" x2="100%" y2="0%">
                    <stop offset="0%" stopColor="#00D4FF" stopOpacity="0.2" />
                    <stop offset="50%" stopColor="#00D4FF" stopOpacity="1" />
                    <stop offset="100%" stopColor="#7C3AED" stopOpacity="0.5" />
                  </linearGradient>
                </defs>

                {/* Path */}
                <motion.path
                  initial={{ pathLength: 0 }}
                  animate={{ pathLength: 1 }}
                  transition={{ duration: 3, repeat: Infinity }}
                  d={`M ${trajectoryData
                    .map((point) => `${128 + point.x * 0.5},${96 + point.y * 0.5}`)
                    .join(' L ')}`}
                  stroke="url(#trajectoryGradient)"
                  strokeWidth="2"
                  fill="none"
                  strokeLinecap="round"
                />

                {/* Points */}
                {trajectoryData.filter((_, i) => i % 5 === 0).map((point, i) => (
                  <motion.circle
                    key={i}
                    initial={{ opacity: 0, scale: 0 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ delay: i * 0.1 }}
                    cx={128 + point.x * 0.5}
                    cy={96 + point.y * 0.5}
                    r="3"
                    fill={i === 0 ? '#00D4FF' : i === 9 ? '#7C3AED' : '#3B82F6'}
                    className={i === 0 ? 'animate-pulse' : ''}
                  />
                ))}
              </svg>
            </div>

            {/* Labels */}
            <div className="flex justify-between text-xs text-gray-500 mt-2">
              <span>Start</span>
              <span>Current Position</span>
              <span>End</span>
            </div>
          </motion.div>
        )}

        {activeTab === 'velocity' && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="bg-white/5 rounded-xl p-4 border border-white/10"
          >
            <h4 className="text-sm text-gray-400 mb-3">Velocity Over Time</h4>
            <div className="h-48">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={velocityData}>
                  <defs>
                    <linearGradient id="velocityGradient" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#00D4FF" stopOpacity="0.3" />
                      <stop offset="100%" stopColor="#00D4FF" stopOpacity="0" />
                    </linearGradient>
                  </defs>
                  <Area
                    type="monotone"
                    dataKey="value"
                    stroke="#00D4FF"
                    strokeWidth={2}
                    fill="url(#velocityGradient)"
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>

            {/* Velocity graph */}
            <div className="mt-4">
              <h4 className="text-sm text-gray-400 mb-3">Acceleration</h4>
              <div className="h-32">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={accelerationData}>
                    <Line
                      type="monotone"
                      dataKey="value"
                      stroke="#8B5CF6"
                      strokeWidth={2}
                      dot={false}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          </motion.div>
        )}

        {activeTab === 'analysis' && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="space-y-4"
          >
            {/* Formula cards */}
            <div className="bg-gradient-to-br from-cyan-500/10 to-blue-500/10 rounded-xl p-4 border border-cyan-500/20">
              <h4 className="text-sm text-cyan-400 mb-2">Period Formula</h4>
              <p className="font-mono text-2xl text-white">T = 2π√(L/g)</p>
              <p className="text-xs text-gray-400 mt-2">
                Period depends only on length and gravity
              </p>
            </div>

            <div className="bg-gradient-to-br from-violet-500/10 to-purple-500/10 rounded-xl p-4 border border-violet-500/20">
              <h4 className="text-sm text-violet-400 mb-2">Energy Conservation</h4>
              <p className="font-mono text-xl text-white">
                E = ½mv² + mgh = constant
              </p>
              <p className="text-xs text-gray-400 mt-2">
                Total mechanical energy remains constant
              </p>
            </div>

            <div className="bg-white/5 rounded-xl p-4 border border-white/10">
              <h4 className="text-sm text-gray-400 mb-3">Current Measurements</h4>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <span className="text-xs text-gray-500">Period (T)</span>
                  <p className="text-xl font-semibold text-white">1.20 s</p>
                </div>
                <div>
                  <span className="text-xs text-gray-500">Length (L)</span>
                  <p className="text-xl font-semibold text-white">35.7 cm</p>
                </div>
                <div>
                  <span className="text-xs text-gray-500">Max Velocity</span>
                  <p className="text-xl font-semibold text-cyan-400">2.45 m/s</p>
                </div>
                <div>
                  <span className="text-xs text-gray-500">Max Angle</span>
                  <p className="text-xl font-semibold text-violet-400">30°</p>
                </div>
              </div>
            </div>

            {/* Conservation verification */}
            <div className="bg-gradient-to-br from-green-500/10 to-emerald-500/10 rounded-xl p-4 border border-green-500/20">
              <div className="flex items-center gap-2 mb-2">
                <div className="w-2 h-2 rounded-full bg-green-500" />
                <h4 className="text-sm text-green-400">Energy Conservation Verified</h4>
              </div>
              <p className="text-xs text-gray-400">
                The system maintains constant total energy throughout oscillation
              </p>
            </div>
          </motion.div>
        )}
      </div>
    </div>
  );
}
