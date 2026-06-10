import { motion, AnimatePresence } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import { useState } from 'react';
import { ArrowLeft, Mail, Send, CheckCircle2, User, HelpCircle, Phone, MapPin } from 'lucide-react';

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
    setTimeout(() => {
      setLoading(false);
      setSubmitted(true);
      
      // Auto close success message
      setTimeout(() => {
        setSubmitted(false);
        setName('');
        setEmail('');
        setSubject('');
        setMessage('');
      }, 4000);
    }, 1500);
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
              className="fixed top-6 left-1/2 -translate-x-1/2 z-[100] bg-[#0c0c16] border border-cyan-500/35 px-6 py-4 rounded-2xl flex items-center gap-3 shadow-2xl shadow-cyan-500/10 backdrop-blur-xl"
            >
              <CheckCircle2 className="w-5 h-5 text-cyan-400" />
              <span className="text-sm font-bold text-white tracking-wide">Message sent successfully! 🚀</span>
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
              Have questions about platform integration, pricing plans, school credentials, or need support? Drop us a line.
            </p>

            <div className="space-y-4 pt-4">
              <div className="flex items-center gap-3.5 text-xs text-gray-300">
                <HelpCircle className="w-5 h-5 text-cyan-400" />
                <div>
                  <span className="text-gray-500 block">General Support</span>
                  <span className="font-semibold">support@neurolab.ai</span>
                </div>
              </div>
              <div className="flex items-center gap-3.5 text-xs text-gray-300">
                <Phone className="w-5 h-5 text-purple-400" />
                <div>
                  <span className="text-gray-500 block">Phone Support</span>
                  <span className="font-semibold">+1 (800) 555-STEM</span>
                </div>
              </div>
              <div className="flex items-center gap-3.5 text-xs text-gray-300">
                <MapPin className="w-5 h-5 text-amber-400" />
                <div>
                  <span className="text-gray-500 block">Corporate Address</span>
                  <span className="font-semibold">100 Cybernetic Way, Silicon Valley</span>
                </div>
              </div>
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


