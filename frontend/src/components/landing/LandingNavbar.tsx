import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import { Menu, X, Sparkles, Github, FlaskConical, LayoutDashboard, LogIn } from 'lucide-react';

interface LandingNavbarProps {
  onLaunchLab: () => void;
}

export default function LandingNavbar({ onLaunchLab }: LandingNavbarProps) {
  const navigate = useNavigate();
  const [scrolled, setScrolled] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [isAuthenticated, setIsAuthenticated] = useState(false);

  useEffect(() => {
    const handleScroll = () => {
      setScrolled(window.scrollY > 20);
    };
    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  useEffect(() => {
    const session = localStorage.getItem('neurolab_session');
    setIsAuthenticated(!!session);
  }, []);

  const navLinks = [
    { label: 'Features', route: '/features' },
    { label: 'Live Lab', route: '/live-lab' },
    { label: 'AI Tutor', route: '/ai-tutor' },
    { label: 'Pricing', route: '/pricing' },
    { label: 'Articles', route: '/blog' },
    { label: 'Docs', route: '/docs' },
  ];

  return (
    <header
      className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${
        scrolled
          ? 'bg-[#070714]/90 backdrop-blur-xl border-b border-white/10 shadow-lg shadow-black/40 py-3'
          : 'bg-transparent py-5'
      }`}
    >
      <div className="max-w-7xl mx-auto px-6 flex items-center justify-between">
        {/* Brand Logo */}
        <div
          onClick={() => navigate('/')}
          className="flex items-center gap-3 cursor-pointer group"
        >
          <div className="w-9 h-9 rounded-xl flex items-center justify-center shadow-lg shadow-cyan-500/20 overflow-hidden bg-[#050511] border border-cyan-500/30 group-hover:border-cyan-400 transition-all">
            <img
              src={`${import.meta.env.BASE_URL}logo.png`}
              alt="NeuroLab Logo"
              className="w-full h-full object-cover"
            />
          </div>
          <div className="flex flex-col text-left">
            <span className="text-lg font-black bg-clip-text text-transparent bg-gradient-to-r from-cyan-400 via-blue-400 to-indigo-400">
              NeuroLab AI
            </span>
            <span className="text-[9px] uppercase tracking-wider text-cyan-400 font-bold -mt-1">
              Interactive STEM
            </span>
          </div>
        </div>

        {/* Desktop Navigation Links */}
        <nav className="hidden md:flex items-center gap-1 bg-white/[0.03] border border-white/5 px-4 py-1.5 rounded-full backdrop-blur-md">
          {navLinks.map((link) => (
            <button
              key={link.label}
              onClick={() => navigate(link.route)}
              className="px-3.5 py-1.5 rounded-full text-xs font-medium text-gray-300 hover:text-white hover:bg-white/5 transition-all"
            >
              {link.label}
            </button>
          ))}
        </nav>

        {/* Action Buttons */}
        <div className="hidden md:flex items-center gap-3">
          <a
            href="https://github.com/vikassaini77/AI-Steam-Lab"
            target="_blank"
            rel="noopener noreferrer"
            className="p-2 rounded-xl border border-white/10 bg-white/5 hover:bg-white/10 text-gray-300 hover:text-white transition-all"
            title="GitHub Repository"
          >
            <Github className="w-4 h-4" />
          </a>

          {isAuthenticated ? (
            <button
              onClick={() => navigate('/dashboard')}
              className="px-4 py-2 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 text-white font-semibold text-xs flex items-center gap-1.5 transition-all"
            >
              <LayoutDashboard className="w-3.5 h-3.5 text-cyan-400" />
              Dashboard
            </button>
          ) : (
            <button
              onClick={() => navigate('/auth')}
              className="px-4 py-2 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 text-white font-semibold text-xs flex items-center gap-1.5 transition-all"
            >
              <LogIn className="w-3.5 h-3.5 text-cyan-400" />
              Sign In
            </button>
          )}

          <button
            onClick={onLaunchLab}
            className="px-4 py-2 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-white font-bold text-xs shadow-md shadow-cyan-500/25 hover:shadow-cyan-500/40 hover:scale-[1.02] active:scale-[0.98] transition-all flex items-center gap-1.5"
          >
            <FlaskConical className="w-3.5 h-3.5 fill-current" />
            Launch Lab
          </button>
        </div>

        {/* Mobile Hamburger Toggle */}
        <button
          onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
          className="md:hidden p-2 rounded-xl border border-white/10 bg-white/5 text-gray-300 hover:text-white"
        >
          {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
        </button>
      </div>

      {/* Mobile Drawer */}
      <AnimatePresence>
        {mobileMenuOpen && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="md:hidden bg-[#070714]/95 border-b border-white/10 backdrop-blur-2xl px-6 py-6 space-y-4"
          >
            <div className="flex flex-col space-y-2">
              {navLinks.map((link) => (
                <button
                  key={link.label}
                  onClick={() => {
                    setMobileMenuOpen(false);
                    navigate(link.route);
                  }}
                  className="w-full text-left px-4 py-2.5 rounded-xl text-sm font-medium text-gray-300 hover:text-white hover:bg-white/5 transition-all"
                >
                  {link.label}
                </button>
              ))}
            </div>

            <div className="pt-4 border-t border-white/10 flex flex-col gap-3">
              {isAuthenticated ? (
                <button
                  onClick={() => {
                    setMobileMenuOpen(false);
                    navigate('/dashboard');
                  }}
                  className="w-full py-2.5 rounded-xl bg-white/5 border border-white/10 text-white text-xs font-semibold flex items-center justify-center gap-2"
                >
                  <LayoutDashboard className="w-4 h-4 text-cyan-400" />
                  Dashboard
                </button>
              ) : (
                <button
                  onClick={() => {
                    setMobileMenuOpen(false);
                    navigate('/auth');
                  }}
                  className="w-full py-2.5 rounded-xl bg-white/5 border border-white/10 text-white text-xs font-semibold flex items-center justify-center gap-2"
                >
                  <LogIn className="w-4 h-4 text-cyan-400" />
                  Sign In
                </button>
              )}

              <button
                onClick={() => {
                  setMobileMenuOpen(false);
                  onLaunchLab();
                }}
                className="w-full py-2.5 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 text-white text-xs font-bold shadow-lg shadow-cyan-500/25 flex items-center justify-center gap-2"
              >
                <Sparkles className="w-4 h-4" />
                Launch Live Lab
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </header>
  );
}

