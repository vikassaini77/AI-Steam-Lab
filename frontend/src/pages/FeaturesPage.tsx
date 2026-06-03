import { motion } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, Sparkles, Camera, Cpu, Zap, CheckCircle2, BarChart2, ShieldCheck, Award, GraduationCap } from 'lucide-react';

export default function FeaturesPage() {
  const navigate = useNavigate();

  const features = [
    {
      icon: GraduationCap,
      title: "Professor Nova: AI STEM Tutor",
      desc: "Our conversational AI science mentor speaks equations, clarifies complex parameters, and guides students step-by-step using advanced HTML5 text-to-speech audio outputs."
    },
    {
      icon: Camera,
      title: "Interactive Live Lab",
      desc: "Connect your webcam directly to access real-time particle, projectile, and pendulum tracking. No cloud frame storage needed—fully secure on-device processing."
    },
    {
      icon: Cpu,
      title: "OpenCV Computer Vision",
      desc: "High-accuracy HSV color filtering and deep learning YOLOv8 neural network models track physics objects and estimate speed vectors instantly."
    },
    {
      icon: Zap,
      title: "Dynamic Digital Twin",
      desc: "Side-by-side virtual simulator mirrors physical motion parameters. Tweak gravity or string length and watch the virtual twin adapt to alien conditions."
    },
    {
      icon: CheckCircle2,
      title: "CV Experiment Verification",
      desc: "Automatic algorithmic checklist scores experiments. Checks object detection, path trajectories, and physical constraints before awarding XP."
    },
    {
      icon: ShieldCheck,
      title: "ReportLab AI Reports",
      desc: "One-click scientific PDF compiler utilizes ReportLab and Matplotlib to compile beautiful trajectory graphs, metrics tables, and Nova's reviews."
    },
    {
      icon: Award,
      title: "STEM Gamification Hub",
      desc: "Earn XP streaks, level up, and unlock rare badges (like Gravity Pioneer) that showcase your mastery of kinematics and dynamics."
    },
    {
      icon: BarChart2,
      title: "Advanced Learning Analytics",
      desc: "Continuous trajectory graphs map kinetic versus potential energy conservation, providing granular mathematical feedback instantly."
    }
  ];

  return (
    <div className="min-h-screen bg-[#070714] text-white relative overflow-hidden">
      {/* Grid background */}
      <div className="absolute inset-0 z-0 pointer-events-none">
        <div className="absolute top-0 left-1/4 w-[500px] h-[500px] bg-cyan-500/5 rounded-full blur-3xl" />
        <div className="absolute bottom-0 right-1/4 w-[500px] h-[500px] bg-violet-600/5 rounded-full blur-3xl" />
        <div className="absolute inset-0 opacity-[0.02]" style={{
          backgroundImage: 'linear-gradient(rgba(6,182,212,0.4) 1px, transparent 1px), linear-gradient(90deg, rgba(6,182,212,0.4) 1px, transparent 1px)',
          backgroundSize: '60px 60px'
        }} />
      </div>

      <div className="relative z-10 max-w-5xl mx-auto px-6 py-16">
        {/* Back */}
        <button onClick={() => navigate('/')} className="flex items-center gap-2 text-gray-400 hover:text-white transition-colors text-sm mb-10 group">
          <ArrowLeft className="w-4 h-4 group-hover:-translate-x-0.5 transition-transform" />
          Back to Home
        </button>

        {/* Header */}
        <div className="text-center space-y-4 mb-16">
          <motion.div
            initial={{ scale: 0.8, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-cyan-500/15 border border-cyan-500/30 text-cyan-400 mb-2"
          >
            <Sparkles className="w-7 h-7" />
          </motion.div>
          <h1 className="text-4xl md:text-5xl font-black tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-cyan-400 via-blue-400 to-purple-400">
            NeuroLab Platform Features
          </h1>
          <p className="text-gray-400 text-base max-w-2xl mx-auto leading-relaxed">
            Discover the state-of-the-art technologies powering our premium AI STEM Laboratory.
          </p>
        </div>

        {/* Features grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-16">
          {features.map((f, i) => (
            <motion.div
              key={f.title}
              initial={{ opacity: 0, y: 15 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.05 }}
              className="p-6 rounded-2xl border border-white/5 bg-white/[0.02] hover:bg-white/[0.04] hover:border-cyan-500/25 transition-all group"
            >
              <div className="w-11 h-11 rounded-xl bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center text-cyan-400 mb-4 group-hover:bg-cyan-500/15 group-hover:border-cyan-500/40 transition-colors">
                <f.icon className="w-5 h-5" />
              </div>
              <h3 className="text-white font-bold text-lg mb-2">{f.title}</h3>
              <p className="text-gray-400 text-sm leading-relaxed">{f.desc}</p>
            </motion.div>
          ))}
        </div>

        {/* Call to action card */}
        <div className="p-8 bg-gradient-to-r from-cyan-500/10 via-blue-600/5 to-purple-600/10 border border-cyan-500/20 rounded-3xl text-center shadow-2xl relative overflow-hidden">
          <div className="absolute inset-0 bg-scanlines opacity-[0.1] pointer-events-none" />
          <h4 className="text-cyan-400 font-extrabold uppercase tracking-widest text-xs mb-2">Ready to Experiment?</h4>
          <h2 className="text-2xl font-black text-white mb-4">Start Launching Physical Live Simulations Today</h2>
          <p className="text-gray-400 text-sm max-w-xl mx-auto mb-6">
            Sign up for a free student profile or test our automated Judge Demo Mode to unlock rare badges in seconds.
          </p>
          <button onClick={() => navigate('/')} className="px-6 py-3 bg-gradient-to-r from-cyan-500 to-blue-600 rounded-xl text-white font-bold text-sm shadow-lg shadow-cyan-500/20 hover:shadow-cyan-500/40 hover:scale-[1.02] active:scale-[0.98] transition-all">
            Launch Platform Now
          </button>
        </div>
      </div>
    </div>
  );
}
