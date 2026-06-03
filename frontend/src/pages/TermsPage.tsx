import { motion, AnimatePresence } from 'framer-motion';
import { useState } from 'react';
import {
  FileText, Shield, User, Terminal, Book, Landmark, AlertTriangle,
  ChevronDown, Mail, Globe, ArrowLeft, Camera, Scale, BadgeCheck
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
        <div className="w-9 h-9 rounded-lg bg-violet-500/10 border border-violet-500/20 flex items-center justify-center flex-shrink-0 group-hover:bg-violet-500/15 transition-colors">
          <Icon className="w-4 h-4 text-violet-400" />
        </div>
        <div className="flex-1 min-w-0">
          <span className="text-xs text-violet-400/70 font-semibold">Section {number}</span>
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
            <div className="px-5 pb-5 pt-0 border-t border-white/5 text-gray-400 text-sm leading-relaxed space-y-3">
              {children}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

export default function TermsPage() {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-[#070714] text-white relative overflow-hidden">
      {/* Background */}
      <div className="absolute inset-0 z-0 pointer-events-none">
        <div className="absolute top-0 left-1/4 w-[500px] h-[500px] bg-violet-500/5 rounded-full blur-3xl" />
        <div className="absolute bottom-0 right-1/4 w-[500px] h-[500px] bg-cyan-500/5 rounded-full blur-3xl" />
        <div className="absolute inset-0 opacity-[0.03]" style={{
          backgroundImage: 'linear-gradient(rgba(139,92,246,0.4) 1px, transparent 1px), linear-gradient(90deg, rgba(139,92,246,0.4) 1px, transparent 1px)',
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
            className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-violet-500/15 border border-violet-500/30 text-violet-400 mb-2"
          >
            <Scale className="w-7 h-7" />
          </motion.div>
          <h1 className="text-4xl font-black tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-violet-400 to-cyan-400">
            Terms & Conditions
          </h1>
          <p className="text-gray-400 text-sm">Last Updated: May 31, 2026 · Stable Release v2.0</p>

          <div className="flex flex-wrap justify-center gap-3 pt-2">
            {[
              { icon: BadgeCheck, label: 'Student Safe', color: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20' },
              { icon: Shield, label: 'COPPA Compliant', color: 'text-blue-400 bg-blue-500/10 border-blue-500/20' },
              { icon: Scale, label: 'Fair Use Terms', color: 'text-violet-400 bg-violet-500/10 border-violet-500/20' },
            ].map(({ icon: Icon, label, color }) => (
              <div key={label} className={`flex items-center gap-2 px-3 py-1.5 rounded-full border text-xs font-semibold ${color}`}>
                <Icon className="w-3.5 h-3.5" />
                {label}
              </div>
            ))}
          </div>
        </div>

        {/* Intro */}
        <div className="p-5 bg-violet-500/5 border border-violet-500/15 rounded-xl mb-8 text-sm text-gray-400 leading-relaxed">
          By accessing or using NeuroLab AI, you agree to be bound by these Terms and Conditions. Please read them carefully. If you do not agree, please do not use the platform.
        </div>

        {/* Sections */}
        <div className="space-y-3 mb-10">

          <AccordionSection icon={User} title="User Responsibilities" number="1" defaultOpen={true}>
            <p>As a user of NeuroLab AI, you agree to:</p>
            <ul className="list-disc list-inside space-y-1.5 mt-2">
              <li>Provide accurate and truthful registration information</li>
              <li>Keep your login credentials confidential and not share your account</li>
              <li>Notify us immediately of unauthorized access to your account</li>
              <li>Use the platform responsibly and in compliance with all applicable laws</li>
              <li>Not attempt to reverse engineer, scrape, or abuse the platform</li>
              <li>Respect other users and maintain a positive learning environment</li>
            </ul>
            <p className="mt-2 text-xs text-gray-500">Accounts are individual, non-transferable, and may not be shared between multiple users.</p>
          </AccordionSection>

          <AccordionSection icon={Globe} title="Platform Usage & Acceptable Use" number="2">
            <p>NeuroLab AI is an educational platform designed for STEM learning. Permitted uses include:</p>
            <ul className="list-disc list-inside space-y-1.5 mt-2">
              <li>Personal learning, school assignments, and research projects</li>
              <li>Accessing physics simulations and AI tutoring features</li>
              <li>Using camera features for live experiment tracking</li>
            </ul>
            <p className="mt-3">Prohibited uses include:</p>
            <ul className="list-disc list-inside space-y-1.5 mt-2">
              <li>Commercial use without express written permission</li>
              <li>Automated scraping of content, experiments, or AI responses</li>
              <li>Using the platform to generate harmful, misleading, or illegal content</li>
              <li>Attempting to access other users' accounts or data</li>
            </ul>
          </AccordionSection>

          <AccordionSection icon={Terminal} title="AI Disclaimer & Learning Content" number="3">
            <p>NeuroLab AI's artificial intelligence features are educational tools designed to support learning. Important disclaimers:</p>
            <ul className="list-disc list-inside space-y-1.5 mt-2">
              <li>AI responses are for educational guidance only and may contain errors</li>
              <li>Physics simulations use simplified models and should not replace professional calculations</li>
              <li>AI tutor explanations should be cross-referenced with textbooks and teachers</li>
              <li>We make no guarantee of 100% accuracy for AI-generated content</li>
              <li>NeuroLab AI is not responsible for decisions made based on AI outputs</li>
            </ul>
          </AccordionSection>

          <AccordionSection icon={Camera} title="Experiment & Camera Usage" number="4">
            <p>When using the Live Lab camera and experiment features:</p>
            <ul className="list-disc list-inside space-y-1.5 mt-2">
              <li>Camera access is optional and requires explicit browser permission</li>
              <li>All camera processing occurs locally on your device</li>
              <li>Users are responsible for setting up safe physical experiment environments</li>
              <li>Do not film other people without their consent</li>
              <li>Experiment results are for learning purposes and approximate only</li>
              <li>Always follow proper safety protocols when conducting physical experiments</li>
            </ul>
          </AccordionSection>

          <AccordionSection icon={Book} title="Intellectual Property" number="5">
            <p>All content on NeuroLab AI is protected by intellectual property law:</p>
            <ul className="list-disc list-inside space-y-1.5 mt-2">
              <li>Physics simulations, algorithms, and visualizations are proprietary</li>
              <li>UI design, graphics, and branding are owned by NeuroLab AI</li>
              <li>AI models and training methodologies are trade secrets</li>
              <li>You may not reproduce, distribute, or create derivative works without written permission</li>
            </ul>
            <p className="mt-2">Your learning progress data (quiz answers, experiment logs) belongs to you and can be exported upon request.</p>
          </AccordionSection>

          <AccordionSection icon={Landmark} title="Account Rules & Platform Conduct" number="6">
            <p>The following behaviors may result in account suspension or termination:</p>
            <ul className="list-disc list-inside space-y-1.5 mt-2">
              <li>Attempting to exploit or hack the platform or its APIs</li>
              <li>Submitting false or malicious inputs to the AI tutor</li>
              <li>Spamming, phishing, or engaging in social engineering</li>
              <li>Creating multiple accounts to circumvent restrictions</li>
              <li>Sharing account access with unauthorized individuals</li>
              <li>Any activity that violates local, national, or international laws</li>
            </ul>
          </AccordionSection>

          <AccordionSection icon={AlertTriangle} title="Termination Policy" number="7">
            <p>NeuroLab AI reserves the right to terminate or suspend accounts:</p>
            <ul className="list-disc list-inside space-y-1.5 mt-2">
              <li>For violations of these Terms and Conditions</li>
              <li>For conduct that harms other users or the platform</li>
              <li>For non-payment of premium subscription fees (if applicable)</li>
            </ul>
            <p className="mt-2">Upon termination:</p>
            <ul className="list-disc list-inside space-y-1.5 mt-2">
              <li>You will receive a notification at your registered email address</li>
              <li>Access will be revoked immediately for security violations</li>
              <li>You may appeal terminations by contacting support@neurolab.ai within 30 days</li>
              <li>Your data will be retained for 30 days before deletion (unless legally required otherwise)</li>
            </ul>
          </AccordionSection>

          <AccordionSection icon={Mail} title="Contact Information" number="8">
            <p>For legal inquiries and terms-related matters:</p>
            <div className="mt-3 space-y-2">
              <div className="flex items-center gap-2 text-cyan-400">
                <Mail className="w-4 h-4" />
                <span>legal@neurolab.ai</span>
              </div>
              <div className="flex items-center gap-2 text-cyan-400">
                <Mail className="w-4 h-4" />
                <span>support@neurolab.ai</span>
              </div>
              <div className="flex items-center gap-2 text-cyan-400">
                <Globe className="w-4 h-4" />
                <span>neurolab.ai/legal</span>
              </div>
            </div>
            <p className="mt-3 text-xs text-gray-500">These terms are governed by applicable law. Disputes shall be resolved through good-faith negotiation before legal proceedings.</p>
          </AccordionSection>
        </div>

        {/* Footer badge */}
        <div className="p-5 bg-gradient-to-r from-violet-500/10 to-cyan-500/10 border border-violet-500/20 rounded-2xl text-center mb-8">
          <h4 className="text-violet-400 font-black uppercase tracking-widest text-sm mb-2">🛡️ Production-Grade Platform Safety</h4>
          <p className="text-gray-400 text-xs max-w-2xl mx-auto leading-relaxed">
            By using NeuroLab AI, you confirm alignment with responsible AI standards, student safety regulations, and our commitment to ethical STEM education.
          </p>
        </div>

        {/* Nav buttons */}
        <div className="flex flex-wrap justify-center gap-3">
          <button onClick={() => navigate('/privacy')} className="px-5 py-2.5 bg-white/5 border border-white/10 rounded-xl text-sm font-medium text-gray-300 hover:text-white hover:bg-white/8 transition-all flex items-center gap-2">
            <Shield className="w-4 h-4" />
            Privacy Policy
          </button>
          <button onClick={() => navigate('/trust')} className="px-5 py-2.5 bg-gradient-to-r from-violet-500 to-cyan-500 rounded-xl text-white text-sm font-semibold shadow-lg flex items-center gap-2">
            <BadgeCheck className="w-4 h-4" />
            Trust Center
          </button>
          <button onClick={() => navigate('/security')} className="px-5 py-2.5 bg-white/5 border border-white/10 rounded-xl text-sm font-medium text-gray-300 hover:text-white hover:bg-white/8 transition-all flex items-center gap-2">
            <Landmark className="w-4 h-4" />
            Security Center
          </button>
        </div>
      </div>
    </div>
  );
}
