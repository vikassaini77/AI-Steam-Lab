import { motion, AnimatePresence } from 'framer-motion';
import { useState, useEffect } from 'react';
import { supabase } from '../lib/supabase';
import {
  Mail, Lock, User, ArrowRight, Sparkles, Github, Chrome, Eye, EyeOff,
  Check, X, AlertCircle, CheckCircle, RefreshCw, BookOpen, Globe, GraduationCap,
  AtSign, ChevronLeft, Send, ShieldCheck, Zap, Brain, Microscope
} from 'lucide-react';

/* ─── Types ─────────────────────────────────────── */
type AuthView = 'signin' | 'signup' | 'forgot' | 'verify' | 'welcome' | 'reset';

interface AuthPageProps {
  onAuthSuccess?: () => void;
  initialView?: AuthView;
}

/* ─── Password Strength Helper ───────────────────── */
function getPasswordStrength(password: string): { score: number; label: string; color: string } {
  if (!password) return { score: 0, label: '', color: '' };
  let score = 0;
  if (password.length >= 8) score++;
  if (password.length >= 12) score++;
  if (/[A-Z]/.test(password)) score++;
  if (/[0-9]/.test(password)) score++;
  if (/[^A-Za-z0-9]/.test(password)) score++;
  if (score <= 1) return { score, label: 'Weak', color: '#ef4444' };
  if (score <= 2) return { score, label: 'Fair', color: '#f59e0b' };
  if (score <= 3) return { score, label: 'Good', color: '#3b82f6' };
  if (score <= 4) return { score, label: 'Strong', color: '#10b981' };
  return { score, label: 'Very Strong', color: '#06b6d4' };
}

/* ─── Reusable Input Component ───────────────────── */
function InputField({
  label, icon: Icon, type = 'text', value, onChange, placeholder, required, error, success,
  rightElement
}: {
  label: string; icon: any; type?: string; value: string; onChange: (v: string) => void;
  placeholder: string; required?: boolean; error?: string; success?: boolean; rightElement?: React.ReactNode;
}) {
  return (
    <div>
      <label className="block text-sm text-gray-400 mb-2 font-medium">{label}</label>
      <div className="relative">
        <Icon className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
        <input
          type={type}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          required={required}
          className={`w-full pl-10 pr-10 py-3 bg-white/5 border rounded-xl text-white placeholder-gray-600 text-sm focus:outline-none focus:ring-2 transition-all ${
            error
              ? 'border-red-500/50 focus:border-red-500/50 focus:ring-red-500/20'
              : success
              ? 'border-emerald-500/50 focus:border-emerald-500/50 focus:ring-emerald-500/20'
              : 'border-white/10 focus:border-cyan-500/50 focus:ring-cyan-500/20'
          }`}
        />
        <div className="absolute right-3 top-1/2 -translate-y-1/2">
          {rightElement || (error ? <X className="w-4 h-4 text-red-400" /> : success ? <Check className="w-4 h-4 text-emerald-400" /> : null)}
        </div>
      </div>
      {error && (
        <motion.p initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} className="mt-1.5 text-xs text-red-400 flex items-center gap-1">
          <AlertCircle className="w-3 h-3" /> {error}
        </motion.p>
      )}
    </div>
  );
}

/* ─── Social Button ──────────────────────────────── */
function SocialButton({ icon: Icon, label, onClick, disabled }: { icon: any; label: string; onClick: () => void; disabled: boolean }) {
  return (
    <motion.button
      whileHover={{ scale: 1.02, backgroundColor: 'rgba(255,255,255,0.08)' }}
      whileTap={{ scale: 0.98 }}
      onClick={onClick}
      disabled={disabled}
      type="button"
      className="flex items-center justify-center gap-2.5 px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white text-sm hover:bg-white/8 transition-all disabled:opacity-40 disabled:cursor-not-allowed w-full"
    >
      <Icon className="w-4 h-4" />
      <span className="font-medium">{label}</span>
    </motion.button>
  );
}

/* ─── Background Effects ─────────────────────────── */
function AuthBackground() {
  return (
    <div className="absolute inset-0 overflow-hidden pointer-events-none">
      <div className="absolute -top-40 -left-40 w-96 h-96 bg-cyan-500/8 rounded-full blur-3xl animate-pulse" />
      <div className="absolute -bottom-40 -right-40 w-96 h-96 bg-violet-500/8 rounded-full blur-3xl animate-pulse" style={{ animationDelay: '1s' }} />
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] bg-blue-500/3 rounded-full blur-3xl" />
      <div
        className="absolute inset-0 opacity-[0.03]"
        style={{
          backgroundImage: `
            linear-gradient(rgba(6,182,212,0.4) 1px, transparent 1px),
            linear-gradient(90deg, rgba(6,182,212,0.4) 1px, transparent 1px)
          `,
          backgroundSize: '60px 60px',
        }}
      />
    </div>
  );
}

/* ─── Trust Badges ───────────────────────────────── */
function TrustBadges() {
  return (
    <div className="flex items-center justify-center gap-4 flex-wrap mt-6">
      {[
        { icon: '🔒', label: 'E2E Encrypted' },
        { icon: '🛡️', label: 'Secure Auth' },
        { icon: '✅', label: 'Verified' },
      ].map((b) => (
        <div key={b.label} className="flex items-center gap-1.5 text-gray-500 text-xs">
          <span>{b.icon}</span>
          <span>{b.label}</span>
        </div>
      ))}
    </div>
  );
}

/* ─── Sign In Form ───────────────────────────────── */
function SignInForm({ onSwitch, onAuthSuccess, onForgot }: { onSwitch: () => void; onAuthSuccess?: () => void; onForgot: () => void }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [rememberMe, setRememberMe] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const { error } = await supabase.auth.signInWithPassword({ email, password });
      if (error) throw error;
      onAuthSuccess?.();
    } catch (err: any) {
      setError(err.message || 'Invalid email or password.');
    } finally {
      setLoading(false);
    }
  };

  const handleOAuth = async (provider: 'google' | 'github') => {
    const providerName = provider === 'google' ? 'Google' : 'GitHub';
    setError(`${providerName} sign in is coming soon!`);
  };

  return (
    <motion.div
      key="signin"
      initial={{ opacity: 0, x: -20 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: 20 }}
      transition={{ duration: 0.3 }}
    >
      <div className="text-center mb-7">
        <h1 className="text-2xl font-bold text-white mb-1.5">Welcome back</h1>
        <p className="text-gray-400 text-sm">Sign in to continue your STEM journey</p>
      </div>

      {/* Social Providers */}
      <div className="grid grid-cols-2 gap-3 mb-5">
        <SocialButton icon={Chrome} label="Google" onClick={() => handleOAuth('google')} disabled={loading} />
        <SocialButton icon={Github} label="GitHub" onClick={() => handleOAuth('github')} disabled={loading} />
      </div>

      <div className="flex items-center gap-3 mb-5">
        <div className="flex-1 h-px bg-white/8" />
        <span className="text-gray-600 text-xs font-medium">or continue with email</span>
        <div className="flex-1 h-px bg-white/8" />
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        <InputField label="Email address" icon={Mail} type="email" value={email} onChange={setEmail} placeholder="you@example.com" required />
        <InputField
          label="Password"
          icon={Lock}
          type={showPassword ? 'text' : 'password'}
          value={password}
          onChange={setPassword}
          placeholder="••••••••"
          required
          rightElement={
            <button type="button" onClick={() => setShowPassword(!showPassword)} className="text-gray-500 hover:text-gray-300 transition-colors">
              {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
            </button>
          }
        />

        <div className="flex items-center justify-between">
          <label className="flex items-center gap-2 cursor-pointer group">
            <div
              onClick={() => setRememberMe(!rememberMe)}
              className={`w-4 h-4 rounded border transition-all flex items-center justify-center ${rememberMe ? 'bg-cyan-500 border-cyan-500' : 'border-white/20 bg-white/5'}`}
            >
              {rememberMe && <Check className="w-2.5 h-2.5 text-black" />}
            </div>
            <span className="text-sm text-gray-400 group-hover:text-gray-300 transition-colors">Remember me</span>
          </label>
          <button type="button" onClick={onForgot} className="text-sm text-cyan-400 hover:text-cyan-300 transition-colors font-medium">
            Forgot password?
          </button>
        </div>

        {error && (
          <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} className="p-3 bg-red-500/10 border border-red-500/20 rounded-xl text-red-400 text-sm flex items-start gap-2">
            <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
            {error}
          </motion.div>
        )}

        <motion.button
          whileHover={{ scale: 1.01, boxShadow: '0 0 40px rgba(6,182,212,0.25)' }}
          whileTap={{ scale: 0.99 }}
          type="submit"
          disabled={loading}
          className="w-full py-3.5 bg-gradient-to-r from-cyan-500 to-blue-600 rounded-xl text-white font-semibold flex items-center justify-center gap-2 disabled:opacity-50 text-sm shadow-lg shadow-cyan-500/20 mt-2"
        >
          {loading ? (
            <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
          ) : (
            <>
              <Sparkles className="w-4 h-4" />
              Sign In to NeuroLab
              <ArrowRight className="w-4 h-4" />
            </>
          )}
        </motion.button>
      </form>

      <p className="text-center text-gray-500 text-sm mt-5">
        Don't have an account?{' '}
        <button onClick={onSwitch} className="text-cyan-400 hover:text-cyan-300 transition-colors font-semibold">
          Create account
        </button>
      </p>
    </motion.div>
  );
}

/* ─── Sign Up Form ───────────────────────────────── */
function SignUpForm({ onSwitch, onVerify }: { onSwitch: () => void; onVerify: (email: string) => void }) {
  const [formData, setFormData] = useState({
    firstName: '', lastName: '', username: '', email: '',
    password: '', confirmPassword: '', country: '', education: '', stemInterest: '',
  });
  const [showPassword, setShowPassword] = useState(false);
  const [showTerms, setShowTerms] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  const strength = getPasswordStrength(formData.password);

  const update = (key: string) => (val: string) => setFormData((p) => ({ ...p, [key]: val }));

  const validate = () => {
    const errors: Record<string, string> = {};
    if (!formData.firstName.trim()) errors.firstName = 'First name is required';
    if (!formData.lastName.trim()) errors.lastName = 'Last name is required';
    if (!formData.username.trim()) errors.username = 'Username is required';
    if (!/^[a-zA-Z0-9_]{3,20}$/.test(formData.username)) errors.username = 'Username must be 3-20 chars, letters, numbers, underscores';
    if (!formData.email.includes('@')) errors.email = 'Valid email required';
    if (formData.password.length < 8) errors.password = 'Password must be at least 8 characters';
    if (formData.password !== formData.confirmPassword) errors.confirmPassword = 'Passwords do not match';
    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleInitialSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!validate()) return;
    setShowTerms(true);
  };

  const handleFinalSignup = async () => {
    setError(null);
    setLoading(true);
    try {
      const { error } = await supabase.auth.signUp({
        email: formData.email,
        password: formData.password,
        options: {
          data: {
            full_name: `${formData.firstName} ${formData.lastName}`,
            username: formData.username,
            country: formData.country,
            education: formData.education,
            stem_interest: formData.stemInterest,
          },
        },
      });
      if (error) throw error;
      onVerify(formData.email);
    } catch (err: any) {
      setError(err.message || 'Could not create account. Please try again.');
      setShowTerms(false); // Go back to form to show error
    } finally {
      setLoading(false);
    }
  };

  const handleOAuth = async (provider: 'google' | 'github') => {
    const providerName = provider === 'google' ? 'Google' : 'GitHub';
    setError(`${providerName} sign in is coming soon!`);
  };

  return (
    <motion.div
      key="signup"
      initial={{ opacity: 0, x: 20 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: -20 }}
      transition={{ duration: 0.3 }}
    >
      {showTerms ? (
        <div className="text-left">
          <div className="text-center mb-6">
            <div className="w-14 h-14 rounded-2xl bg-cyan-500/15 border border-cyan-500/30 flex items-center justify-center mx-auto mb-4">
              <ShieldCheck className="w-7 h-7 text-cyan-400" />
            </div>
            <h1 className="text-2xl font-bold text-white mb-1.5">Review & Accept Terms</h1>
            <p className="text-gray-400 text-sm">Please accept our terms to finish creating your account.</p>
          </div>

          <div className="h-64 overflow-y-auto pr-2 mb-6 custom-scrollbar text-xs text-gray-400 space-y-4 bg-white/[0.02] border border-white/10 rounded-xl p-4">
            <h3 className="text-sm font-bold text-white uppercase tracking-wider">1. Acceptance of Terms</h3>
            <p>By creating an account, you agree to NeuroLab's Terms of Service and Privacy Policy. You must be at least 13 years old to use the platform.</p>
            
            <h3 className="text-sm font-bold text-white uppercase tracking-wider">2. Data Privacy & Camera Usage</h3>
            <p>NeuroLab utilizes your device's camera for the Live Lab physical experiment tracker. <strong>All video processing happens locally on your device.</strong> We do not record, store, or transmit your camera feed.</p>
            
            <h3 className="text-sm font-bold text-white uppercase tracking-wider">3. AI Limitations</h3>
            <p>Our AI Tutor is an educational tool. While we strive for accuracy, AI-generated content may occasionally contain errors. It should not replace professional guidance or substitute for verifiable academic research.</p>

            <h3 className="text-sm font-bold text-white uppercase tracking-wider">4. Acceptable Use</h3>
            <p>You agree not to misuse the platform, attempt to breach security measures, scrape data, or use our services for malicious purposes.</p>
          </div>

          <div className="flex flex-col gap-3">
            <button
              onClick={handleFinalSignup}
              disabled={loading}
              className="w-full py-3.5 bg-gradient-to-r from-cyan-500 to-blue-600 rounded-xl text-white font-semibold flex items-center justify-center gap-2 shadow-lg shadow-cyan-500/20"
            >
              {loading ? <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" /> : 'I Accept & Create Account'}
            </button>
            <button
              onClick={() => setShowTerms(false)}
              disabled={loading}
              className="w-full py-3 bg-white/5 border border-white/10 rounded-xl text-gray-300 font-medium hover:bg-white/10 transition-colors"
            >
              Decline & Go Back
            </button>
          </div>
        </div>
      ) : (
        <>
          <div className="text-center mb-6">
            <h1 className="text-2xl font-bold text-white mb-1.5">Create your account</h1>
            <p className="text-gray-400 text-sm">Join thousands of STEM learners worldwide</p>
          </div>

      {/* Social Providers */}
      <div className="grid grid-cols-2 gap-3 mb-5">
        <SocialButton icon={Chrome} label="Google" onClick={() => handleOAuth('google')} disabled={loading} />
        <SocialButton icon={Github} label="GitHub" onClick={() => handleOAuth('github')} disabled={loading} />
      </div>

      <div className="flex items-center gap-3 mb-5">
        <div className="flex-1 h-px bg-white/8" />
        <span className="text-gray-600 text-xs font-medium">or sign up with email</span>
        <div className="flex-1 h-px bg-white/8" />
      </div>

      <form onSubmit={handleInitialSubmit} className="space-y-4">
        {/* Name Row */}
        <div className="grid grid-cols-2 gap-3">
          <InputField label="First Name" icon={User} value={formData.firstName} onChange={update('firstName')} placeholder="Alex" required error={fieldErrors.firstName} success={!!formData.firstName && !fieldErrors.firstName} />
          <InputField label="Last Name" icon={User} value={formData.lastName} onChange={update('lastName')} placeholder="Chen" required error={fieldErrors.lastName} success={!!formData.lastName && !fieldErrors.lastName} />
        </div>

        <InputField label="Username" icon={AtSign} value={formData.username} onChange={update('username')} placeholder="alex_chen" required error={fieldErrors.username} success={!!formData.username && !fieldErrors.username} />

        <InputField label="Email address" icon={Mail} type="email" value={formData.email} onChange={update('email')} placeholder="alex@example.com" required error={fieldErrors.email} success={!!formData.email && formData.email.includes('@') && !fieldErrors.email} />

        {/* Password */}
        <div>
          <InputField
            label="Password"
            icon={Lock}
            type={showPassword ? 'text' : 'password'}
            value={formData.password}
            onChange={update('password')}
            placeholder="Create strong password"
            required
            error={fieldErrors.password}
            rightElement={
              <button type="button" onClick={() => setShowPassword(!showPassword)} className="text-gray-500 hover:text-gray-300 transition-colors">
                {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            }
          />
          {formData.password && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="mt-2">
              <div className="flex gap-1.5 mb-1">
                {[1, 2, 3, 4, 5].map((i) => (
                  <div
                    key={i}
                    className="h-1 flex-1 rounded-full transition-all duration-500"
                    style={{ backgroundColor: i <= strength.score ? strength.color : 'rgba(255,255,255,0.08)' }}
                  />
                ))}
              </div>
              <p className="text-xs" style={{ color: strength.color }}>{strength.label}</p>
            </motion.div>
          )}
        </div>

        <InputField label="Confirm Password" icon={Lock} type="password" value={formData.confirmPassword} onChange={update('confirmPassword')} placeholder="Repeat your password" required error={fieldErrors.confirmPassword} success={!!formData.confirmPassword && formData.password === formData.confirmPassword} />

        {/* Country & Education Row */}
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-sm text-gray-400 mb-2 font-medium">Country</label>
            <div className="relative">
              <Globe className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500 pointer-events-none" />
              <select
                value={formData.country}
                onChange={(e) => update('country')(e.target.value)}
                className="w-full pl-9 pr-3 py-3 bg-white/5 border border-white/10 rounded-xl text-white text-sm focus:outline-none focus:border-cyan-500/50 focus:ring-2 focus:ring-cyan-500/20 appearance-none"
              >
                <option value="" className="bg-[#0d0d1a]">Select</option>
                {['India', 'United States', 'United Kingdom', 'Canada', 'Australia', 'Germany', 'France', 'Japan', 'Brazil', 'Other'].map((c) => (
                  <option key={c} value={c} className="bg-[#0d0d1a]">{c}</option>
                ))}
              </select>
            </div>
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-2 font-medium">Education Level</label>
            <div className="relative">
              <GraduationCap className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500 pointer-events-none" />
              <select
                value={formData.education}
                onChange={(e) => update('education')(e.target.value)}
                className="w-full pl-9 pr-3 py-3 bg-white/5 border border-white/10 rounded-xl text-white text-sm focus:outline-none focus:border-cyan-500/50 focus:ring-2 focus:ring-cyan-500/20 appearance-none"
              >
                <option value="" className="bg-[#0d0d1a]">Select</option>
                {['Middle School', 'High School', 'Undergraduate', 'Graduate', 'PhD', 'Professional', 'Other'].map((e) => (
                  <option key={e} value={e} className="bg-[#0d0d1a]">{e}</option>
                ))}
              </select>
            </div>
          </div>
        </div>

        {/* STEM Interest */}
        <div>
          <label className="block text-sm text-gray-400 mb-2 font-medium">Primary STEM Interest</label>
          <div className="grid grid-cols-3 gap-2">
            {[
              { value: 'physics', label: 'Physics', icon: Zap },
              { value: 'biology', label: 'Biology', icon: Microscope },
              { value: 'ai', label: 'AI & CS', icon: Brain },
              { value: 'chemistry', label: 'Chemistry', icon: BookOpen },
              { value: 'math', label: 'Math', icon: Sparkles },
              { value: 'astronomy', label: 'Astronomy', icon: Globe },
            ].map(({ value, label, icon: Icon }) => (
              <button
                key={value}
                type="button"
                onClick={() => update('stemInterest')(value)}
                className={`flex flex-col items-center gap-1.5 p-2.5 rounded-xl border text-xs font-medium transition-all ${
                  formData.stemInterest === value
                    ? 'border-cyan-500/50 bg-cyan-500/10 text-cyan-300'
                    : 'border-white/10 bg-white/5 text-gray-400 hover:border-white/20'
                }`}
              >
                <Icon className="w-4 h-4" />
                {label}
              </button>
            ))}
          </div>
        </div>



        {error && (
          <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} className="p-3 bg-red-500/10 border border-red-500/20 rounded-xl text-red-400 text-sm flex items-start gap-2">
            <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
            {error}
          </motion.div>
        )}

        <motion.button
          whileHover={{ scale: 1.01, boxShadow: '0 0 40px rgba(6,182,212,0.25)' }}
          whileTap={{ scale: 0.99 }}
          type="submit"
          disabled={loading}
          className="w-full py-3.5 bg-gradient-to-r from-cyan-500 to-blue-600 rounded-xl text-white font-semibold flex items-center justify-center gap-2 disabled:opacity-50 text-sm shadow-lg shadow-cyan-500/20 mt-1"
        >
          {loading ? (
            <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
          ) : (
            <>
              <Sparkles className="w-4 h-4" />
              Create Account
              <ArrowRight className="w-4 h-4" />
            </>
          )}
        </motion.button>
      </form>

      <p className="text-center text-gray-500 text-sm mt-5">
        Already have an account?{' '}
        <button onClick={onSwitch} className="text-cyan-400 hover:text-cyan-300 transition-colors font-semibold">
          Sign in
        </button>
      </p>
      </>
      )}
    </motion.div>
  );
}

/* ─── Forgot Password Form ───────────────────────── */
function ForgotPasswordForm({ onBack }: { onBack: () => void }) {
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const { error } = await supabase.auth.resetPasswordForEmail(email, {
        redirectTo: `${window.location.origin}/reset-password`,
      });
      if (error) throw error;
      setSent(true);
    } catch (err: any) {
      setError(err.message || 'Failed to send reset email.');
    } finally {
      setLoading(false);
    }
  };

  if (sent) {
    return (
      <motion.div key="forgot-sent" initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} className="text-center py-4">
        <div className="w-16 h-16 rounded-full bg-emerald-500/15 border border-emerald-500/30 flex items-center justify-center mx-auto mb-5">
          <CheckCircle className="w-8 h-8 text-emerald-400" />
        </div>
        <h2 className="text-xl font-bold text-white mb-2">Check your inbox</h2>
        <p className="text-gray-400 text-sm mb-2">
          We've sent a password reset link to:
        </p>
        <p className="text-cyan-400 font-semibold text-sm mb-6">{email}</p>
        <p className="text-gray-500 text-xs mb-6 leading-relaxed">
          Didn't receive the email? Check your spam folder or try again in a few minutes.
        </p>
        <div className="flex gap-3">
          <button
            onClick={() => setSent(false)}
            className="flex-1 py-3 bg-white/5 border border-white/10 rounded-xl text-gray-300 text-sm font-medium hover:bg-white/8 transition-all"
          >
            Try another email
          </button>
          <button
            onClick={onBack}
            className="flex-1 py-3 bg-gradient-to-r from-cyan-500 to-blue-600 rounded-xl text-white text-sm font-semibold"
          >
            Back to Sign In
          </button>
        </div>
      </motion.div>
    );
  }

  return (
    <motion.div key="forgot" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }}>
      <button onClick={onBack} className="flex items-center gap-2 text-gray-400 hover:text-white transition-colors text-sm mb-6 group">
        <ChevronLeft className="w-4 h-4 group-hover:-translate-x-0.5 transition-transform" />
        Back to sign in
      </button>

      <div className="text-center mb-7">
        <div className="w-14 h-14 rounded-2xl bg-cyan-500/15 border border-cyan-500/20 flex items-center justify-center mx-auto mb-4">
          <Send className="w-6 h-6 text-cyan-400" />
        </div>
        <h1 className="text-2xl font-bold text-white mb-1.5">Reset your password</h1>
        <p className="text-gray-400 text-sm">Enter your email and we'll send you a secure reset link</p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        <InputField label="Email address" icon={Mail} type="email" value={email} onChange={setEmail} placeholder="you@example.com" required />

        {error && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="p-3 bg-red-500/10 border border-red-500/20 rounded-xl text-red-400 text-sm flex items-start gap-2">
            <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
            {error}
          </motion.div>
        )}

        <motion.button
          whileHover={{ scale: 1.01, boxShadow: '0 0 30px rgba(6,182,212,0.2)' }}
          whileTap={{ scale: 0.99 }}
          type="submit"
          disabled={loading}
          className="w-full py-3.5 bg-gradient-to-r from-cyan-500 to-blue-600 rounded-xl text-white font-semibold flex items-center justify-center gap-2 disabled:opacity-50 text-sm shadow-lg shadow-cyan-500/20"
        >
          {loading ? (
            <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
          ) : (
            <>
              <Send className="w-4 h-4" />
              Send Reset Link
            </>
          )}
        </motion.button>
      </form>

      <div className="mt-6 p-3 bg-white/3 border border-white/8 rounded-xl">
        <p className="text-xs text-gray-500 text-center leading-relaxed">
          🔒 The reset link expires in <strong className="text-gray-400">1 hour</strong> for security. Your password won't change until you follow the link.
        </p>
      </div>
    </motion.div>
  );
}

/* ─── Reset Password Form ─────────────────────────── */
function ResetPasswordForm({ onBack }: { onBack: () => void }) {
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showPassword, setShowPassword] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (password.length < 8) {
      setError('Password must be at least 8 characters long.');
      return;
    }
    if (password !== confirmPassword) {
      setError('Passwords do not match.');
      return;
    }
    setError(null);
    setLoading(true);
    try {
      const { error } = await supabase.auth.updateUser({ password });
      if (error) throw error;
      setSuccess(true);
    } catch (err: any) {
      setError(err.message || 'Failed to reset password.');
    } finally {
      setLoading(false);
    }
  };

  if (success) {
    return (
      <motion.div key="reset-success" initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} className="text-center py-4">
        <div className="w-16 h-16 rounded-full bg-emerald-500/15 border border-emerald-500/30 flex items-center justify-center mx-auto mb-5">
          <CheckCircle className="w-8 h-8 text-emerald-400" />
        </div>
        <h2 className="text-xl font-bold text-white mb-2">Password Reset Complete</h2>
        <p className="text-gray-400 text-sm mb-6 leading-relaxed">
          Your password has been successfully updated. You can now sign in with your new credentials.
        </p>
        <button
          onClick={onBack}
          className="w-full py-3.5 bg-gradient-to-r from-cyan-500 to-blue-600 rounded-xl text-white font-semibold"
        >
          Sign In
        </button>
      </motion.div>
    );
  }

  return (
    <motion.div key="reset" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }}>
      <button onClick={onBack} className="flex items-center gap-2 text-gray-400 hover:text-white transition-colors text-sm mb-6 group">
        <ChevronLeft className="w-4 h-4 group-hover:-translate-x-0.5 transition-transform" />
        Back to sign in
      </button>

      <div className="text-center mb-7">
        <div className="w-14 h-14 rounded-2xl bg-cyan-500/15 border border-cyan-500/30 flex items-center justify-center mx-auto mb-4 text-cyan-400">
          <Lock className="w-6 h-6" />
        </div>
        <h1 className="text-2xl font-bold text-white mb-1.5">Create New Password</h1>
        <p className="text-gray-400 text-sm">Please choose a secure password with at least 8 characters.</p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        <InputField
          label="New Password"
          icon={Lock}
          type={showPassword ? 'text' : 'password'}
          value={password}
          onChange={setPassword}
          placeholder="New secure password"
          required
          rightElement={
            <button type="button" onClick={() => setShowPassword(!showPassword)} className="text-gray-500 hover:text-gray-300 transition-colors">
              {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
            </button>
          }
        />
        <InputField
          label="Confirm New Password"
          icon={Lock}
          type="password"
          value={confirmPassword}
          onChange={setConfirmPassword}
          placeholder="Repeat new password"
          required
        />

        {error && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="p-3 bg-red-500/10 border border-red-500/20 rounded-xl text-red-400 text-sm flex items-start gap-2">
            <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
            {error}
          </motion.div>
        )}

        <motion.button
          whileHover={{ scale: 1.01, boxShadow: '0 0 30px rgba(6,182,212,0.2)' }}
          whileTap={{ scale: 0.99 }}
          type="submit"
          disabled={loading}
          className="w-full py-3.5 bg-gradient-to-r from-cyan-500 to-blue-600 rounded-xl text-white font-semibold flex items-center justify-center gap-2 disabled:opacity-50 text-sm shadow-lg shadow-cyan-500/20"
        >
          {loading ? (
            <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
          ) : (
            <>
              <RefreshCw className="w-4 h-4" />
              Reset Password
            </>
          )}
        </motion.button>
      </form>
    </motion.div>
  );
}

/* ─── Verify Email Screen ────────────────────────── */
function VerifyEmailScreen({ email, onBack }: { email?: string; onBack: () => void }) {
  const [resent, setResent] = useState(false);
  const [resending, setResending] = useState(false);

  const handleResend = async () => {
    setResending(true);
    try {
      if (email) {
        await supabase.auth.resend({ type: 'signup', email });
      }
      setResent(true);
      setTimeout(() => setResent(false), 5000);
    } catch {
      // silently handle
    } finally {
      setResending(false);
    }
  };

  return (
    <motion.div key="verify" initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} className="text-center py-4">
      <motion.div
        animate={{ rotate: [0, -10, 10, -5, 5, 0] }}
        transition={{ duration: 0.6, delay: 0.2 }}
        className="w-16 h-16 rounded-full bg-cyan-500/15 border border-cyan-500/30 flex items-center justify-center mx-auto mb-5"
      >
        <Mail className="w-8 h-8 text-cyan-400" />
      </motion.div>

      <h2 className="text-xl font-bold text-white mb-2">Verify your email</h2>
      <p className="text-gray-400 text-sm mb-2">We sent a verification link to:</p>
      {email && <p className="text-cyan-400 font-semibold text-sm mb-4">{email}</p>}

      <div className="p-4 bg-white/3 border border-white/8 rounded-xl mb-5 text-left space-y-2">
        {[
          'Check your email inbox',
          'Click the verification link',
          'You\'ll be redirected to NeuroLab AI',
        ].map((step, i) => (
          <div key={i} className="flex items-center gap-3">
            <div className="w-5 h-5 rounded-full bg-cyan-500/20 text-cyan-400 text-xs font-bold flex items-center justify-center flex-shrink-0">{i + 1}</div>
            <span className="text-gray-400 text-xs">{step}</span>
          </div>
        ))}
      </div>

      <p className="text-gray-500 text-xs mb-4">Didn't receive it? Check your spam or</p>

      {resent ? (
        <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="text-emerald-400 text-sm font-medium flex items-center justify-center gap-1.5 mb-4">
          <CheckCircle className="w-4 h-4" /> Email resent successfully!
        </motion.p>
      ) : (
        <button
          onClick={handleResend}
          disabled={resending}
          className="text-cyan-400 hover:text-cyan-300 transition-colors text-sm font-semibold flex items-center gap-1.5 mx-auto mb-4 disabled:opacity-50"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${resending ? 'animate-spin' : ''}`} />
          Resend verification email
        </button>
      )}

      <button
        onClick={onBack}
        className="text-gray-500 hover:text-gray-300 transition-colors text-xs flex items-center gap-1.5 mx-auto"
      >
        <ChevronLeft className="w-3.5 h-3.5" />
        Back to sign in
      </button>
    </motion.div>
  );
}

/* ─── Welcome Screen ─────────────────────────────── */
function WelcomeScreen({ onContinue }: { onContinue: () => void }) {
  return (
    <motion.div key="welcome" initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} className="text-center py-4">
      <motion.div
        animate={{ scale: [1, 1.05, 1] }}
        transition={{ duration: 2, repeat: Infinity }}
        className="w-16 h-16 rounded-full bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center mx-auto mb-5 shadow-lg shadow-cyan-500/30"
      >
        <CheckCircle className="w-8 h-8 text-white" />
      </motion.div>

      <div className="mb-2">
        <span className="text-xs font-bold text-emerald-400 uppercase tracking-wider px-3 py-1 bg-emerald-500/10 border border-emerald-500/20 rounded-full">
          Account Created Successfully
        </span>
      </div>

      <h2 className="text-2xl font-bold text-white mt-4 mb-2">Welcome to NeuroLab AI!</h2>
      <p className="text-gray-400 text-sm mb-6 leading-relaxed max-w-xs mx-auto">
        Your account is ready. You'll receive a verification email shortly. Start exploring STEM experiments now!
      </p>

      <div className="grid grid-cols-3 gap-3 mb-6">
        {[
          { icon: Zap, label: 'Physics Lab', color: 'text-cyan-400' },
          { icon: Brain, label: 'AI Tutor', color: 'text-violet-400' },
          { icon: Microscope, label: 'Biology', color: 'text-emerald-400' },
        ].map(({ icon: Icon, label, color }) => (
          <div key={label} className="p-3 bg-white/5 border border-white/10 rounded-xl">
            <Icon className={`w-5 h-5 ${color} mx-auto mb-1.5`} />
            <p className="text-gray-400 text-xs">{label}</p>
          </div>
        ))}
      </div>

      <motion.button
        whileHover={{ scale: 1.02, boxShadow: '0 0 30px rgba(6,182,212,0.25)' }}
        whileTap={{ scale: 0.98 }}
        onClick={onContinue}
        className="w-full py-3.5 bg-gradient-to-r from-cyan-500 to-blue-600 rounded-xl text-white font-semibold flex items-center justify-center gap-2 text-sm shadow-lg shadow-cyan-500/20"
      >
        <Sparkles className="w-4 h-4" />
        Enter NeuroLab AI
        <ArrowRight className="w-4 h-4" />
      </motion.button>
    </motion.div>
  );
}

/* ─── Logo ───────────────────────────────────────── */
function Logo() {
  return (
    <div className="flex items-center gap-3 mb-8 justify-center">
      <div className="w-10 h-10 rounded-xl flex items-center justify-center shadow-lg shadow-cyan-500/30 overflow-hidden bg-[#070714]">
        <img src="/logo.png" alt="NeuroLab Logo" className="w-full h-full object-cover" />
      </div>
      <span className="text-xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-cyan-400 to-blue-400">
        NeuroLab AI
      </span>
    </div>
  );
}

/* ─── Main Auth Page ──────────────────────────────── */
export default function AuthPage({ onAuthSuccess, initialView = 'signin' }: AuthPageProps) {
  const [view, setView] = useState<AuthView>(initialView);
  const [signupEmail, setSignupEmail] = useState('');

  return (
    <div className="min-h-screen bg-[#070714] relative overflow-x-hidden flex items-center justify-center p-4">
      <AuthBackground />

      {/* Left panel — only on large screens */}
      <div className="hidden lg:flex flex-col justify-center items-start max-w-sm w-full mr-16 relative z-10">
        <div className="mb-6">
          <span className="text-xs font-bold text-cyan-400 uppercase tracking-widest px-3 py-1 bg-cyan-500/10 border border-cyan-500/20 rounded-full">
            Trusted by 10,000+ STEM Learners
          </span>
        </div>
        <h2 className="text-4xl font-black text-white leading-tight mb-4">
          Learn Science
          <br />
          <span className="bg-clip-text text-transparent bg-gradient-to-r from-cyan-400 to-blue-400">
            Like Never Before
          </span>
        </h2>
        <p className="text-gray-400 text-sm leading-relaxed mb-8">
          NeuroLab AI combines real-time computer vision, AI tutoring, and interactive physics simulations to make STEM learning extraordinary.
        </p>

        <div className="space-y-4 w-full">
          {[
            { icon: Zap, title: 'Live Physics Lab', desc: 'Real-time AI tracks pendulums, projectiles & more' },
            { icon: Brain, title: 'AI Tutor', desc: '24/7 intelligent STEM assistance and explanations' },
            { icon: ShieldCheck, title: 'Privacy Protected', desc: 'Camera data processed locally. Never stored.' },
          ].map(({ icon: Icon, title, desc }) => (
            <div key={title} className="flex items-start gap-3 p-3 rounded-xl bg-white/3 border border-white/8">
              <div className="w-8 h-8 rounded-lg bg-cyan-500/15 border border-cyan-500/20 flex items-center justify-center flex-shrink-0">
                <Icon className="w-4 h-4 text-cyan-400" />
              </div>
              <div>
                <h4 className="text-white font-semibold text-sm">{title}</h4>
                <p className="text-gray-500 text-xs mt-0.5">{desc}</p>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Auth Card */}
      <motion.div
        initial={{ opacity: 0, y: 24 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="relative z-10 w-full max-w-md"
      >
        <div className="bg-white/[0.04] backdrop-blur-2xl rounded-2xl border border-white/10 p-8 shadow-2xl shadow-black/50">
          <Logo />

          <AnimatePresence mode="wait">
            {view === 'signin' && (
              <SignInForm
                onSwitch={() => setView('signup')}
                onAuthSuccess={onAuthSuccess}
                onForgot={() => setView('forgot')}
              />
            )}
            {view === 'signup' && (
              <SignUpForm
                onSwitch={() => setView('signin')}
                onVerify={(email) => { setSignupEmail(email); setView('verify'); }}
              />
            )}
            {view === 'forgot' && (
              <ForgotPasswordForm onBack={() => setView('signin')} />
            )}
            {view === 'reset' && (
              <ResetPasswordForm onBack={() => setView('signin')} />
            )}
            {view === 'verify' && (
              <VerifyEmailScreen email={signupEmail} onBack={() => setView('signin')} />
            )}
            {view === 'welcome' && (
              <WelcomeScreen onContinue={() => { onAuthSuccess?.(); }} />
            )}
          </AnimatePresence>
        </div>

        <TrustBadges />

        <p className="text-center text-gray-600 text-xs mt-4">
          <a href="/" className="hover:text-gray-400 transition-colors">← Back to home</a>
        </p>
      </motion.div>
    </div>
  );
}
