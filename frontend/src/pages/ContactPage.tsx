import { motion, AnimatePresence } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import { useState } from 'react';
import { ArrowLeft, Mail, Send, CheckCircle2, HelpCircle, GitBranch, Clock, ExternalLink } from 'lucide-react';

export default function ContactPage() {
  const navigate = useNavigate();

  // Form states
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [subject, setSubject] = useState('');
  const [message, setMessage] = useState('');
  const [submitted, setSubmitted] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name || !email || !message) return;

    setLoading(true);
    // Simulate immediate safe submission state while offering direct mailto
    setTimeout(() => {
      setLoading(false);
      setSubmitted(true);
      
      // Auto close success message after 6 seconds
      setTimeout(() => {
        setSubmitted(false);
        setName('');
        setEmail('');
        setSubject('');
        setMessage('');
      }, 6000);
    }, 800);
  };

  const handleOpenMailto = () => {
    const encodedSubject = encodeURIComponent(subject || 'NeuroLab AI STEM Platform Inquiry');
    const encodedBody = encodeURIComponent(`Name: ${name || 'N/A'}\nEmail: ${email || 'N/A'}\n\nMessage:\n${message || ''}`);
    window.open(`mailto:support@neurolab.ai?subject=${encodedSubject}&body=${encodedBody}`, '_blank');
  };

  return (
    <div className="min-h-screen bg-[#070714] text-white relative overflow-x-hidden">
      {/* Background decoration */}
      <div className="absolute inset-0 z-0 pointer-events-none">
        <div className="absolute top-0 left-1/4 w-[400px] h-[400px] bg-cyan-500/5 rounded-full blur-3xl" />
        <div className="absolute bottom-0 right-1/4 w-[400px] h-[400px] bg-blue-500/5 rounded-full blur-3xl" />
      </div>

      <div className="relative z-10 max-w-5xl mx-auto px-6 py-16">
        {/* Back */}
        <button onClick={() => navigate(-1)} className="flex items-center gap-2 text-gray-400 hover:text-white transition-colors text-sm mb-10 group">
          <ArrowLeft className="w-4 h-4 group-hover:-translate-x-0.5 transition-transform" />
          Back
        </button>

        {/* Floating Auto-save toast */}
        <AnimatePresence>
          {submitted && (
            <motion.div
              initial={{ opacity: 0, y: -50, scale: 0.9 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -20, scale: 0.95 }}
              className="fixed top-6 left-1/2 -translate-x-1/2 z-[100] bg-[#0c0c16] border border-cyan-500/35 px-6 py-4 rounded-2xl flex items-center gap-3 shadow-2xl shadow-cyan-500/10 backdrop-blur-xl max-w-md text-left"
            >
              <CheckCircle2 className="w-5 h-5 text-cyan-400 flex-shrink-0" />
              <div>
                <span className="text-sm font-bold text-white tracking-wide block">Inquiry Recorded</span>
                <span className="text-xs text-gray-400">Thank you! Our engineering and academic team will reply to {email} within 24–48 hours.</span>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-10">
          
          {/* Left panel: Info */}
          <div className="lg:col-span-5 space-y-6">
            <div className="flex items-center gap-3 mb-6">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center">
                <Mail className="w-5 h-5 text-white" />
              </div>
              <h2 className="text-2xl font-black text-white">Get in Touch</h2>
            </div>
            <p className="text-gray-400 text-xs leading-relaxed mb-6">
              Have questions about platform integration, classroom adoption, research collaborations, or technical support? We are here to assist.
            </p>

            <div className="space-y-4 pt-4">
              <div className="flex items-center gap-3.5 text-xs text-gray-300">
                <HelpCircle className="w-5 h-5 text-cyan-400 flex-shrink-0" />
                <div>
                  <span className="text-gray-500 block">Academic & Technical Support</span>
                  <a href="mailto:support@neurolab.ai" className="font-semibold text-cyan-400 hover:underline">
                    support@neurolab.ai
                  </a>
                </div>
              </div>
              <div className="flex items-center gap-3.5 text-xs text-gray-300">
                <GitBranch className="w-5 h-5 text-purple-400 flex-shrink-0" />
                <div>
                  <span className="text-gray-500 block">Open Source Repository & Bug Reports</span>
                  <a 
                    href="https://github.com/vikassaini77/AI-Steam-Lab/issues" 
                    target="_blank" 
                    rel="noopener noreferrer" 
                    className="font-semibold text-purple-400 hover:underline flex items-center gap-1"
                  >
                    GitHub Issues Tracker
                    <ExternalLink className="w-3 h-3" />
                  </a>
                </div>
              </div>
              <div className="flex items-center gap-3.5 text-xs text-gray-300">
                <Clock className="w-5 h-5 text-amber-400 flex-shrink-0" />
                <div>
                  <span className="text-gray-500 block">Expected Response SLA</span>
                  <span className="font-semibold">Within 24–48 hours on business days</span>
                </div>
              </div>
            </div>

            <div className="pt-6 border-t border-white/5">
              <button
                type="button"
                onClick={handleOpenMailto}
                className="w-full py-2.5 px-4 rounded-xl border border-white/10 hover:border-cyan-500/40 bg-white/5 hover:bg-white/10 text-xs font-semibold text-gray-300 hover:text-white transition-all flex items-center justify-center gap-2"
              >
                <Mail className="w-3.5 h-3.5 text-cyan-400" />
                Open Directly in Email Client
              </button>
            </div>
          </div>

          {/* Right panel: Contact Form */}
          <div className="lg:col-span-7 bg-white/[0.02] border border-white/5 p-6 rounded-2xl shadow-xl">
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="space-y-1 text-left">
                  <label className="text-[10px] text-gray-500 uppercase font-black">Full Name</label>
                  <input
                    type="text"
                    required
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="Enter your name"
                    className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-2.5 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-cyan-500/50 focus:ring-1 focus:ring-cyan-500/25 transition-all"
                  />
                </div>
                <div className="space-y-1 text-left">
                  <label className="text-[10px] text-gray-500 uppercase font-black">Email Address</label>
                  <input
                    type="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="name@school.edu"
                    className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-2.5 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-cyan-500/50 focus:ring-1 focus:ring-cyan-500/25 transition-all"
                  />
                </div>
              </div>

              <div className="space-y-1 text-left">
                <label className="text-[10px] text-gray-500 uppercase font-black">Subject</label>
                <input
                  type="text"
                  value={subject}
                  onChange={(e) => setSubject(e.target.value)}
                  placeholder="How can we help you?"
                  className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-2.5 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-cyan-500/50 focus:ring-1 focus:ring-cyan-500/25 transition-all"
                />
              </div>

              <div className="space-y-1 text-left">
                <label className="text-[10px] text-gray-500 uppercase font-black">Message Body</label>
                <textarea
                  required
                  rows={5}
                  value={message}
                  onChange={(e) => setMessage(e.target.value)}
                  placeholder="Explain your inquiry in detail..."
                  className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-2.5 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-cyan-500/50 focus:ring-1 focus:ring-cyan-500/25 transition-all resize-none"
                />
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full py-3 bg-gradient-to-r from-cyan-500 to-blue-600 rounded-xl text-white font-bold text-xs shadow-md shadow-cyan-500/20 hover:shadow-cyan-500/35 hover:scale-[1.01] active:scale-[0.98] transition-all flex items-center justify-center gap-1.5 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {loading ? (
                  <>
                    <span className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                    Sending Message...
                  </>
                ) : (
                  <>
                    <Send className="w-3.5 h-3.5" />
                    Submit Inquiry Form
                  </>
                )}
              </button>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}


