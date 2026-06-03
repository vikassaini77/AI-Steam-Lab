import { motion, AnimatePresence } from 'framer-motion';
import { useState, useEffect } from 'react';
import {
  ShieldCheck, Lock, Smartphone, RefreshCw, Key, LogOut, CheckCircle,
  Terminal, AlertTriangle, Bell, Clock, Zap, Eye, ArrowLeft, Shield,
  Wifi, Activity, UserCheck, Globe, ChevronRight, TrendingUp, Laptop, Trash2
} from 'lucide-react';
import { useNavigate, useLocation } from 'react-router-dom';

/* ─── Toggle Switch ──────────────────────────────── */
function Toggle({ enabled, onToggle }: { enabled: boolean; onToggle: () => void }) {
  return (
    <button
      type="button"
      onClick={onToggle}
      className={`relative w-11 h-6 rounded-full transition-all duration-300 focus:outline-none ${enabled ? 'bg-cyan-500' : 'bg-white/15'}`}
    >
      <div className={`absolute top-1 w-4 h-4 bg-white rounded-full shadow-sm transition-all duration-300 ${enabled ? 'left-6' : 'left-1'}`} />
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

export default function SecurityPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const isDashboard = location.pathname.startsWith('/dashboard');
  const [mfaEnabled, setMfaEnabled] = useState(false);
  const [loginAlerts, setLoginAlerts] = useState(true);
  const [recState, setRecState] = useState(true);
  const [suspiciousDetect, setSuspiciousDetect] = useState(true);
  const [sessionTimeout, setSessionTimeout] = useState(false);
  const [toastMsg, setToastMsg] = useState<string | null>(null);

  const [devices, setDevices] = useState([
    { id: '1', name: 'Chrome on Windows 11 Desktop', location: 'Mumbai, India', date: 'Active now', icon: Terminal, active: true, trusted: true },
    { id: '2', name: 'Safari on iPhone 15 Pro', location: 'London, UK', date: '10 hours ago', icon: Smartphone, active: false, trusted: false },
    { id: '3', name: 'Firefox on macOS Ventura', location: 'San Jose, USA', date: '3 days ago', icon: Terminal, active: false, trusted: false },
  ]);

  const loginHistory = [
    { device: 'Chrome · Windows 11', location: 'Mumbai, India', time: 'Just now', status: 'success', ip: '182.64.x.x' },
    { device: 'Mobile App · iOS', location: 'London, UK', time: '10 hours ago', status: 'success', ip: '86.45.x.x' },
    { device: 'Unknown Browser', location: 'Moscow, Russia', time: '2 days ago', status: 'blocked', ip: '178.211.x.x' },
    { device: 'Firefox · macOS', location: 'San Jose, USA', time: '3 days ago', status: 'success', ip: '67.180.x.x' },
  ];

  const getSecurityScore = () => {
    let score = 50;
    if (mfaEnabled) score += 20;
    if (loginAlerts) score += 12;
    if (recState) score += 10;
    if (suspiciousDetect) score += 8;
    if (!sessionTimeout) score += 0; else score += 5;
    return Math.min(score, 100);
  };

  const score = getSecurityScore();
  const scoreColor = score >= 90 ? '#10b981' : score >= 70 ? '#06b6d4' : score >= 50 ? '#f59e0b' : '#ef4444';
  const scoreLabel = score >= 90 ? 'Excellent' : score >= 70 ? 'Strong' : score >= 50 ? 'Fair' : 'Weak';

  const toast = (msg: string) => setToastMsg(msg);
  useEffect(() => {
    if (toastMsg) {
      const t = setTimeout(() => setToastMsg(null), 3000);
      return () => clearTimeout(t);
    }
  }, [toastMsg]);
  const handleRevokeDevice = (id: string, name: string) => {
    setDevices((prev) => prev.filter((d) => d.id !== id));
    toast(`Session revoked: ${name} 🔒`);
  };

  const circumference = 2 * Math.PI * 54;

  const content = (
    <div className={`space-y-8 ${isDashboard ? '' : 'relative z-10 max-w-5xl mx-auto px-6 py-16'}`}>
      {!isDashboard && (
        <>
          {/* Back */}
          <button onClick={() => navigate('/')} className="flex items-center gap-2 text-gray-400 hover:text-white transition-colors text-sm group">
            <ArrowLeft className="w-4 h-4 group-hover:-translate-x-0.5 transition-transform" />
            Back to Home
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
            <p className="text-gray-400 text-sm">🛡️ Enterprise-Grade Authentication & Session Protection</p>
          </div>
        </>
      )}

      {/* Top grid: Score + Controls */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">

        {/* Security Score */}
        <div className="p-6 bg-white/[0.04] border border-white/10 rounded-2xl backdrop-blur-md flex flex-col items-center text-center space-y-4">
          <h3 className="font-bold text-sm text-white uppercase tracking-wider">Security Score</h3>

          <div className="relative w-36 h-36 flex items-center justify-center">
            <svg className="absolute inset-0 w-full h-full -rotate-90">
              <circle cx="72" cy="72" r="54" fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="9" />
              <circle
                cx="72" cy="72" r="54" fill="none"
                stroke={scoreColor}
                strokeWidth="9"
                strokeDasharray={circumference}
                strokeDashoffset={circumference - (circumference * score) / 100}
                strokeLinecap="round"
                className="transition-all duration-700"
              />
            </svg>
            <div>
              <div className="text-4xl font-black text-white">{score}</div>
              <div className="text-[10px] font-bold uppercase tracking-wider" style={{ color: scoreColor }}>{scoreLabel}</div>
            </div>
          </div>

          <div className="w-full space-y-1.5 text-left">
            {[
              { label: 'Password', ok: true },
              { label: '2FA', ok: mfaEnabled },
              { label: 'Login Alerts', ok: loginAlerts },
              { label: 'Recovery Key', ok: recState },
              { label: 'Threat Detection', ok: suspiciousDetect },
            ].map((item) => (
              <div key={item.label} className="flex items-center justify-between text-xs">
                <span className="text-gray-400">{item.label}</span>
                <span className={item.ok ? 'text-emerald-400 font-bold' : 'text-red-400 font-bold'}>{item.ok ? '✓' : '✗'}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Auth factor controls */}
        <div className="md:col-span-2 p-6 bg-white/[0.04] border border-white/10 rounded-2xl backdrop-blur-md space-y-4">
          <h3 className="font-bold text-sm text-white uppercase tracking-wider border-b border-white/8 pb-3">
            Authentication Factor Configuration
          </h3>

          {[
            {
              icon: Key,
              label: 'Two-Factor Authentication (2FA)',
              sub: 'Adds extra verification via authenticator app or SMS code.',
              state: mfaEnabled,
              onToggle: () => { setMfaEnabled(!mfaEnabled); toast(mfaEnabled ? 'Two-Factor Authentication disabled.' : '2FA Activated! Your account is now more secure. 🔐'); },
            },
            {
              icon: Bell,
              label: 'Security Login Alerts',
              sub: 'Sends instant email alerts with device and location details on new sign-ins.',
              state: loginAlerts,
              onToggle: () => { setLoginAlerts(!loginAlerts); toast(loginAlerts ? 'Login alerts disabled.' : 'Login alerts enabled — you\'ll be notified of every sign-in. ✉️'); },
            },
            {
              icon: RefreshCw,
              label: 'Account Recovery Key',
              sub: 'Generates secure backup recovery keys for emergency access.',
              state: recState,
              onToggle: () => { setRecState(!recState); toast(recState ? 'Recovery key disabled.' : 'Recovery key generated and secured! 🔑'); },
            },
            {
              icon: Eye,
              label: 'Suspicious Activity Detection',
              sub: 'Monitors for unusual login patterns, rate violations, and anomalies.',
              state: suspiciousDetect,
              onToggle: () => { setSuspiciousDetect(!suspiciousDetect); toast(suspiciousDetect ? 'Threat detection disabled.' : 'Threat detection active — anomalies will be flagged. 🚨'); },
            },
            {
              icon: Clock,
              label: 'Automatic Session Timeout',
              sub: 'Auto-signs out after 30 minutes of inactivity for security.',
              state: sessionTimeout,
              onToggle: () => { setSessionTimeout(!sessionTimeout); toast(sessionTimeout ? 'Auto-timeout disabled.' : 'Session auto-timeout enabled (30 min idle). ⏱️'); },
            },
          ].map(({ icon: Icon, label, sub, state, onToggle }) => (
            <div key={label} className="flex items-center justify-between bg-white/[0.03] p-3.5 rounded-xl border border-white/8 gap-4">
              <div className="flex items-start gap-3 flex-1 min-w-0">
                <div className="w-8 h-8 rounded-lg bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center flex-shrink-0 mt-0.5">
                  <Icon className="w-4 h-4 text-cyan-400" />
                </div>
                <div>
                  <p className="text-sm font-semibold text-white">{label}</p>
                  <p className="text-xs text-gray-500 mt-0.5 leading-relaxed">{sub}</p>
                </div>
              </div>
              <Toggle enabled={state} onToggle={onToggle} />
            </div>
          ))}
        </div>
      </div>

      {/* Recent Login Activity */}
      <div className="p-6 bg-white/[0.04] border border-white/10 rounded-2xl backdrop-blur-md">
        <div className="flex items-center justify-between mb-5">
          <h3 className="font-bold text-sm text-white uppercase tracking-wider flex items-center gap-2">
            <Activity className="w-4 h-4 text-cyan-400" />
            Recent Login Activity
          </h3>
          <span className="text-xs text-gray-500">Last 7 days</span>
        </div>

        <div className="space-y-2">
          {loginHistory.map((entry, i) => (
            <div key={i} className="flex items-center gap-4 p-3.5 bg-white/[0.02] border border-white/6 rounded-xl">
              <div className={`w-2 h-2 rounded-full flex-shrink-0 ${entry.status === 'success' ? 'bg-emerald-500' : 'bg-red-500'}`} />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-white text-sm font-medium">{entry.device}</span>
                  {entry.status === 'blocked' && (
                    <span className="text-[10px] px-1.5 py-0.5 bg-red-500/15 text-red-400 border border-red-500/20 rounded font-bold uppercase">Blocked</span>
                  )}
                </div>
                <div className="text-xs text-gray-500 mt-0.5">{entry.location} · {entry.ip}</div>
              </div>
              <span className="text-xs text-gray-500 flex-shrink-0">{entry.time}</span>
              {entry.status === 'blocked' && (
                <AlertTriangle className="w-4 h-4 text-red-400 flex-shrink-0" />
              )}
            </div>
          ))}
        </div>

        <div className="mt-3 p-3 bg-amber-500/8 border border-amber-500/20 rounded-xl flex items-start gap-3">
          <AlertTriangle className="w-4 h-4 text-amber-400 flex-shrink-0 mt-0.5" />
          <p className="text-xs text-amber-300/80 leading-relaxed">
            <strong className="text-amber-300">Security Notice:</strong> A sign-in attempt from Moscow, Russia was blocked 2 days ago. If this was not you, your account is safe — the attempt was rejected automatically.
          </p>
        </div>
      </div>

      {/* Connected Devices */}
      <div className="p-6 bg-white/[0.04] border border-white/10 rounded-2xl backdrop-blur-md">
        <h3 className="font-bold text-sm text-white uppercase tracking-wider border-b border-white/8 pb-3 mb-4 flex items-center gap-2">
          <Wifi className="w-4 h-4 text-cyan-400" />
          Active Device Sessions
        </h3>

        <div className="divide-y divide-white/6">
          {devices.map((dev) => {
            const DevIcon = dev.icon;
            return (
              <div key={dev.id} className="py-4 flex items-center justify-between gap-4">
                <div className="flex items-center gap-3 flex-1 min-w-0">
                  <div className={`w-10 h-10 rounded-xl border flex items-center justify-center flex-shrink-0 ${dev.active ? 'bg-cyan-500/15 border-cyan-500/30 text-cyan-400' : 'bg-white/5 border-white/10 text-gray-400'}`}>
                    <DevIcon className="w-5 h-5" />
                  </div>
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-sm font-semibold text-white truncate">{dev.name}</span>
                      {dev.active && (
                        <span className="text-[9px] px-2 py-0.5 bg-cyan-500 text-black font-black rounded-full uppercase">Current</span>
                      )}
                      {dev.trusted && !dev.active && (
                        <span className="text-[9px] px-2 py-0.5 bg-emerald-500/15 text-emerald-400 border border-emerald-500/25 font-bold rounded-full uppercase">Trusted</span>
                      )}
                    </div>
                    <p className="text-xs text-gray-500 mt-0.5">{dev.location} · {dev.date}</p>
                  </div>
                </div>
                {!dev.active && (
                  <button
                    onClick={() => handleRevokeDevice(dev.id, dev.name)}
                    className="px-3 py-1.5 bg-red-500/10 border border-red-500/20 text-red-400 hover:bg-red-500/20 text-xs font-bold rounded-lg transition-all flex items-center gap-1.5 flex-shrink-0"
                  >
                    <LogOut className="w-3.5 h-3.5" />
                    Revoke
                  </button>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Security Recommendations */}
      <div className="p-6 bg-white/[0.04] border border-white/10 rounded-2xl backdrop-blur-md">
        <h3 className="font-bold text-sm text-white uppercase tracking-wider border-b border-white/8 pb-3 mb-4 flex items-center gap-2">
          <TrendingUp className="w-4 h-4 text-emerald-400" />
          Security Recommendations
        </h3>

        <div className="space-y-2.5">
          {[
            { ok: true, text: 'Strong password detected (12+ characters, mixed case, symbols)', priority: 'low' },
            { ok: mfaEnabled, text: mfaEnabled ? '2FA enabled — excellent! Your account has maximum login protection' : 'Enable Two-Factor Authentication to significantly improve account security', priority: 'high' },
            { ok: loginAlerts, text: loginAlerts ? 'Login alerts are active — you\'ll be notified of suspicious sign-ins' : 'Enable login alerts to detect unauthorized access attempts', priority: 'medium' },
            { ok: recState, text: recState ? 'Account recovery key is set up and secured' : 'Generate a recovery key in case you lose access to your account', priority: 'medium' },
            { ok: true, text: 'Email address verified — account recovery email is active', priority: 'low' },
          ].map((item, i) => (
            <div key={i} className={`flex items-start gap-3 p-3 rounded-xl border ${item.ok ? 'bg-emerald-500/5 border-emerald-500/15' : item.priority === 'high' ? 'bg-red-500/5 border-red-500/15' : 'bg-amber-500/5 border-amber-500/15'}`}>
              <div className={`w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5 ${item.ok ? 'bg-emerald-500/20' : item.priority === 'high' ? 'bg-red-500/20' : 'bg-amber-500/20'}`}>
                {item.ok ? <CheckCircle className="w-3 h-3 text-emerald-400" /> : <AlertTriangle className={`w-3 h-3 ${item.priority === 'high' ? 'text-red-400' : 'text-amber-400'}`} />}
              </div>
              <span className={`text-xs leading-relaxed ${item.ok ? 'text-gray-400' : item.priority === 'high' ? 'text-red-300' : 'text-amber-300'}`}>{item.text}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Trust indicators */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div className="p-4 bg-cyan-500/5 border border-cyan-500/20 rounded-xl space-y-2">
          <h4 className="text-xs font-black text-cyan-400 uppercase tracking-widest">🔒 End-to-End Encryption</h4>
          <p className="text-xs text-gray-400 leading-relaxed">All data transferred between your browser and our servers is encrypted using TLS 1.3. Your credentials are hashed with bcrypt and never stored in plaintext.</p>
        </div>
        <div className="p-4 bg-violet-500/5 border border-violet-500/20 rounded-xl space-y-2">
          <h4 className="text-xs font-black text-violet-400 uppercase tracking-widest">🛡️ Rate Limiting & CAPTCHA</h4>
          <p className="text-xs text-gray-400 leading-relaxed">NeuroLab AI enforces strict rate limiting, bot detection, and invisible CAPTCHA verification on all authentication endpoints to prevent brute-force attacks.</p>
        </div>
      </div>

      {!isDashboard && (
        /* Bottom actions */
        <div className="flex flex-wrap justify-center gap-3">
          <motion.button
            whileHover={{ scale: 1.03 }}
            whileTap={{ scale: 0.97 }}
            onClick={() => navigate('/')}
            className="px-6 py-3 bg-white/5 border border-white/10 rounded-xl text-sm font-bold text-gray-300 hover:text-white transition-all flex items-center gap-2"
          >
            Back to Home
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
    <div className="min-h-screen bg-[#070714] text-white relative overflow-hidden">
      <Toast msg={toastMsg} />

      {/* Background */}
      <div className="absolute inset-0 z-0 pointer-events-none">
        <div className="absolute top-0 left-1/4 w-[500px] h-[500px] bg-cyan-500/6 rounded-full blur-3xl" />
        <div className="absolute bottom-0 right-1/4 w-[500px] h-[500px] bg-violet-500/6 rounded-full blur-3xl" />
        <div className="absolute inset-0 opacity-[0.03]" style={{
          backgroundImage: 'linear-gradient(rgba(6,182,212,0.4) 1px, transparent 1px), linear-gradient(90deg, rgba(6,182,212,0.4) 1px, transparent 1px)',
          backgroundSize: '60px 60px'
        }} />
      </div>

      {content}
    </div>
  );
}
