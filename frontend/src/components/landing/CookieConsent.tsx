import { motion, AnimatePresence } from 'framer-motion';
import { useState, useEffect } from 'react';
import { ShieldCheck, Settings, Eye, HelpCircle } from 'lucide-react';

export default function CookieConsent() {
  const [visible, setVisible] = useState<boolean>(false);
  const [showCustomize, setShowCustomize] = useState<boolean>(false);
  const [essential, setEssential] = useState<boolean>(true);
  const [analytics, setAnalytics] = useState<boolean>(true);
  const [personalization, setPersonalization] = useState<boolean>(false);

  useEffect(() => {
    const consent = localStorage.getItem('neurolab_cookie_consent');
    if (!consent) {
      // Show banner after 2 seconds
      const timer = setTimeout(() => setVisible(true), 2500);
      return () => clearTimeout(timer);
    }
  }, []);

  const handleAcceptAll = () => {
    localStorage.setItem('neurolab_cookie_consent', JSON.stringify({ essential: true, analytics: true, personalization: true }));
    setVisible(false);
  };

  const handleRejectNonEssential = () => {
    localStorage.setItem('neurolab_cookie_consent', JSON.stringify({ essential: true, analytics: false, personalization: false }));
    setVisible(false);
  };

  const handleSavePreferences = () => {
    localStorage.setItem('neurolab_cookie_consent', JSON.stringify({ essential, analytics, personalization }));
    setVisible(false);
  };

  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          initial={{ opacity: 0, y: 100, scale: 0.95 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: 50, scale: 0.95 }}
          transition={{ type: 'spring', damping: 20 }}
          className="fixed bottom-6 left-6 right-6 md:left-auto md:max-w-md z-[200] bg-[#0d0d20]/95 backdrop-blur-2xl border border-white/10 rounded-2xl p-5 shadow-2xl text-left"
        >
          <div className="space-y-4">
            {/* Header */}
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center text-cyan-400">
                <ShieldCheck className="w-5 h-5" />
              </div>
              <div>
                <h4 className="text-sm font-black text-white tracking-wide">Cookie Consent & Privacy</h4>
                <p className="text-[10px] text-gray-400">We optimize your STEM learning environments.</p>
              </div>
            </div>

            {/* Main description */}
            <p className="text-xs text-gray-300 leading-relaxed">
              NeuroLab AI uses secure local cookies and token headers to authenticate student sessions, save theme accents, and track daily physics achievements.
            </p>

            {/* Customization Details drawer */}
            <AnimatePresence>
              {showCustomize && (
                <motion.div
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: 'auto', opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  className="space-y-3 pt-3 border-t border-white/5 overflow-hidden"
                >
                  <div className="space-y-2">
                    {/* Essential */}
                    <div className="flex justify-between items-center bg-white/[0.02] p-2.5 rounded-xl border border-white/5">
                      <div>
                        <h5 className="text-[11px] font-bold text-white flex items-center gap-1">
                          Essential Cookies
                          <span className="text-[8px] px-1 bg-cyan-500/10 text-cyan-400 rounded uppercase font-black">Required</span>
                        </h5>
                        <p className="text-[9px] text-gray-500 mt-0.5">Persistent credentials and proxy sessions.</p>
                      </div>
                      <div className="w-8 h-4 rounded-full bg-cyan-500/40 p-0.5 cursor-not-allowed">
                        <div className="w-3 h-3 bg-cyan-400 rounded-full translate-x-4" />
                      </div>
                    </div>

                    {/* Analytics */}
                    <div className="flex justify-between items-center bg-white/[0.02] p-2.5 rounded-xl border border-white/5">
                      <div>
                        <h5 className="text-[11px] font-bold text-white">Physics Metrics Analytics</h5>
                        <p className="text-[9px] text-gray-500 mt-0.5">Saves speed, angular ratios, and calibration logs.</p>
                      </div>
                      <button
                        type="button"
                        onClick={() => setAnalytics(!analytics)}
                        className={`w-8 h-4.5 rounded-full p-0.5 transition-all ${analytics ? 'bg-cyan-500' : 'bg-white/10'}`}
                      >
                        <div className={`w-3.5 h-3.5 bg-white rounded-full transition-all ${analytics ? 'translate-x-3.5' : 'translate-x-0'}`} />
                      </button>
                    </div>

                    {/* Personalization */}
                    <div className="flex justify-between items-center bg-white/[0.02] p-2.5 rounded-xl border border-white/5">
                      <div>
                        <h5 className="text-[11px] font-bold text-white">AI Tutor Preferences</h5>
                        <p className="text-[9px] text-gray-500 mt-0.5">Remembers voice outputs and assistant speed.</p>
                      </div>
                      <button
                        type="button"
                        onClick={() => setPersonalization(!personalization)}
                        className={`w-8 h-4.5 rounded-full p-0.5 transition-all ${personalization ? 'bg-cyan-500' : 'bg-white/10'}`}
                      >
                        <div className={`w-3.5 h-3.5 bg-white rounded-full transition-all ${personalization ? 'translate-x-3.5' : 'translate-x-0'}`} />
                      </button>
                    </div>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>

            {/* Actions Buttons */}
            <div className="flex flex-col gap-2 pt-2 border-t border-white/5">
              {!showCustomize ? (
                <>
                  <div className="flex gap-2">
                    <button
                      onClick={handleAcceptAll}
                      className="flex-1 py-2 bg-gradient-to-r from-cyan-500 to-blue-600 text-white text-xs font-bold rounded-xl transition-all"
                    >
                      Accept All
                    </button>
                    <button
                      onClick={handleRejectNonEssential}
                      className="flex-1 py-2 bg-white/5 border border-white/10 text-gray-300 hover:text-white text-xs font-bold rounded-xl transition-all"
                    >
                      Essential Only
                    </button>
                  </div>
                  <button
                    onClick={() => setShowCustomize(true)}
                    className="py-1.5 text-center text-[10px] text-cyan-400 hover:text-cyan-300 font-bold flex items-center justify-center gap-1"
                  >
                    <Settings className="w-3 h-3" />
                    Customize Cookie Preferences
                  </button>
                </>
              ) : (
                <div className="flex gap-2">
                  <button
                    onClick={handleSavePreferences}
                    className="flex-1 py-2 bg-gradient-to-r from-cyan-500 to-blue-600 text-white text-xs font-bold rounded-xl"
                  >
                    Save Preferences
                  </button>
                  <button
                    onClick={() => setShowCustomize(false)}
                    className="px-4 py-2 bg-white/5 border border-white/10 text-gray-300 text-xs font-bold rounded-xl"
                  >
                    Cancel
                  </button>
                </div>
              )}
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
