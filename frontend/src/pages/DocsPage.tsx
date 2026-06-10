import { motion } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import { useState } from 'react';
import { ArrowLeft, BookOpen, ChevronRight, Play, Cpu, Sparkles, Shield, User, HelpCircle } from 'lucide-react';

export default function DocsPage() {
  const navigate = useNavigate();
  const [activeSection, setActiveSection] = useState<'getting-started' | 'experiments' | 'tutor' | 'reports' | 'account' | 'faq'>('getting-started');

  const docNav = [
    { id: 'getting-started', label: 'Getting Started', icon: Play },
    { id: 'experiments', label: 'Physics Experiments', icon: Cpu },
    { id: 'tutor', label: 'AI Nova Tutor', icon: Sparkles },
    { id: 'reports', label: 'Scientific Reports', icon: Shield },
    { id: 'account', label: 'Account Setup', icon: User },
    { id: 'faq', label: 'Frequently Asked Questions', icon: HelpCircle }
  ] as const;

  return (
    <div className="min-h-screen bg-[#070714] text-white relative overflow-x-hidden">
      {/* Gradients */}
      <div className="absolute inset-0 z-0 pointer-events-none">
        <div className="absolute top-0 left-1/4 w-[400px] h-[400px] bg-cyan-500/5 rounded-full blur-3xl" />
        <div className="absolute bottom-0 right-1/4 w-[400px] h-[400px] bg-blue-500/5 rounded-full blur-3xl" />
      </div>

      <div className="relative z-10 max-w-5xl mx-auto px-6 py-16">
        {/* Back */}
        <button onClick={() => navigate(-1)} className="flex items-center gap-2 text-gray-400 hover:text-white transition-colors text-sm mb-10 group">
          <ArrowLeft className="w-4 h-4 group-hover:-translate-x-0.5 transition-transform" />
          Back
        </button>

        {/* Header */}
        <div className="flex items-center gap-4 mb-12">
          <div className="w-12 h-12 rounded-xl bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center text-cyan-400">
            <BookOpen className="w-6 h-6" />
          </div>
          <div>
            <h1 className="text-3xl font-black bg-clip-text text-transparent bg-gradient-to-r from-cyan-400 to-blue-400">
              Documentation Center
            </h1>
            <p className="text-gray-500 text-xs mt-0.5">Explore guides, experiment calibration, and FAQ setups.</p>
          </div>
        </div>

        {/* Sidebar & Content Layout */}
        <div className="grid grid-cols-1 md:grid-cols-12 gap-8">
          {/* Sidebar */}
          <div className="md:col-span-4 space-y-2">
            {docNav.map((item) => {
              const IconComp = item.icon;
              return (
                <button
                  key={item.id}
                  onClick={() => setActiveSection(item.id)}
                  className={`w-full flex items-center justify-between p-3 rounded-xl border text-xs font-bold transition-all ${
                    activeSection === item.id
                      ? 'bg-gradient-to-r from-cyan-500/10 to-blue-500/10 border-cyan-500/40 text-cyan-400'
                      : 'bg-white/[0.01] border-white/5 text-gray-400 hover:text-white hover:bg-white/[0.03]'
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <IconComp className="w-4 h-4 flex-shrink-0" />
                    <span>{item.label}</span>
                  </div>
                  <ChevronRight className={`w-3.5 h-3.5 transition-transform ${activeSection === item.id ? 'translate-x-0.5' : ''}`} />
                </button>
              );
            })}
          </div>

          {/* Content Pane */}
          <div className="md:col-span-8 bg-white/[0.02] border border-white/5 rounded-2xl p-6 min-h-[350px]">
            {activeSection === 'getting-started' && (
              <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-4">
                <h3 className="text-lg font-bold text-white border-b border-white/5 pb-2">🚀 Getting Started with NeuroLab</h3>
                <p className="text-gray-400 text-xs leading-relaxed">
                  Welcome to NeuroLab AI, a high-fidelity virtual STEM laboratory syncing physical observations with simulated twins.
                </p>
                <div className="space-y-2">
                  <h4 className="text-white text-xs font-extrabold uppercase tracking-wide">Quick Start Steps:</h4>
                  <ol className="list-decimal list-inside text-gray-400 text-xs space-y-2 leading-relaxed">
                    <li>Create an account or log in via Supabase Auth.</li>
                    <li>Launch the <strong className="text-white">Live Lab Dashboard</strong> screen.</li>
                    <li>Toggle the <strong className="text-white">Webcam Permission</strong> bar (processed 100% locally).</li>
                    <li>Mount or hold a target bob (like a colored ball) and start calibration parameters!</li>
                  </ol>
                </div>
              </motion.div>
            )}

            {activeSection === 'experiments' && (
              <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-4">
                <h3 className="text-lg font-bold text-white border-b border-white/5 pb-2">🕰️ Physics Experiments Guide</h3>
                <p className="text-gray-400 text-xs leading-relaxed">
                  NeuroLab AI features advanced mathematical engines to compute projectile arcs, free fall damping, and simple harmonic oscillations.
                </p>
                <div className="space-y-3">
                  <div className="p-3 bg-white/[0.02] rounded-xl border border-white/5">
                    <span className="text-xs text-cyan-400 font-bold">1. Simple Pendulum Harmonic Motion</span>
                    <p className="text-gray-500 text-[11px] mt-1">
                      Tracks bob amplitude, swing periods, and string lengths ({"$T = 2\\pi\\sqrt{L/g}$"}) utilizing computer vision color bounding trackers.
                    </p>
                  </div>
                  <div className="p-3 bg-white/[0.02] rounded-xl border border-white/5">
                    <span className="text-xs text-purple-400 font-bold">2. Parabolic Projectile Trajectories</span>
                    <p className="text-gray-500 text-[11px] mt-1">
                      Models launched particle velocities, angles, maximum heights, and horizontal ranges with optional air damping coefficients.
                    </p>
                  </div>
                </div>
              </motion.div>
            )}

            {activeSection === 'tutor' && (
              <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-4">
                <h3 className="text-lg font-bold text-white border-b border-white/5 pb-2">🤖 Professor Nova: Voice-Enabled Scientist</h3>
                <p className="text-gray-400 text-xs leading-relaxed">
                  Professor Nova is a Gemini-powered STEM assistant that continuously reads your active experimental parameters and translates equations.
                </p>
                <ul className="list-disc list-inside text-gray-400 text-xs space-y-1.5 leading-relaxed">
                  <li>Features standard <strong className="text-white">HTML5 SpeechSynthesis</strong> for vocal STEM lectures.</li>
                  <li>Automatically cleans LaTeX syntax for elegant vocalized equations.</li>
                  <li>Suggests clickable inquiries based on active physics metrics (Kinetic and Potential energy balance).</li>
                </ul>
              </motion.div>
            )}

            {activeSection === 'reports' && (
              <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-4">
                <h3 className="text-lg font-bold text-white border-b border-white/5 pb-2">🛡️ Scientific PDF Reports</h3>
                <p className="text-gray-400 text-xs leading-relaxed">
                  At the click of a button, our Python FastAPI server uses ReportLab and Matplotlib to compile academic scientific reports.
                </p>
                <div className="p-3 bg-emerald-500/10 border border-emerald-500/20 rounded-xl text-xs text-emerald-300">
                  📄 Fully compiled documents include dark-themed energy curves, complete calibration matrices, and Professor Nova's notes.
                </div>
              </motion.div>
            )}

            {activeSection === 'account' && (
              <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-4">
                <h3 className="text-lg font-bold text-white border-b border-white/5 pb-2">👤 Account Setup & Security</h3>
                <p className="text-gray-400 text-xs leading-relaxed">
                  All logins and credentials profiles are securely stored using Supabase Auth DB wraps with local offline JSON database resilience fallbacks.
                </p>
                <p className="text-gray-400 text-xs leading-relaxed">
                  Navigate to your profile to edit your name, level, school credentials, streaks, or delete your account data.
                </p>
              </motion.div>
            )}

            {activeSection === 'faq' && (
              <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-3">
                <h3 className="text-lg font-bold text-white border-b border-white/5 pb-2">❓ FAQ Setup</h3>
                
                <div className="space-y-2.5">
                  <div>
                    <h4 className="text-white font-bold text-xs">Do I need hardware accessories to run the lab?</h4>
                    <p className="text-gray-500 text-[11px]">No! Use simple household objects (like a red apple or a stringed keys ring) for the CV tracking.</p>
                  </div>
                  <div>
                    <h4 className="text-white font-bold text-xs">Is my camera feed safe?</h4>
                    <p className="text-gray-500 text-[11px]">Absolutely! All frames are processed locally inside your web browser. No camera feed ever hits our servers.</p>
                  </div>
                </div>
              </motion.div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}


