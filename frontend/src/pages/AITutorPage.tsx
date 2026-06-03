import { motion } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, Sparkles, Volume2, Mic, Play, ArrowRight, ShieldCheck, Heart } from 'lucide-react';
import AITutorPanel from '../components/ai-tutor/AITutorPanel';

export default function AITutorPage() {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-[#070714] text-white relative overflow-hidden">
      {/* Dynamic scanning overlays */}
      <div className="absolute inset-0 bg-scanlines opacity-[0.03] pointer-events-none" />
      
      <div className="absolute inset-0 z-0 pointer-events-none">
        <div className="absolute top-0 left-1/4 w-[500px] h-[500px] bg-cyan-500/5 rounded-full blur-3xl" />
        <div className="absolute bottom-0 right-1/4 w-[500px] h-[500px] bg-purple-600/5 rounded-full blur-3xl" />
      </div>

      <div className="relative z-10 max-w-6xl mx-auto px-6 py-16">
        {/* Back */}
        <button onClick={() => navigate('/')} className="flex items-center gap-2 text-gray-400 hover:text-white transition-colors text-sm mb-10 group">
          <ArrowLeft className="w-4 h-4 group-hover:-translate-x-0.5 transition-transform" />
          Back to Home
        </button>

        {/* Content Layout: Left Intro, Right Live Chat Panel */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-10 items-center">
          
          {/* Left Block: Presentation */}
          <div className="lg:col-span-5 space-y-6 text-left">
            <motion.div
              initial={{ scale: 0.8, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              className="inline-flex items-center justify-center w-12 h-12 rounded-xl bg-cyan-500/10 border border-cyan-500/20 text-cyan-400"
            >
              <Sparkles className="w-6 h-6 animate-pulse" />
            </motion.div>
            
            <h1 className="text-3xl md:text-4xl font-black leading-tight bg-clip-text text-transparent bg-gradient-to-r from-cyan-400 via-blue-400 to-purple-400">
              Meet Professor Nova, Your Voice-Guided STEM Mentor
            </h1>
            
            <p className="text-gray-400 text-xs leading-relaxed">
              Professor Nova combines Gemini generative context with your active physical laboratory measurements to explain complex scientific constants.
            </p>

            <div className="space-y-4 pt-2">
              <div className="flex gap-3 items-start text-xs">
                <Volume2 className="w-5 h-5 text-cyan-400 shrink-0 mt-0.5" />
                <div>
                  <h4 className="text-white font-bold">SpeechSynthesis Math Output</h4>
                  <p className="text-gray-500 text-[11px]">Nova cleans LaTeX markers and speaks mathematical formulas in fluid, natural accents.</p>
                </div>
              </div>

              <div className="flex gap-3 items-start text-xs">
                <ShieldCheck className="w-5 h-5 text-purple-400 shrink-0 mt-0.5" />
                <div>
                  <h4 className="text-white font-bold">Grounded Lab Context</h4>
                  <p className="text-gray-500 text-[11px]">Nova directly inspects velocities, angles, and conservation values from your camera streams.</p>
                </div>
              </div>
            </div>

            <div className="pt-4">
              <button onClick={() => navigate('/')} className="px-5 py-3 bg-gradient-to-r from-cyan-500 to-blue-600 rounded-xl text-white font-bold text-xs shadow-lg shadow-cyan-500/20 hover:shadow-cyan-500/35 hover:scale-[1.02] active:scale-[0.98] transition-all flex items-center gap-1">
                Launch Complete Live Lab
                <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* Right Block: Live Tutor Sandbox Container */}
          <div className="lg:col-span-7 bg-[#12121a] border border-[#22222f] rounded-3xl overflow-hidden shadow-2xl relative">
            <div className="absolute top-4 right-4 z-20 flex gap-1.5">
              <span className="px-2 py-0.5 bg-cyan-500/10 border border-cyan-500/20 text-[8px] font-extrabold text-cyan-400 rounded-md uppercase tracking-wider">AI Sandbox</span>
            </div>
            <AITutorPanel />
          </div>

        </div>
      </div>
    </div>
  );
}
