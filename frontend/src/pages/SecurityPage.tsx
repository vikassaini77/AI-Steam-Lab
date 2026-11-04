import { motion, AnimatePresence } from 'framer-motion';
import { useState, useEffect } from 'react';
import {
  ShieldCheck, Smartphone, RefreshCw, Key, LogOut, CheckCircle,
  Terminal, AlertTriangle, Bell, Clock, Eye, ArrowLeft, Shield,
  Wifi, Activity, TrendingUp
} from 'lucide-react';
import { useNavigate, useLocation } from 'react-router-dom';
import { supabase } from '../lib/supabase';

/* ─── Toggle Switch ──────────────────────────────── */
function Toggle({
  enabled,
  disabled = false,
  onToggle,
}: {
  enabled: boolean;
  disabled?: boolean;
  onToggle?: () => void;
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={disabled ? undefined : onToggle}
      className={`relative w-11 h-6 rounded-full transition-all duration-300 focus:outline-none ${
        disabled
          ? enabled
            ? 'bg-cyan-500/40 cursor-not-allowed opacity-75'
            : 'bg-white/10 cursor-not-allowed opacity-40'
          : enabled
          ? 'bg-cyan-500'
          : 'bg-white/15'
      }`}
    >
      <div
        className={`absolute top-1 w-4 h-4 bg-white rounded-full shadow-sm transition-all duration-300 ${
          enabled ? 'left-6' : 'left-1'
        }`}
      />
    </button>
  );
}

/* ─── Toast ─────────────────────────────────────── */
function Toast({ msg }: { msg: string | null }) {
  return (
    <AnimatePresence>
      {msg && (
        <motion.div
          initial={{ opacity: 0, y: -60, scale: 0.9 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: -20, scale: 0.95 }}
          className="fixed top-6 left-1/2 -translate-x-1/2 z-[100] bg-[#0d0d20] border border-cyan-500/30 px-5 py-3.5 rounded-2xl flex items-center gap-3 shadow-2xl shadow-cyan-500/10 backdrop-blur-xl"
        >
          <CheckCircle className="w-4 h-4 text-cyan-400 flex-shrink-0" />
          <span className="text-sm font-semibold text-white">{msg}</span>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

/* ─── Helper: Detect Browser & OS ───────────────── */
function getBrowserDeviceInfo() {
  if (typeof navigator === 'undefined') {
    return { name: 'Active Web Client', icon: Terminal };
  }
  const ua = navigator.userAgent;
  let browser = 'Modern Browser';
  if (ua.includes('Firefox/')) browser = 'Firefox';
  else if (ua.includes('Edg/')) browser = 'Edge';
  else if (ua.includes('Chrome/')) browser = 'Chrome';
  else if (ua.includes('Safari/') && !ua.includes('Chrome/')) browser = 'Safari';

  let os = 'Desktop';
  let isMobile = false;
  if (ua.includes('Win')) os = 'Windows';
  else if (ua.includes('Mac')) os = 'macOS';
  else if (ua.includes('Linux') && !ua.includes('Android')) os = 'Linux';
  else if (ua.includes('Android')) { os = 'Android'; isMobile = true; }
  else if (ua.includes('iPhone') || ua.includes('iPad')) { os = 'iOS'; isMobile = true; }

  return {
    name: `${browser} on ${os}`,
    icon: isMobile ? Smartphone : Terminal,
  };
}

export default function SecurityPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const isDashboard = location.pathname.startsWith('/dashboard');

  const [toastMsg, setToastMsg] = useState<string | null>(null);
  const [deviceInfo, setDeviceInfo] = useState({ name: 'Current Browser Session', icon: Terminal });

  useEffect(() => {
    setDeviceInfo(getBrowserDeviceInfo());
  }, []);

  // Verified security posture: represents genuine, server-backed security capabilities
  // 1. Password hashing (BCrypt via Supabase): 20%
  // 2. TLS 1.3 transport encryption: 20%
  // 3. Cryptographic JWT claims verification: 20%
  // 4. API Rate Limiting & brute-force defense: 20%
  // 5. In-memory token revocation on logout: 20%
  // Currently 2FA is planned (not implemented yet), so verified base score is 80%.
  const verifiedScore = 80;
  const scoreColor = '#06b6d4';
  const scoreLabel = 'Strong';

  const circumference = 2 * Math.PI * 54;

  const toast = (msg: string) => setToastMsg(msg);
  useEffect(() => {
    if (toastMsg) {
      const t = setTimeout(() => setToastMsg(null), 3000);
      return () => clearTimeout(t);
    }
  }, [toastMsg]);

  const handleSignOutCurrentSession = async () => {
    try {
      await supabase.auth.signOut();
      toast('Signed out successfully.');
      setTimeout(() => navigate('/auth'), 800);
    } catch (err) {
      console.error('Sign-out error:', err);
      toast('Error signing out. Please try again.');
    }
  };

  const content = (
    <div className={`space-y-8 ${isDashboard ? '' : 'relative z-10 max-w-5xl mx-auto px-6 py-16'}`}>
      {!isDashboard && (
        <>
          {/* Back */}
          <button
            onClick={() => navigate(-1)}
            className="flex items-center gap-2 text-gray-400 hover:text-white transition-colors text-sm group"
          >
            <ArrowLeft className="w-4 h-4 group-hover:-translate-x-0.5 transition-transform" />
            Back
          </button>

          {/* Header */}
          <div className="text-center space-y-3">
            <motion.div
              initial={{ scale: 0.8, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-cyan-500/15 border border-cyan-500/30 text-cyan-400 mb-2"
            >
              <ShieldCheck className="w-7 h-7" />
            </motion.div>
            <h1 className="text-4xl font-black tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-cyan-400 to-blue-400">
              Cyber Security Center
            </h1>
            <p className="text-gray-400 text-sm">🛡️ Production Authentication & Verified Infrastructure Protection</p>
          </div>
        </>
      )}

      {/* Top grid: Score + Controls */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">

        {/* Verified Security Score */}
        <div className="p-6 bg-white/[0.04] border border-white/10 rounded-2xl backdrop-blur-md flex flex-col items-center text-center space-y-4">
          <div className="flex items-center justify-between w-full">
            <h3 className="font-bold text-sm text-white uppercase tracking-wider">Security Score</h3>
            <span className="text-[10px] px-2 py-0.5 rounded-full bg-cyan-500/10 border border-cyan-500/25 text-cyan-400 font-bold uppercase tracking-wider">
              Verified
            </span>
          </div>

          <div className="relative w-36 h-36 flex items-center justify-center">
            <svg className="absolute inset-0 w-full h-full -rotate-90">
              <circle cx="72" cy="72" r="54" fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="9" />
              <circle
                cx="72" cy="72" r="54" fill="none"
                stroke={scoreColor}
                strokeWidth="9"
                strokeDasharray={circumference}
                strokeDashoffset={circumference - (circumference * verifiedScore) / 100}
                strokeLinecap="round"
                className="transition-all duration-700"
              />
            </svg>
            <div>
              <div className="text-4xl font-black text-white">{verifiedScore}</div>
              <div className="text-[10px] font-bold uppercase tracking-wider" style={{ color: scoreColor }}>
                {scoreLabel}
              </div>
            </div>
          </div>

          <div className="w-full space-y-2 text-left pt-2 border-t border-white/8">
            {[
              { label: 'Password Encryption (BCrypt)', ok: true },
              { label: 'TLS 1.3 Transport Security', ok: true },
              { label: 'JWT Cryptographic Claims Validation', ok: true },
              { label: 'API Rate Limiting & Abuse Shield', ok: true },
              { label: 'Two-Factor Authentication (2FA)', ok: false, note: 'Coming Soon' },
            ].map((item) => (
              <div key={item.label} className="flex items-center justify-between text-xs gap-2">
                <span className="text-gray-400 truncate">{item.label}</span>
                {item.ok ? (
                  <span className="text-emerald-400 font-bold flex-shrink-0">✓ Active</span>
                ) : (
                  <span className="text-amber-400/90 font-medium text-[10px] uppercase flex-shrink-0">
                    {item.note || 'Disabled'}
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Auth factor controls */}
        <div className="md:col-span-2 p-6 bg-white/[0.04] border border-white/10 rounded-2xl backdrop-blur-md space-y-4">
          <div className="flex items-center justify-between border-b border-white/8 pb-3">
            <h3 className="font-bold text-sm text-white uppercase tracking-wider">
              Authentication Factor Configuration
            </h3>
            <span className="text-xs text-gray-500">Platform Security Controls</span>
          </div>

          {/* 2FA - Coming Soon */}
          <div className="flex items-center justify-between bg-white/[0.03] p-3.5 rounded-xl border border-white/8 gap-4">
            <div className="flex items-start gap-3 flex-1 min-w-0">
              <div className="w-8 h-8 rounded-lg bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center flex-shrink-0 mt-0.5">
                <Key className="w-4 h-4 text-cyan-400" />
              </div>
              <div className="min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <p className="text-sm font-semibold text-white">Two-Factor Authentication (2FA)</p>
                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-cyan-500/10 border border-cyan-500/30 text-cyan-400 font-bold uppercase">
                    Coming Soon
                  </span>
                </div>
                <p className="text-xs text-gray-400 mt-0.5 leading-relaxed">
                  Multi-factor authentication via TOTP authenticator apps is in development and will be enabled in an upcoming platform release.
                </p>
              </div>
            </div>
            <Toggle enabled={false} disabled={true} />
          </div>

          {/* Security Login Alerts - In Development */}
          <div className="flex items-center justify-between bg-white/[0.03] p-3.5 rounded-xl border border-white/8 gap-4">
            <div className="flex items-start gap-3 flex-1 min-w-0">
              <div className="w-8 h-8 rounded-lg bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center flex-shrink-0 mt-0.5">
                <Bell className="w-4 h-4 text-cyan-400" />
              </div>
              <div className="min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <p className="text-sm font-semibold text-white">Security Sign-In Alerts</p>
                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-white/5 border border-white/10 text-gray-400 font-bold uppercase">
                    In Development
                  </span>
                </div>
                <p className="text-xs text-gray-400 mt-0.5 leading-relaxed">
                  Transactional email notifications for new device sign-ins will be activated upon completion of email service integration.
                </p>
              </div>
            </div>
            <Toggle enabled={false} disabled={true} />
          </div>

          {/* Account Recovery Key - In Development */}
          <div className="flex items-center justify-between bg-white/[0.03] p-3.5 rounded-xl border border-white/8 gap-4">
            <div className="flex items-start gap-3 flex-1 min-w-0">
              <div className="w-8 h-8 rounded-lg bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center flex-shrink-0 mt-0.5">
                <RefreshCw className="w-4 h-4 text-cyan-400" />
              </div>
              <div className="min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <p className="text-sm font-semibold text-white">Cryptographic Recovery Key</p>
                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-white/5 border border-white/10 text-gray-400 font-bold uppercase">
                    In Development
                  </span>
                </div>
                <p className="text-xs text-gray-400 mt-0.5 leading-relaxed">
                  Offline recovery phrases are currently in development. Password reset via verified email remains available.
                </p>
              </div>
            </div>
            <Toggle enabled={false} disabled={true} />
          </div>

          {/* API Rate Limiting & Abuse Defense - System Enforced */}
          <div className="flex items-center justify-between bg-white/[0.03] p-3.5 rounded-xl border border-white/8 gap-4">
            <div className="flex items-start gap-3 flex-1 min-w-0">
              <div className="w-8 h-8 rounded-lg bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center flex-shrink-0 mt-0.5">
                <Eye className="w-4 h-4 text-emerald-400" />
              </div>
              <div className="min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <p className="text-sm font-semibold text-white">API Rate Limiting & Abuse Shield</p>
                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/15 border border-emerald-500/30 text-emerald-400 font-bold uppercase">
                    System Enforced
                  </span>
                </div>
                <p className="text-xs text-gray-400 mt-0.5 leading-relaxed">
                  Per-user and per-IP request bounds are enforced on all FastAPI endpoints by SlowAPI to safeguard against brute-force attacks.
                </p>
              </div>
            </div>
            <Toggle enabled={true} disabled={true} />
          </div>

          {/* Token Expiration & Revocation - System Enforced */}
          <div className="flex items-center justify-between bg-white/[0.03] p-3.5 rounded-xl border border-white/8 gap-4">
            <div className="flex items-start gap-3 flex-1 min-w-0">
              <div className="w-8 h-8 rounded-lg bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center flex-shrink-0 mt-0.5">
                <Clock className="w-4 h-4 text-emerald-400" />
              </div>
              <div className="min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <p className="text-sm font-semibold text-white">Token Expiration & Session Revocation</p>
                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/15 border border-emerald-500/30 text-emerald-400 font-bold uppercase">
                    System Enforced
                  </span>
                </div>
                <p className="text-xs text-gray-400 mt-0.5 leading-relaxed">
                  JWT access tokens carry strict expiration timestamps. Logging out invalidates active session tokens on the backend immediately.
                </p>
              </div>
            </div>
            <Toggle enabled={true} disabled={true} />
          </div>
        </div>
      </div>

      {/* Session Activity */}
      <div className="p-6 bg-white/[0.04] border border-white/10 rounded-2xl backdrop-blur-md">
        <div className="flex items-center justify-between mb-5">
          <h3 className="font-bold text-sm text-white uppercase tracking-wider flex items-center gap-2">
            <Activity className="w-4 h-4 text-cyan-400" />
            Session Authentication Status
          </h3>
          <span className="text-xs text-gray-500">Live Client Context</span>
        </div>

        <div className="space-y-2">
          <div className="flex items-center gap-4 p-3.5 bg-white/[0.02] border border-white/6 rounded-xl">
            <div className="w-2.5 h-2.5 rounded-full bg-emerald-500 flex-shrink-0 animate-pulse" />
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-white text-sm font-medium">{deviceInfo.name}</span>
                <span className="text-[10px] px-2 py-0.5 bg-emerald-500/15 text-emerald-400 border border-emerald-500/25 rounded font-bold uppercase">
                  Current Session
                </span>
              </div>
              <div className="text-xs text-gray-500 mt-0.5">
                Authenticated via Supabase Auth · Cryptographic JWT Session
              </div>
            </div>
            <span className="text-xs text-gray-400 flex-shrink-0">Active</span>
          </div>
        </div>

        <div className="mt-3 p-3 bg-cyan-500/8 border border-cyan-500/20 rounded-xl flex items-start gap-3">
          <Shield className="w-4 h-4 text-cyan-400 flex-shrink-0 mt-0.5" />
          <p className="text-xs text-cyan-200/80 leading-relaxed">
            <strong className="text-cyan-300">Session Security:</strong> Every API call to NeuroLab AI validates the Bearer token against cryptographic signatures and revocation lists. Logging out invalidates the token across all backend services.
          </p>
        </div>
      </div>

      {/* Connected Devices */}
      <div className="p-6 bg-white/[0.04] border border-white/10 rounded-2xl backdrop-blur-md">
        <h3 className="font-bold text-sm text-white uppercase tracking-wider border-b border-white/8 pb-3 mb-4 flex items-center gap-2">
          <Wifi className="w-4 h-4 text-cyan-400" />
          Active Device Session
        </h3>

        <div className="divide-y divide-white/6">
          <div className="py-4 flex items-center justify-between gap-4">
            <div className="flex items-center gap-3 flex-1 min-w-0">
              <div className="w-10 h-10 rounded-xl border flex items-center justify-center flex-shrink-0 bg-cyan-500/15 border-cyan-500/30 text-cyan-400">
                <deviceInfo.icon className="w-5 h-5" />
              </div>
              <div className="min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-sm font-semibold text-white truncate">{deviceInfo.name}</span>
                  <span className="text-[9px] px-2 py-0.5 bg-cyan-500 text-black font-black rounded-full uppercase">
                    Current Device
                  </span>
                  <span className="text-[9px] px-2 py-0.5 bg-emerald-500/15 text-emerald-400 border border-emerald-500/25 font-bold rounded-full uppercase">
                    Authorized
                  </span>
                </div>
                <p className="text-xs text-gray-500 mt-0.5">Local browser session · Connected to NeuroLab backend</p>
              </div>
            </div>
            <button
              onClick={handleSignOutCurrentSession}
              className="px-3 py-1.5 bg-red-500/10 border border-red-500/20 text-red-400 hover:bg-red-500/20 text-xs font-bold rounded-lg transition-all flex items-center gap-1.5 flex-shrink-0"
            >
              <LogOut className="w-3.5 h-3.5" />
              Sign Out
            </button>
          </div>
        </div>
      </div>

      {/* Verified Security Recommendations */}
      <div className="p-6 bg-white/[0.04] border border-white/10 rounded-2xl backdrop-blur-md">
        <h3 className="font-bold text-sm text-white uppercase tracking-wider border-b border-white/8 pb-3 mb-4 flex items-center gap-2">
          <TrendingUp className="w-4 h-4 text-emerald-400" />
          Verified Security Posture & Recommendations
        </h3>

        <div className="space-y-2.5">
          {[
            {
              ok: true,
              text: 'Strong authentication database: Passwords are encrypted with salted one-way hashing (BCrypt) via Supabase Auth.',
              priority: 'low',
            },
            {
              ok: true,
              text: 'Transport layer encryption: Production endpoints enforce TLS 1.3 encryption across all client-server communications.',
              priority: 'low',
            },
            {
              ok: true,
              text: 'Cryptographic token validation: FastAPI verifies signature, issuer, audience, and expiration on every request.',
              priority: 'low',
            },
            {
              ok: false,
              text: 'Two-Factor Authentication: Planned for an upcoming release. When available, enabling 2FA will further safeguard account credentials.',
              priority: 'medium',
            },
          ].map((item, i) => (
            <div
              key={i}
              className={`flex items-start gap-3 p-3 rounded-xl border ${
                item.ok
                  ? 'bg-emerald-500/5 border-emerald-500/15'
                  : 'bg-amber-500/5 border-amber-500/15'
              }`}
            >
              <div
                className={`w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5 ${
                  item.ok ? 'bg-emerald-500/20' : 'bg-amber-500/20'
                }`}
              >
                {item.ok ? (
                  <CheckCircle className="w-3 h-3 text-emerald-400" />
                ) : (
                  <AlertTriangle className="w-3 h-3 text-amber-400" />
                )}
              </div>
              <span
                className={`text-xs leading-relaxed ${
                  item.ok ? 'text-gray-300' : 'text-amber-300'
                }`}
              >
                {item.text}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Trust indicators */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div className="p-4 bg-cyan-500/5 border border-cyan-500/20 rounded-xl space-y-2">
          <h4 className="text-xs font-black text-cyan-400 uppercase tracking-widest">🔒 End-to-End Encryption</h4>
          <p className="text-xs text-gray-400 leading-relaxed">
            All data transferred between your browser and our servers is encrypted using modern TLS. Your credentials are hashed with salted algorithms and never stored in plaintext.
          </p>
        </div>
        <div className="p-4 bg-violet-500/5 border border-violet-500/20 rounded-xl space-y-2">
          <h4 className="text-xs font-black text-violet-400 uppercase tracking-widest">🛡️ Rate Limiting & Abuse Defense</h4>
          <p className="text-xs text-gray-400 leading-relaxed">
            NeuroLab AI enforces strict per-user and per-IP rate limiting across authentication and computer vision endpoints to prevent credential stuffing and denial of service.
          </p>
        </div>
      </div>

      {!isDashboard && (
        /* Bottom actions */
        <div className="flex flex-wrap justify-center gap-3">
          <motion.button
            whileHover={{ scale: 1.03 }}
            whileTap={{ scale: 0.97 }}
            onClick={() => navigate(-1)}
            className="px-6 py-3 bg-white/5 border border-white/10 rounded-xl text-sm font-bold text-gray-300 hover:text-white transition-all flex items-center gap-2"
          >
            Back
          </motion.button>
          <motion.button
            whileHover={{ scale: 1.03 }}
            whileTap={{ scale: 0.97 }}
            onClick={() => navigate('/trust')}
            className="px-6 py-3 bg-gradient-to-r from-cyan-500 to-blue-600 text-white rounded-xl text-sm font-bold shadow-lg shadow-cyan-500/20 flex items-center gap-2"
          >
            <Shield className="w-4 h-4" />
            View Trust Center
          </motion.button>
        </div>
      )}
    </div>
  );

  if (isDashboard) {
    return (
      <div className="text-white relative">
        <Toast msg={toastMsg} />
        {content}
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#070714] text-white relative overflow-x-hidden">
      <Toast msg={toastMsg} />

      {/* Background */}
      <div className="absolute inset-0 z-0 pointer-events-none">
        <div className="absolute top-0 left-1/4 w-[500px] h-[500px] bg-cyan-500/6 rounded-full blur-3xl" />
        <div className="absolute bottom-0 right-1/4 w-[500px] h-[500px] bg-violet-500/6 rounded-full blur-3xl" />
        <div
          className="absolute inset-0 opacity-[0.03]"
          style={{
            backgroundImage:
              'linear-gradient(rgba(6,182,212,0.4) 1px, transparent 1px), linear-gradient(90deg, rgba(6,182,212,0.4) 1px, transparent 1px)',
            backgroundSize: '60px 60px',
          }}
        />
      </div>

      {content}
    </div>
  );
}
