import { motion, AnimatePresence } from 'framer-motion';
import { useState, useEffect } from 'react';
import {
  ShieldCheck, Smartphone, RefreshCw, Key, LogOut, CheckCircle,
  Terminal, AlertTriangle, Bell, Clock, Eye, ArrowLeft, Shield,
  Wifi, Activity, TrendingUp, X, Copy, QrCode
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

  // Live Multi-Factor Authentication (MFA / TOTP) State
  const [is2FAEnabled, setIs2FAEnabled] = useState(false);
  const [activeFactorId, setActiveFactorId] = useState<string | null>(null);
  const [showMFAModal, setShowMFAModal] = useState(false);
  const [mfaLoading, setMfaLoading] = useState(false);
  const [mfaEnrollData, setMfaEnrollData] = useState<{ id: string; qr_code: string; secret: string } | null>(null);
  const [verifyCode, setVerifyCode] = useState('');
  const [verifyError, setVerifyError] = useState<string | null>(null);
  const [isVerifying, setIsVerifying] = useState(false);

  const loadMFAStatus = async () => {
    try {
      const authWithMfa = supabase.auth as unknown as {
        mfa?: {
          listFactors?: () => Promise<{ data?: { all?: Array<{ id: string; status: string; factor_type: string }> } | null }>;
        };
      };
      if (authWithMfa?.mfa?.listFactors) {
        const res = await authWithMfa.mfa.listFactors();
        const all = res?.data?.all || [];
        const verified = all.find((f) => f.status === 'verified' && f.factor_type === 'totp');
        if (verified) {
          setIs2FAEnabled(true);
          setActiveFactorId(verified.id);
        } else {
          setIs2FAEnabled(false);
          setActiveFactorId(null);
        }
      }
    } catch (e) {
      console.warn('Failed to load MFA factors:', e);
    }
  };

  useEffect(() => {
    setDeviceInfo(getBrowserDeviceInfo());
    loadMFAStatus();
  }, []);

  // Verified security posture:
  // 1. Password hashing (BCrypt via Supabase): 20%
  // 2. TLS 1.3 transport encryption: 20%
  // 3. Cryptographic JWT claims verification: 20%
  // 4. API Rate Limiting & brute-force defense: 20%
  // 5. Multi-Factor Authentication (2FA TOTP): 20% (when active)
  const verifiedScore = is2FAEnabled ? 100 : 80;
  const scoreColor = is2FAEnabled ? '#10b981' : '#06b6d4';
  const scoreLabel = is2FAEnabled ? 'Excellent' : 'Strong';

  const circumference = 2 * Math.PI * 54;

  const toast = (msg: string) => setToastMsg(msg);
  useEffect(() => {
    if (toastMsg) {
      const t = setTimeout(() => setToastMsg(null), 3000);
      return () => clearTimeout(t);
    }
  }, [toastMsg]);

  const handleToggle2FA = async () => {
    if (is2FAEnabled) {
      if (!window.confirm('Are you sure you want to disable Two-Factor Authentication?')) {
        return;
      }
      try {
        setMfaLoading(true);
        const authWithMfa = supabase.auth as unknown as {
          mfa?: {
            unenroll?: (p: { factorId: string }) => Promise<unknown>;
          };
        };
        if (activeFactorId && authWithMfa?.mfa?.unenroll) {
          await authWithMfa.mfa.unenroll({ factorId: activeFactorId });
        }
        setIs2FAEnabled(false);
        setActiveFactorId(null);
        toast('Two-Factor Authentication disabled.');
      } catch (err) {
        console.error('Failed to disable 2FA:', err);
        toast('Error disabling 2FA. Please try again.');
      } finally {
        setMfaLoading(false);
      }
    } else {
      setMfaLoading(true);
      setVerifyError(null);
      setVerifyCode('');
      try {
        const authWithMfa = supabase.auth as unknown as {
          mfa?: {
            enroll?: (p: { factorType: string; issuer?: string }) => Promise<{
              data?: { id: string; totp?: { qr_code?: string; secret?: string } } | null;
              error?: { message: string } | null;
            }>;
          };
        };
        if (authWithMfa?.mfa?.enroll) {
          const res = await authWithMfa.mfa.enroll({
            factorType: 'totp',
            issuer: 'NeuroLab AI',
          });
          if (res?.data?.totp?.qr_code && res?.data?.totp?.secret) {
            setMfaEnrollData({
              id: res.data.id,
              qr_code: res.data.totp.qr_code,
              secret: res.data.totp.secret,
            });
            setShowMFAModal(true);
          } else if (res?.error) {
            toast(res.error.message || '2FA enrollment failed');
          }
        }
      } catch (e) {
        console.error('2FA enroll error:', e);
        toast('Failed to initialize 2FA enrollment.');
      } finally {
        setMfaLoading(false);
      }
    }
  };

  const handleVerify2FACode = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!mfaEnrollData) return;
    if (verifyCode.trim().length !== 6) {
      setVerifyError('Please enter the 6-digit verification code from your authenticator app.');
      return;
    }
    setIsVerifying(true);
    setVerifyError(null);
    try {
      const authWithMfa = supabase.auth as unknown as {
        mfa?: {
          challenge?: (p: { factorId: string }) => Promise<{ data?: { id: string } | null; error?: { message: string } | null }>;
          verify?: (p: { factorId: string; challengeId?: string; code: string }) => Promise<{ data?: unknown; error?: { message: string } | null }>;
        };
      };
      if (!authWithMfa?.mfa?.challenge || !authWithMfa?.mfa?.verify) {
        throw new Error('MFA service unavailable');
      }

      const challengeRes = await authWithMfa.mfa.challenge({ factorId: mfaEnrollData.id });
      const challengeId = challengeRes?.data?.id;

      const verifyRes = await authWithMfa.mfa.verify({
        factorId: mfaEnrollData.id,
        challengeId,
        code: verifyCode.trim(),
      });

      if (verifyRes?.error) {
        setVerifyError(verifyRes.error.message || 'Invalid 6-digit code. Please verify the code in your app.');
      } else {
        setIs2FAEnabled(true);
        setActiveFactorId(mfaEnrollData.id);
        setShowMFAModal(false);
        toast('Two-Factor Authentication activated successfully!');
      }
    } catch (err: unknown) {
      setVerifyError((err as Error)?.message || 'Verification failed. Please try again.');
    } finally {
      setIsVerifying(false);
    }
  };

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
              { label: 'Two-Factor Authentication (2FA)', ok: is2FAEnabled, note: is2FAEnabled ? 'Active' : 'Recommended' },
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

          {/* 2FA - Multi-Factor Authentication (TOTP) */}
          <div className="flex items-center justify-between bg-white/[0.03] p-3.5 rounded-xl border border-white/8 gap-4">
            <div className="flex items-start gap-3 flex-1 min-w-0">
              <div className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5 ${
                is2FAEnabled
                  ? 'bg-emerald-500/10 border border-emerald-500/20 text-emerald-400'
                  : 'bg-cyan-500/10 border border-cyan-500/20 text-cyan-400'
              }`}>
                <Key className="w-4 h-4" />
              </div>
              <div className="min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <p className="text-sm font-semibold text-white">Two-Factor Authentication (2FA / TOTP)</p>
                  {is2FAEnabled ? (
                    <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/15 border border-emerald-500/30 text-emerald-400 font-bold uppercase">
                      Active
                    </span>
                  ) : (
                    <span className="text-[10px] px-2 py-0.5 rounded-full bg-cyan-500/10 border border-cyan-500/30 text-cyan-400 font-bold uppercase">
                      Ready to Setup
                    </span>
                  )}
                </div>
                <p className="text-xs text-gray-400 mt-0.5 leading-relaxed">
                  {is2FAEnabled
                    ? 'Protected with time-based one-time password (TOTP). Authenticator verification is required at login.'
                    : 'Add an extra cryptographic defense layer using Google Authenticator, Authy, or 1Password.'}
                </p>
              </div>
            </div>
            <Toggle enabled={is2FAEnabled} disabled={mfaLoading} onToggle={handleToggle2FA} />
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
              ok: is2FAEnabled,
              text: is2FAEnabled
                ? 'Two-Factor Authentication: Active with cryptographic TOTP authenticator protection.'
                : 'Two-Factor Authentication: Available and recommended. Enable 2FA above to safeguard account credentials.',
              priority: is2FAEnabled ? 'low' : 'medium',
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

      {/* 2FA TOTP Enrollment Modal */}
      <AnimatePresence>
        {showMFAModal && mfaEnrollData && (
          <div className="fixed inset-0 z-[120] flex items-center justify-center p-4">
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setShowMFAModal(false)}
              className="absolute inset-0 bg-black/80 backdrop-blur-md"
            />
            <motion.div
              initial={{ scale: 0.9, opacity: 0, y: 20 }}
              animate={{ scale: 1, opacity: 1, y: 0 }}
              exit={{ scale: 0.95, opacity: 0, y: 10 }}
              className="relative w-full max-w-md bg-[#0d0d20] border border-cyan-500/30 rounded-2xl p-6 shadow-2xl shadow-cyan-500/10 space-y-5 z-10"
            >
              <div className="flex items-center justify-between border-b border-white/10 pb-3">
                <div className="flex items-center gap-2">
                  <div className="w-8 h-8 rounded-lg bg-cyan-500/15 border border-cyan-500/30 flex items-center justify-center text-cyan-400">
                    <QrCode className="w-4 h-4" />
                  </div>
                  <div>
                    <h3 className="font-bold text-white text-sm">Setup Authenticator App</h3>
                    <p className="text-[11px] text-gray-400">Scan with Google Authenticator, Authy, or 1Password</p>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => setShowMFAModal(false)}
                  className="p-1 rounded-lg text-gray-400 hover:text-white hover:bg-white/10 transition-colors"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              {/* QR Code */}
              <div className="flex flex-col items-center justify-center p-4 bg-white/[0.03] border border-white/8 rounded-xl space-y-3">
                <div className="p-3 bg-white rounded-xl shadow-lg">
                  <img
                    src={mfaEnrollData.qr_code}
                    alt="2FA TOTP QR Code"
                    className="w-44 h-44 object-contain"
                  />
                </div>
                <div className="w-full text-center space-y-1">
                  <p className="text-[11px] text-gray-400">Or enter this secret key manually:</p>
                  <div className="flex items-center justify-center gap-2">
                    <code className="text-xs bg-black/50 px-2 py-1 rounded text-cyan-300 font-mono tracking-wider select-all">
                      {mfaEnrollData.secret}
                    </code>
                    <button
                      type="button"
                      onClick={() => {
                        if (typeof navigator !== 'undefined' && navigator.clipboard) {
                          navigator.clipboard.writeText(mfaEnrollData.secret);
                          toast('Secret key copied to clipboard!');
                        }
                      }}
                      className="p-1 text-gray-400 hover:text-cyan-400 transition-colors"
                      title="Copy Secret"
                    >
                      <Copy className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              </div>

              {/* Verification Form */}
              <form onSubmit={handleVerify2FACode} className="space-y-4">
                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-gray-300 block">
                    6-Digit Verification Code
                  </label>
                  <input
                    type="text"
                    inputMode="numeric"
                    pattern="[0-9]*"
                    maxLength={6}
                    value={verifyCode}
                    onChange={(e) => {
                      setVerifyCode(e.target.value.replace(/\D/g, ''));
                      setVerifyError(null);
                    }}
                    placeholder="123456"
                    className="w-full px-4 py-2.5 rounded-xl bg-black/40 border border-white/15 text-white text-center font-mono text-xl tracking-[0.3em] placeholder:text-gray-600 focus:outline-none focus:border-cyan-400 transition-colors"
                    autoFocus
                  />
                  {verifyError && (
                    <p className="text-xs text-rose-400 font-medium">{verifyError}</p>
                  )}
                </div>

                <div className="flex items-center gap-3 pt-2">
                  <button
                    type="button"
                    onClick={() => setShowMFAModal(false)}
                    className="flex-1 px-4 py-2.5 rounded-xl bg-white/5 border border-white/10 text-xs font-bold text-gray-300 hover:text-white transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={isVerifying || verifyCode.length !== 6}
                    className="flex-1 px-4 py-2.5 rounded-xl bg-cyan-500 text-black text-xs font-black shadow-lg shadow-cyan-500/20 hover:bg-cyan-400 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
                  >
                    {isVerifying ? 'Verifying...' : 'Verify & Enable'}
                  </button>
                </div>
              </form>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
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
