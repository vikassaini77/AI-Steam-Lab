import { motion } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, Target, Eye, AlertCircle, Compass } from 'lucide-react';

export default function AboutPage() {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-[#070714] text-white relative overflow-hidden">
      {/* Background gradients */}
      <div className="absolute inset-0 z-0 pointer-events-none">
        <div className="absolute top-0 left-1/3 w-[500px] h-[500px] bg-cyan-500/5 rounded-full blur-3xl" />
        <div className="absolute bottom-0 right-1/3 w-[500px] h-[500px] bg-purple-500/5 rounded-full blur-3xl" />
      </div>

      <div className="relative z-10 max-w-4xl mx-auto px-6 py-16">
        {/* Back */}
        <button onClick={() => navigate(-1)} className="flex items-center gap-2 text-gray-400 hover:text-white transition-colors text-sm mb-10 group">
          <ArrowLeft className="w-4 h-4 group-hover:-translate-x-0.5 transition-transform" />
          Back
        </button>

        {/* Header */}
        <div className="text-center space-y-4 mb-16">
          <motion.div
            initial={{ scale: 0.8, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-cyan-500/15 border border-cyan-500/30 text-cyan-400 mb-2"
          >
            <Compass className="w-7 h-7" />
          </motion.div>
          <h1 className="text-4xl md:text-5xl font-black tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-cyan-400 to-blue-500">
            Our Story & Mission
          </h1>
          <p className="text-gray-400 text-base max-w-2xl mx-auto leading-relaxed">
            Pioneering the future of interactive AI-driven scientific laboratories.
          </p>
        </div>

        {/* Story Section */}
        <div className="space-y-12 mb-16">
          <div className="prose prose-invert max-w-none text-gray-300 text-sm leading-relaxed space-y-4">
            <h3 className="text-white font-bold text-lg">Why NeuroLab AI Exists</h3>
            <p>
              Traditional science education is often restricted by either cost or simulation limits. 
              Students are forced to choose between expensive, resource-heavy hardware set-ups or flat, un-engaging 2D mock screen illustrations.
            </p>
            <p>
              NeuroLab AI was born out of a simple, disruptive idea: **What if a student could use simple household objects, their laptop camera, and advanced on-device computer vision to sync physical experiments directly with an active, predictive Digital Twin simulation?**
            </p>
          </div>

          {/* Mission & Vision Grid */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="p-5 rounded-2xl border border-white/5 bg-white/[0.02] space-y-3">
              <div className="w-9 h-9 rounded-lg bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center text-cyan-400">
                <Target className="w-4 h-4" />
              </div>
              <h4 className="text-white font-bold text-sm">Our Mission</h4>
              <p className="text-gray-400 text-xs leading-relaxed">
                Democratizing high-level science laboratories by making predictive mathematical engines and computer vision accessible to every school.
              </p>
            </div>

            <div className="p-5 rounded-2xl border border-white/5 bg-white/[0.02] space-y-3">
              <div className="w-9 h-9 rounded-lg bg-purple-500/10 border border-purple-500/20 flex items-center justify-center text-purple-400">
                <Eye className="w-4 h-4" />
              </div>
              <h4 className="text-white font-bold text-sm">Our Vision</h4>
              <p className="text-gray-400 text-xs leading-relaxed">
                Empowering students to gain physical intuition, earn achievements, and review experiments alongside a voice-enabled AI scientist.
              </p>
            </div>

            <div className="p-5 rounded-2xl border border-white/5 bg-white/[0.02] space-y-3">
              <div className="w-9 h-9 rounded-lg bg-amber-500/10 border border-amber-500/20 flex items-center justify-center text-amber-400">
                <AlertCircle className="w-4 h-4" />
              </div>
              <h4 className="text-white font-bold text-sm">Problem Solved</h4>
              <p className="text-gray-400 text-xs leading-relaxed">
                Eliminating expensive lab setup budgets and boring digital worksheets by creating a gamified, beautiful, real-world educational experience.
              </p>
            </div>
          </div>
        </div>

        {/* Founders / Core Team Quote */}
        <div className="p-8 bg-white/[0.01] border border-white/5 rounded-3xl relative overflow-hidden text-center">
          <div className="absolute inset-0 bg-scanlines opacity-[0.05] pointer-events-none" />
          <span className="text-cyan-400 text-4xl font-serif">“</span>
          <p className="text-gray-300 italic text-sm max-w-xl mx-auto leading-relaxed mb-4">
            "We believe true scientific interest begins at the intersection of observation and play. NeuroLab is designed to give every child a voice-enabled STEM lab right in their home."
          </p>
          <h5 className="text-white font-bold text-xs">The NeuroLab AI Team</h5>
          <span className="text-gray-500 text-[10px]">Pioneering Interactive Laboratories</span>
        </div>
      </div>
    </div>
  );
}


