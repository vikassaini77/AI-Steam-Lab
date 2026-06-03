import { motion } from 'framer-motion';
import {
  Eye,
  Activity,
  Bot,
  Mic,
  Box,
  Route,
  Trophy,
  Zap,
} from 'lucide-react';

const features = [
  {
    icon: Eye,
    title: 'Real-Time Object Detection',
    description: 'AI instantly identifies objects in your camera feed with 99% accuracy',
    color: 'from-cyan-500 to-blue-500',
    glow: 'shadow-cyan-500/50',
  },
  {
    icon: Activity,
    title: 'Physics Motion Tracking',
    description: 'Track velocity, acceleration, and trajectory in real-time',
    color: 'from-blue-500 to-violet-500',
    glow: 'shadow-blue-500/50',
  },
  {
    icon: Bot,
    title: 'AI STEM Tutor',
    description: 'Get personalized explanations and guidance 24/7',
    color: 'from-violet-500 to-purple-500',
    glow: 'shadow-violet-500/50',
  },
  {
    icon: Mic,
    title: 'Voice Learning Assistant',
    description: 'Speak naturally and get instant AI responses',
    color: 'from-teal-500 to-cyan-500',
    glow: 'shadow-teal-500/50',
  },
  {
    icon: Box,
    title: 'Digital Twin Simulations',
    description: 'Create virtual replicas of real-world experiments',
    color: 'from-orange-500 to-amber-500',
    glow: 'shadow-orange-500/50',
  },
  {
    icon: Route,
    title: 'Personalized Learning Paths',
    description: 'AI adapts to your pace and learning style',
    color: 'from-green-500 to-emerald-500',
    glow: 'shadow-green-500/50',
  },
  {
    icon: Zap,
    title: 'STEM Challenges',
    description: 'Compete in real-world problem-solving challenges',
    color: 'from-pink-500 to-rose-500',
    glow: 'shadow-pink-500/50',
  },
  {
    icon: Trophy,
    title: 'Achievement System',
    description: 'Earn badges, XP, and climb the leaderboard',
    color: 'from-yellow-500 to-orange-500',
    glow: 'shadow-yellow-500/50',
  },
];

export default function FeatureSection() {
  return (
    <section className="relative py-32 overflow-hidden">
      <div className="absolute inset-0 bg-gradient-to-b from-[#0a0a1a] via-[#0d0d20] to-[#0a0a1a]" />

      <div className="relative container mx-auto px-6">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="text-center mb-20"
        >
          <motion.span className="text-cyan-400 font-semibold text-lg">
            Features
          </motion.span>
          <h2 className="text-4xl md:text-6xl font-bold text-white mt-4 mb-6">
            Everything You Need to{' '}
            <span className="bg-clip-text text-transparent bg-gradient-to-r from-cyan-400 to-blue-400">
              Master STEM
            </span>
          </h2>
          <p className="text-gray-400 text-xl max-w-2xl mx-auto">
            Powerful AI tools designed to transform how you learn science and engineering
          </p>
        </motion.div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {features.map((feature, index) => (
            <motion.div
              key={index}
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: index * 0.1 }}
              whileHover={{
                y: -10,
                scale: 1.02,
                transition: { duration: 0.3 },
              }}
              className="group relative"
            >
              <div className="absolute inset-0 bg-gradient-to-r opacity-0 group-hover:opacity-100 blur-xl transition-opacity duration-500 -z-10" />

              <div className="relative h-full p-6 bg-white/5 backdrop-blur-sm rounded-2xl border border-white/10 hover:border-white/20 transition-all duration-300">
                {/* Icon container */}
                <motion.div
                  whileHover={{ scale: 1.1, rotate: 5 }}
                  className={`w-14 h-14 rounded-xl bg-gradient-to-r ${feature.color} flex items-center justify-center mb-4 group-hover:shadow-lg ${feature.glow} transition-shadow duration-300`}
                >
                  <feature.icon className="w-7 h-7 text-white" />
                </motion.div>

                <h3 className="text-xl font-semibold text-white mb-2 group-hover:text-cyan-300 transition-colors">
                  {feature.title}
                </h3>

                <p className="text-gray-400 group-hover:text-gray-300 transition-colors">
                  {feature.description}
                </p>

                {/* Hover glow effect */}
                <motion.div
                  className="absolute inset-0 rounded-2xl bg-gradient-to-r from-cyan-500/0 to-blue-500/0 group-hover:from-cyan-500/5 group-hover:to-blue-500/5 transition-all duration-300"
                />
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
