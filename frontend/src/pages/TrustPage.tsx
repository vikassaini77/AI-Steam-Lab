import { motion } from 'framer-motion';
import {
  Shield, Lock, Eye, CheckCircle, HardDrive, Brain, Users, Activity,
  Star, Zap, Database, Globe, ArrowLeft, ShieldCheck, BadgeCheck
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';

const trustPillars = [
  {
    icon: Eye,
    title: 'Privacy-First Design',
    desc: 'Camera processing runs entirely on your device. Video frames never leave your browser. We built privacy into the architecture, not bolted on as an afterthought.',
    color: 'from-cyan-500/20 to-cyan-600/5',
    border: 'border-cyan-500/25',
    iconColor: 'text-cyan-400',
    iconBg: 'bg-cyan-500/10 border-cyan-500/20',
    badge: '🔒 Local Only',
  },
  {
    icon: Database,
    title: 'Secure Data Handling',
    desc: 'All profile data, learning progress, and experiment logs are encrypted with AES-256 at rest and TLS 1.3 in transit. We follow SOC 2 security principles.',
    color: 'from-blue-500/20 to-blue-600/5',
    border: 'border-blue-500/25',
    iconColor: 'text-blue-400',
    iconBg: 'bg-blue-500/10 border-blue-500/20',
    badge: '🛡️ AES-256',
  },
  {
    icon: Brain,
    title: 'Responsible AI',
    desc: 'Our AI Tutor is focused exclusively on STEM education. No ads, no promotional targeting, no user profiling. AI explanations include source transparency.',
    color: 'from-violet-500/20 to-violet-600/5',
    border: 'border-violet-500/25',
    iconColor: 'text-violet-400',
    iconBg: 'bg-violet-500/10 border-violet-500/20',
    badge: '🤖 Transparent',
  },
  {
    icon: Users,
    title: 'Student Safety First',
    desc: 'Aligned with COPPA and global student data protection laws. No advertising to minors. Leaderboards are opt-in only. Content is education-only.',
    color: 'from-emerald-500/20 to-emerald-600/5',
    border: 'border-emerald-500/25',
    iconColor: 'text-emerald-400',
    iconBg: 'bg-emerald-500/10 border-emerald-500/20',
    badge: '✅ COPPA Safe',
  },
  {
    icon: Activity,
    title: 'Platform Reliability',
    desc: '99.9% uptime SLA target backed by Supabase infrastructure redundancy. Real-time monitoring and instant incident response protocols.',
    color: 'from-amber-500/20 to-amber-600/5',
    border: 'border-amber-500/25',
    iconColor: 'text-amber-400',
    iconBg: 'bg-amber-500/10 border-amber-500/20',
    badge: '⚡ 99.9% Uptime',
  },
  {
    icon: Globe,
    title: 'AI Algorithmic Transparency',
    desc: 'Physics formulas, damping equations, and kinematic models are displayed on simulator panels. We show our math. No black boxes in critical calculations.',
    color: 'from-pink-500/20 to-pink-600/5',
    border: 'border-pink-500/25',
    iconColor: 'text-pink-400',
    iconBg: 'bg-pink-500/10 border-pink-500/20',
    badge: '📐 Open Math',
  },
];

const trustBadges = [
  { icon: '🔒', label: 'End-to-End\nEncryption', color: 'border-cyan-500/25 bg-cyan-500/5' },
  { icon: '🛡️', label: 'Secure\nAuthentication', color: 'border-blue-500/25 bg-blue-500/5' },
  { icon: '🔐', label: 'Privacy\nProtected', color: 'border-violet-500/25 bg-violet-500/5' },
  { icon: '✅', label: 'Verified\nPlatform', color: 'border-emerald-500/25 bg-emerald-500/5' },
  { icon: '📵', label: 'Zero Ad\nTracking', color: 'border-amber-500/25 bg-amber-500/5' },
  { icon: '⚖️', label: 'GDPR\nAligned', color: 'border-pink-500/25 bg-pink-500/5' },
];

const stats = [
  { value: '99.9%', label: 'Uptime SLA' },
  { value: 'AES-256', label: 'Encryption' },
  { value: '0 Ads', label: 'No Advertising' },
  { value: 'Local', label: 'Camera Processing' },
];

export default function TrustPage() {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-[#070714] text-white relative overflow-hidden">
      {/* Background */}
      <div className="absolute inset-0 z-0 pointer-events-none">
        <div className="absolute top-0 left-1/4 w-[500px] h-[500px] bg-cyan-500/5 rounded-full blur-3xl" />
        <div className="absolute bottom-0 right-1/4 w-[500px] h-[500px] bg-blue-500/5 rounded-full blur-3xl" />
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] bg-violet-500/3 rounded-full blur-3xl" />
        <div className="absolute inset-0 opacity-[0.03]" style={{
          backgroundImage: 'linear-gradient(rgba(6,182,212,0.4) 1px, transparent 1px), linear-gradient(90deg, rgba(6,182,212,0.4) 1px, transparent 1px)',
          backgroundSize: '60px 60px'
        }} />
      </div>

      <div className="relative z-10 max-w-5xl mx-auto px-6 py-16">

        {/* Back */}
        <button onClick={() => navigate(-1)} className="flex items-center gap-2 text-gray-400 hover:text-white transition-colors text-sm mb-10 group">
          <ArrowLeft className="w-4 h-4 group-hover:-translate-x-0.5 transition-transform" />
          Back
        </button>

        {/* Header */}
        <div className="text-center space-y-4 mb-16">
          <motion.div
            initial={{ scale: 0.8, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            className="relative inline-block mb-2"
          >
            <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-cyan-500/30 to-blue-500/20 border border-cyan-500/30 flex items-center justify-center mx-auto">
              <Shield className="w-8 h-8 text-cyan-400" />
            </div>
            <motion.div
              animate={{ scale: [1, 1.2, 1] }}
              transition={{ duration: 2, repeat: Infinity }}
              className="absolute -top-1 -right-1 w-4 h-4 bg-emerald-500 rounded-full border-2 border-[#070714] flex items-center justify-center"
            >
              <CheckCircle className="w-2.5 h-2.5 text-white" />
            </motion.div>
          </motion.div>

          <h1 className="text-4xl sm:text-5xl font-black tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-cyan-400 via-blue-400 to-violet-400">
            Trust & Safety Center
          </h1>
          <p className="text-gray-400 max-w-2xl mx-auto">
            NeuroLab AI is built for students, educators, and researchers with security, privacy, and transparency as core principles — not afterthoughts.
          </p>

          <div className="inline-flex items-center gap-2 px-4 py-2 bg-emerald-500/10 border border-emerald-500/25 rounded-full text-sm text-emerald-300 font-semibold">
            <BadgeCheck className="w-4 h-4" />
            Fully Compliant · Student-Protected SaaS Architecture
          </div>
        </div>

        {/* Stats row */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-16">
          {stats.map((stat, i) => (
            <motion.div
              key={stat.label}
              initial={{ opacity: 0, y: 15 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.08 }}
              className="p-5 bg-white/[0.04] border border-white/10 rounded-2xl text-center hover:border-cyan-500/25 hover:bg-white/[0.06] transition-all"
            >
              <div className="text-2xl font-black bg-clip-text text-transparent bg-gradient-to-r from-cyan-400 to-blue-400">{stat.value}</div>
              <div className="text-gray-400 text-xs mt-1 font-medium">{stat.label}</div>
            </motion.div>
          ))}
        </div>

        {/* Trust pillars grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5 mb-16">
          {trustPillars.map((pillar, idx) => {
            const Icon = pillar.icon;
            return (
              <motion.div
                key={pillar.title}
                initial={{ opacity: 0, y: 15 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: idx * 0.07 }}
                whileHover={{ y: -4, transition: { duration: 0.2 } }}
                className={`p-5 bg-gradient-to-br ${pillar.color} border ${pillar.border} rounded-2xl backdrop-blur-sm relative overflow-hidden group`}
              >
                <div className="flex items-start gap-3 mb-3">
                  <div className={`w-10 h-10 rounded-xl ${pillar.iconBg} border flex items-center justify-center flex-shrink-0`}>
                    <Icon className={`w-5 h-5 ${pillar.iconColor}`} />
                  </div>
                  <div>
                    <h3 className="text-white font-bold text-sm leading-tight">{pillar.title}</h3>
                    <span className={`text-[10px] font-bold uppercase tracking-wider ${pillar.iconColor} opacity-70`}>{pillar.badge}</span>
                  </div>
                </div>
                <p className="text-gray-400 text-xs leading-relaxed">{pillar.desc}</p>

                {/* Subtle glow on hover */}
                <div className={`absolute inset-0 rounded-2xl opacity-0 group-hover:opacity-100 transition-opacity bg-gradient-to-br ${pillar.color} pointer-events-none`} />
              </motion.div>
            );
          })}
        </div>

        {/* Trust badges grid */}
        <div className="mb-12">
          <h2 className="text-center text-white font-bold text-lg mb-6">Platform Trust Indicators</h2>
          <div className="grid grid-cols-3 sm:grid-cols-6 gap-3">
            {trustBadges.map((badge, i) => (
              <motion.div
                key={badge.label}
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: i * 0.06 }}
                whileHover={{ scale: 1.05, transition: { duration: 0.15 } }}
                className={`p-3 border rounded-xl text-center ${badge.color} cursor-default`}
              >
                <div className="text-2xl mb-1.5">{badge.icon}</div>
                <div className="text-[10px] font-bold text-gray-300 leading-tight whitespace-pre-line">{badge.label}</div>
              </motion.div>
            ))}
          </div>
        </div>

        {/* Camera transparency section */}
        <div className="p-6 bg-gradient-to-r from-emerald-500/10 to-cyan-500/10 border border-emerald-500/25 rounded-2xl mb-8">
          <div className="flex items-start gap-4">
            <div className="w-12 h-12 rounded-xl bg-emerald-500/15 border border-emerald-500/30 flex items-center justify-center flex-shrink-0">
              <Lock className="w-6 h-6 text-emerald-400" />
            </div>
            <div>
              <h3 className="text-white font-bold mb-2 flex items-center gap-2">
                Camera Transparency Statement
                <span className="text-xs px-2 py-0.5 bg-emerald-500/20 text-emerald-400 rounded-full font-semibold">Important</span>
              </h3>
              <p className="text-gray-300 text-sm leading-relaxed">
                When you use the Live Lab camera feature, <strong>all video processing occurs locally on your device</strong>. 
                No camera frames, images, or video data are transmitted to our servers. 
                AI object detection algorithms run entirely in your browser using local compute. 
                You have full control: camera access can be revoked at any time from your browser settings.
              </p>
            </div>
          </div>
        </div>

        {/* Nav buttons */}
        <div className="flex flex-wrap justify-center gap-3">
          <button onClick={() => navigate('/privacy')} className="px-5 py-2.5 bg-white/5 border border-white/10 rounded-xl text-sm font-medium text-gray-300 hover:text-white hover:bg-white/8 transition-all flex items-center gap-2">
            <ShieldCheck className="w-4 h-4" />
            Privacy Policy
          </button>
          <button onClick={() => navigate('/terms')} className="px-5 py-2.5 bg-white/5 border border-white/10 rounded-xl text-sm font-medium text-gray-300 hover:text-white hover:bg-white/8 transition-all flex items-center gap-2">
            <Globe className="w-4 h-4" />
            Terms & Conditions
          </button>
          <button onClick={() => navigate('/security')} className="px-5 py-2.5 bg-gradient-to-r from-cyan-500 to-blue-600 rounded-xl text-white text-sm font-semibold shadow-lg shadow-cyan-500/20 flex items-center gap-2">
            <Lock className="w-4 h-4" />
            Security Center
          </button>
        </div>
      </div>
    </div>
  );
}


