import { motion, AnimatePresence } from 'framer-motion';
import { useState } from 'react';
import {
  ShieldAlert, Eye, Lock, Globe, HardDrive, Cpu, ShieldCheck,
  ChevronDown, Camera, Database, Cookie, UserCheck, Server,
  Trash2, FileText, Mail, ArrowLeft, ExternalLink
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';

/* ─── Accordion Section ────────────────────────── */
function AccordionSection({
  icon: Icon, title, number, children, defaultOpen = false
}: {
  icon: any; title: string; number: string; children: React.ReactNode; defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="border border-white/10 rounded-xl overflow-hidden bg-white/[0.03] hover:border-white/15 transition-colors"
    >
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-4 p-5 text-left group"
      >
        <div className="w-9 h-9 rounded-lg bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center flex-shrink-0 group-hover:bg-cyan-500/15 transition-colors">
          <Icon className="w-4 h-4 text-cyan-400" />
        </div>
        <div className="flex-1 min-w-0">
          <span className="text-xs text-cyan-400/70 font-semibold">Section {number}</span>
          <h3 className="text-white font-semibold text-sm">{title}</h3>
        </div>
        <ChevronDown className={`w-4 h-4 text-gray-500 transition-transform duration-300 flex-shrink-0 ${open ? 'rotate-180' : ''}`} />
      </button>

      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25 }}
            className="overflow-hidden"
          >
            <div className="px-5 pb-5 pt-0 border-t border-white/5 mt-0 text-gray-400 text-sm leading-relaxed space-y-3">
              {children}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

export default function PrivacyPage() {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-[#070714] text-white relative overflow-hidden">
      {/* Background */}
      <div className="absolute inset-0 z-0 pointer-events-none">
        <div className="absolute top-0 left-1/4 w-[500px] h-[500px] bg-cyan-500/6 rounded-full blur-3xl" />
        <div className="absolute bottom-0 right-1/4 w-[500px] h-[500px] bg-blue-500/6 rounded-full blur-3xl" />
        <div className="absolute inset-0 opacity-[0.03]" style={{
          backgroundImage: 'linear-gradient(rgba(6,182,212,0.4) 1px, transparent 1px), linear-gradient(90deg, rgba(6,182,212,0.4) 1px, transparent 1px)',
          backgroundSize: '60px 60px'
        }} />
      </div>

      <div className="relative z-10 max-w-4xl mx-auto px-6 py-16">

        {/* Back */}
        <button onClick={() => navigate('/')} className="flex items-center gap-2 text-gray-400 hover:text-white transition-colors text-sm mb-10 group">
          <ArrowLeft className="w-4 h-4 group-hover:-translate-x-0.5 transition-transform" />
          Back to Home
        </button>

        {/* Header */}
        <div className="text-center space-y-4 mb-12">
          <motion.div
            initial={{ scale: 0.8, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-cyan-500/15 border border-cyan-500/30 text-cyan-400 mb-2"
          >
            <ShieldAlert className="w-7 h-7" />
          </motion.div>
          <h1 className="text-4xl font-black tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-cyan-400 to-blue-400">
            Privacy Policy
          </h1>
          <p className="text-gray-400 text-sm">Last Updated: May 31, 2026 · Version 2.0</p>

          {/* Camera highlight banner */}
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="inline-flex items-center gap-3 px-5 py-3 bg-emerald-500/10 border border-emerald-500/25 rounded-2xl text-sm"
          >
            <Camera className="w-4 h-4 text-emerald-400 flex-shrink-0" />
            <span className="text-emerald-300 font-semibold">We do not store camera footage without your explicit permission.</span>
          </motion.div>
        </div>

        {/* Trust badges row */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-10">
          {[
            { icon: '🔒', label: 'E2E Encrypted', sub: 'All data in transit' },
            { icon: '🛡️', label: 'GDPR Aligned', sub: 'EU data rights' },
            { icon: '📵', label: 'No Ads', sub: 'Zero ad tracking' },
            { icon: '✅', label: 'COPPA Safe', sub: 'Student protected' },
          ].map((b) => (
            <div key={b.label} className="p-3 bg-white/[0.03] border border-white/10 rounded-xl text-center">
              <div className="text-xl mb-1">{b.icon}</div>
              <div className="text-white text-xs font-bold">{b.label}</div>
              <div className="text-gray-500 text-[10px]">{b.sub}</div>
            </div>
          ))}
        </div>

        {/* Sections */}
        <div className="space-y-3 mb-10">

          <AccordionSection icon={Database} title="Data We Collect" number="1" defaultOpen={true}>
            <p>We collect only what is necessary to provide the NeuroLab AI service:</p>
            <ul className="list-disc list-inside space-y-1.5 mt-2">
              <li><strong className="text-white">Account Information:</strong> Name, email, username, country, education level, and STEM interests provided at registration.</li>
              <li><strong className="text-white">Usage Data:</strong> Pages visited, features used, session duration, and experiment completions.</li>
              <li><strong className="text-white">Learning Progress:</strong> Completed experiments, quiz scores, achievement badges, and AI tutor interaction logs.</li>
              <li><strong className="text-white">Device Information:</strong> Browser type, OS, and screen resolution for compatibility optimization.</li>
            </ul>
            <p className="mt-2 text-xs text-gray-500">We do not collect Social Security numbers, financial data, or biometric identifiers.</p>
          </AccordionSection>

          <AccordionSection icon={Camera} title="Camera Data Usage" number="2">
            <div className="p-3 bg-emerald-500/10 border border-emerald-500/20 rounded-lg mb-3">
              <p className="text-emerald-300 font-semibold text-sm">🔒 Core Commitment: We do not store, record, or transmit camera footage without your explicit, opt-in permission.</p>
            </div>
            <p>When you use the Live Lab camera feature:</p>
            <ul className="list-disc list-inside space-y-1.5 mt-2">
              <li>Video frames are processed <strong className="text-white">100% locally</strong> in your browser using the WebRTC and MediaStream APIs.</li>
              <li>AI object detection runs on your device hardware — no frames are sent to our servers.</li>
              <li>Camera access is requested explicitly with a clear permission dialog before activation.</li>
              <li>You may revoke camera access at any time through browser settings.</li>
              <li>Physical experiment tracking data (angles, velocities, positions) is numerical only — never video.</li>
            </ul>
          </AccordionSection>

          <AccordionSection icon={FileText} title="Experiment & Learning Data" number="3">
            <p>Physics simulation results, quiz answers, and AI tutor conversations are stored securely to power your learning analytics dashboard. This data is:</p>
            <ul className="list-disc list-inside space-y-1.5 mt-2">
              <li>Encrypted at rest using AES-256 encryption</li>
              <li>Linked to your account and never shared publicly without consent</li>
              <li>Used to generate personalized recommendations and achievements</li>
              <li>Never sold to third parties or used for advertising</li>
            </ul>
          </AccordionSection>

          <AccordionSection icon={Cookie} title="Cookies & Local Storage" number="4">
            <p>We use cookies and local storage for the following purposes:</p>
            <ul className="list-disc list-inside space-y-1.5 mt-2">
              <li><strong className="text-white">Essential Cookies:</strong> Authentication tokens, session management, and security headers. Required for the platform to function.</li>
              <li><strong className="text-white">Analytics Cookies:</strong> Anonymized usage patterns to improve platform performance (opt-out available).</li>
              <li><strong className="text-white">Preference Cookies:</strong> Theme settings, dashboard layout, and AI tutor voice preferences (optional).</li>
            </ul>
            <p className="mt-2">Cookie preferences can be managed through the cookie banner or browser settings.</p>
          </AccordionSection>

          <AccordionSection icon={UserCheck} title="Account Information & Authentication" number="5">
            <p>Your account credentials are protected by:</p>
            <ul className="list-disc list-inside space-y-1.5 mt-2">
              <li>Passwords hashed using bcrypt with salt rounds — never stored in plaintext</li>
              <li>OAuth tokens from Google/GitHub/Microsoft are handled by their respective secure systems</li>
              <li>JWT sessions expire automatically for security</li>
              <li>Two-factor authentication available for additional protection</li>
            </ul>
          </AccordionSection>

          <AccordionSection icon={Cpu} title="Third-Party Services" number="6">
            <p>We integrate with trusted third-party services:</p>
            <ul className="list-disc list-inside space-y-1.5 mt-2">
              <li><strong className="text-white">Supabase:</strong> Backend database and authentication infrastructure (SOC 2 compliant)</li>
              <li><strong className="text-white">Google OAuth:</strong> Optional sign-in provider</li>
              <li><strong className="text-white">GitHub OAuth:</strong> Optional sign-in provider for developers</li>
            </ul>
            <p className="mt-2">These services have their own privacy policies. We do not grant them access to your NeuroLab AI learning data.</p>
          </AccordionSection>

          <AccordionSection icon={Trash2} title="Data Retention & Deletion" number="7">
            <p>We retain your data for as long as your account is active. Upon account deletion:</p>
            <ul className="list-disc list-inside space-y-1.5 mt-2">
              <li>Personal information is deleted within <strong className="text-white">30 days</strong></li>
              <li>Anonymized, aggregated analytics data may be retained for platform improvement</li>
              <li>Backup copies are purged within <strong className="text-white">90 days</strong></li>
              <li>You may request immediate deletion by contacting privacy@neurolab.ai</li>
            </ul>
          </AccordionSection>

          <AccordionSection icon={ShieldCheck} title="Your Rights" number="8">
            <p>You have the following rights regarding your personal data:</p>
            <ul className="list-disc list-inside space-y-1.5 mt-2">
              <li><strong className="text-white">Access:</strong> Request a copy of all data we hold about you</li>
              <li><strong className="text-white">Correction:</strong> Update inaccurate personal information</li>
              <li><strong className="text-white">Deletion:</strong> Request complete account and data deletion</li>
              <li><strong className="text-white">Portability:</strong> Export your learning data in JSON format</li>
              <li><strong className="text-white">Restriction:</strong> Limit how we process your data</li>
              <li><strong className="text-white">Objection:</strong> Opt out of non-essential data processing</li>
            </ul>
          </AccordionSection>

          <AccordionSection icon={Lock} title="Security Measures" number="9">
            <p>NeuroLab AI implements enterprise-grade security:</p>
            <ul className="list-disc list-inside space-y-1.5 mt-2">
              <li>TLS 1.3 encryption for all data in transit</li>
              <li>AES-256 encryption for data at rest</li>
              <li>Regular security audits and penetration testing</li>
              <li>CAPTCHA and rate limiting to prevent automated attacks</li>
              <li>Suspicious activity detection and login alerts</li>
              <li>99.9% uptime SLA with redundant infrastructure</li>
            </ul>
          </AccordionSection>

          <AccordionSection icon={Mail} title="Contact & Data Requests" number="10">
            <p>For privacy concerns, data requests, or questions about this policy:</p>
            <div className="mt-3 space-y-2">
              <div className="flex items-center gap-2 text-cyan-400">
                <Mail className="w-4 h-4" />
                <span>privacy@neurolab.ai</span>
              </div>
              <div className="flex items-center gap-2 text-cyan-400">
                <Globe className="w-4 h-4" />
                <span>neurolab.ai/privacy-request</span>
              </div>
            </div>
            <p className="mt-3 text-xs text-gray-500">We respond to all verified data requests within <strong className="text-gray-400">72 hours</strong>.</p>
          </AccordionSection>
        </div>

        {/* Core statement */}
        <div className="p-6 bg-gradient-to-r from-cyan-500/10 to-blue-600/10 border border-cyan-500/20 rounded-2xl text-center mb-8">
          <h4 className="text-cyan-400 font-black uppercase tracking-widest text-sm mb-2">🔒 Our Core Camera Promise</h4>
          <p className="text-gray-300 max-w-2xl mx-auto leading-relaxed">
            "We do not store camera footage without permission. All computer vision processing and AI object detection runs locally on your device hardware, protecting your privacy absolutely."
          </p>
        </div>

        {/* Nav buttons */}
        <div className="flex flex-wrap justify-center gap-3">
          <button onClick={() => navigate('/terms')} className="px-5 py-2.5 bg-white/5 border border-white/10 rounded-xl text-sm font-medium text-gray-300 hover:text-white hover:bg-white/8 transition-all flex items-center gap-2">
            <FileText className="w-4 h-4" />
            Terms & Conditions
          </button>
          <button onClick={() => navigate('/trust')} className="px-5 py-2.5 bg-gradient-to-r from-cyan-500 to-blue-600 rounded-xl text-white text-sm font-semibold shadow-lg shadow-cyan-500/20 flex items-center gap-2">
            <ShieldCheck className="w-4 h-4" />
            Trust Center
          </button>
          <button onClick={() => navigate('/security')} className="px-5 py-2.5 bg-white/5 border border-white/10 rounded-xl text-sm font-medium text-gray-300 hover:text-white hover:bg-white/8 transition-all flex items-center gap-2">
            <Lock className="w-4 h-4" />
            Security Center
          </button>
        </div>
      </div>
    </div>
  );
}
