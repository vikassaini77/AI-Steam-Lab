import { motion, AnimatePresence } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import { useState } from 'react';
import { ArrowLeft, Cookie, CheckCircle2 } from 'lucide-react';

export default function CookiesPage() {
  const navigate = useNavigate();

  const [saved, setSaved] = useState(false);
  const [essential] = useState(true); // Mandatory
  const [analytical, setAnalytical] = useState(true);
  const [personalization, setPersonalization] = useState(true);

  const handleSave = () => {
    setSaved(true);
    setTimeout(() => {
      setSaved(false);
      navigate('/');
    }, 1500);
  };

  return (
    <div className="min-h-screen bg-[#070714] text-white relative overflow-hidden">
      {/* Background decoration */}
      <div className="absolute inset-0 z-0 pointer-events-none">
        <div className="absolute top-0 left-1/4 w-[400px] h-[400px] bg-cyan-500/5 rounded-full blur-3xl" />
        <div className="absolute bottom-0 right-1/4 w-[400px] h-[400px] bg-blue-500/5 rounded-full blur-3xl" />
      </div>

      <div className="relative z-10 max-w-3xl mx-auto px-6 py-16">
        {/* Back */}
        <button onClick={() => navigate('/')} className="flex items-center gap-2 text-gray-400 hover:text-white transition-colors text-sm mb-10 group">
          <ArrowLeft className="w-4 h-4 group-hover:-translate-x-0.5 transition-transform" />
          Back to Home
        </button>

        {/* Success toast */}
        <AnimatePresence>
          {saved && (
            <motion.div
              initial={{ opacity: 0, y: -50, scale: 0.9 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -20, scale: 0.95 }}
              className="fixed top-6 left-1/2 -translate-x-1/2 z-[100] bg-[#0c0c16] border border-cyan-500/35 px-6 py-4 rounded-2xl flex items-center gap-3 shadow-2xl shadow-cyan-500/10 backdrop-blur-xl"
            >
              <CheckCircle2 className="w-5 h-5 text-cyan-400" />
              <span className="text-sm font-bold text-white tracking-wide">Cookie preferences saved! 🍪</span>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Header */}
        <div className="text-center space-y-4 mb-12">
          <motion.div
            initial={{ scale: 0.8, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-cyan-500/15 border border-cyan-500/30 text-cyan-400 mb-2"
          >
            <Cookie className="w-7 h-7" />
          </motion.div>
          <h1 className="text-3xl font-black bg-clip-text text-transparent bg-gradient-to-r from-cyan-400 to-blue-400">
            Cookie Settings
          </h1>
          <p className="text-gray-400 text-xs max-w-md mx-auto leading-relaxed">
            Manage your privacy settings. Non-essential cookies are disabled by default until consented.
          </p>
        </div>

        {/* Cookie list */}
        <div className="space-y-4 mb-10 text-left">
          
          {/* Essential */}
          <div className="p-5 rounded-2xl border border-white/5 bg-white/[0.02] flex items-center justify-between gap-6">
            <div className="space-y-1">
              <h3 className="text-white font-bold text-sm">Essential Cookies</h3>
              <p className="text-gray-500 text-[11px] leading-relaxed">
                Required for core functionalities such as secure authentication sign-ins, page navigation, and security firewall. These cannot be disabled.
              </p>
            </div>
            <span className="px-3 py-1 bg-white/5 border border-white/10 rounded-lg text-gray-500 text-[10px] font-black uppercase tracking-wider select-none shrink-0">
              Mandatory
            </span>
          </div>

          {/* Analytical */}
          <div className="p-5 rounded-2xl border border-white/5 bg-white/[0.02] flex items-center justify-between gap-6">
            <div className="space-y-1">
              <h3 className="text-white font-bold text-sm">Performance & Analytics</h3>
              <p className="text-gray-500 text-[11px] leading-relaxed">
                Help us measure usage metrics, aggregate learning duration spikes, and refine our local camera frame grabbed tracking algorithms.
              </p>
            </div>
            <button
              onClick={() => setAnalytical(!analytical)}
              className={`w-12 h-6 rounded-full p-1 transition-colors flex items-center shrink-0 ${
                analytical ? 'bg-cyan-500 justify-end' : 'bg-white/10 justify-start'
              }`}
            >
              <motion.div layout className="w-4 h-4 rounded-full bg-white shadow-md" />
            </button>
          </div>

          {/* Personalization */}
          <div className="p-5 rounded-2xl border border-white/5 bg-white/[0.02] flex items-center justify-between gap-6">
            <div className="space-y-1">
              <h3 className="text-white font-bold text-sm">Personalization Cookies</h3>
              <p className="text-gray-500 text-[11px] leading-relaxed">
                Remember your custom language choices (English, Hindi, Spanish, French), dyslexia font triggers, and Professor Nova tutor mute properties.
              </p>
            </div>
            <button
              onClick={() => setPersonalization(!personalization)}
              className={`w-12 h-6 rounded-full p-1 transition-colors flex items-center shrink-0 ${
                personalization ? 'bg-cyan-500 justify-end' : 'bg-white/10 justify-start'
              }`}
            >
              <motion.div layout className="w-4 h-4 rounded-full bg-white shadow-md" />
            </button>
          </div>
        </div>

        {/* Buttons */}
        <div className="flex gap-3 justify-center">
          <button 
            onClick={() => navigate('/')} 
            className="px-6 py-3 bg-white/5 border border-white/10 rounded-xl text-gray-300 hover:text-white text-xs font-semibold hover:bg-white/8 transition-all"
          >
            Cancel
          </button>
          <button 
            onClick={handleSave}
            className="px-6 py-3 bg-gradient-to-r from-cyan-500 to-blue-600 rounded-xl text-white text-xs font-bold shadow-lg shadow-cyan-500/20 hover:shadow-cyan-500/35 hover:scale-[1.01] active:scale-[0.98] transition-all"
          >
            Save Cookie Preferences
          </button>
        </div>
      </div>
    </div>
  );
}
