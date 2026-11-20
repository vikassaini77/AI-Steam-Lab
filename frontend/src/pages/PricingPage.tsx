import { motion } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, Sparkles, Check, HelpCircle, Mail } from 'lucide-react';

export default function PricingPage() {
  const navigate = useNavigate();

  const plans = [
    {
      name: "Student Scholar",
      price: "$0",
      period: "free forever",
      desc: "For curious students exploring fundamental mechanics.",
      features: [
        "All 6 interactive physics simulation engines",
        "Client-side Edge CV color tracking (100% local)",
        "AI Science Roundtable pedagogical guidance",
        "Real-time Kinetic/Potential energy telemetry",
        "Gamified XP, badges & scholar achievements"
      ],
      cta: "Launch Free Lab",
      popular: false
    },
    {
      name: "Classroom & Teachers",
      price: "$0",
      period: "free forever",
      desc: "Empowering STEM teachers and science classes.",
      features: [
        "Unlimited interactive laboratory runs",
        "Instant publication-ready PDF lab report exports",
        "Pre-configured inquiry challenges & quests",
        "Classroom live demonstrations & digital twin sync",
        "Authentic kinematics error analysis"
      ],
      cta: "Open Experiments",
      popular: true
    },
    {
      name: "Open Science Researchers",
      price: "$0",
      period: "open access",
      desc: "For university physics students and research projects.",
      features: [
        "High-frequency telemetry & velocity extraction",
        "Taylor approximation & damping coefficient proofs",
        "Offline local storage persistence",
        "Interactive STEM sample lab feed (30 FPS)",
        "Scientific data provenance logging"
      ],
      cta: "Explore Research Labs",
      popular: false
    },
    {
      name: "Academic Institutions",
      price: "Free",
      period: "open source",
      desc: "Open access deployment for school districts & universities.",
      features: [
        "Zero per-seat licensing or subscription fees",
        "Self-contained client-side architecture",
        "Compatible with Chromebooks, PCs, and Cloud Agents",
        "Open Educational Resources (OER) aligned",
        "Community driven on GitHub"
      ],
      cta: "View Documentation",
      popular: false
    }
  ];

  return (
    <div className="min-h-screen bg-[#070714] text-white relative overflow-x-hidden">
      {/* Background gradients */}
      <div className="absolute inset-0 z-0 pointer-events-none">
        <div className="absolute top-0 left-1/3 w-[500px] h-[500px] bg-cyan-500/5 rounded-full blur-3xl" />
        <div className="absolute bottom-0 right-1/3 w-[500px] h-[500px] bg-purple-600/5 rounded-full blur-3xl" />
        <div className="absolute inset-0 opacity-[0.02]" style={{
          backgroundImage: 'linear-gradient(rgba(6,182,212,0.4) 1px, transparent 1px), linear-gradient(90deg, rgba(6,182,212,0.4) 1px, transparent 1px)',
          backgroundSize: '60px 60px'
        }} />
      </div>

      <div className="relative z-10 max-w-6xl mx-auto px-6 py-16">
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
            className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-cyan-500/15 border border-cyan-500/30 text-cyan-400 mb-2"
          >
            <Sparkles className="w-7 h-7" />
          </motion.div>
          <h1 className="text-4xl md:text-5xl font-black tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-cyan-400 via-blue-400 to-purple-400">
            Open Access STEM Education
          </h1>
          <p className="text-gray-400 text-base max-w-2xl mx-auto leading-relaxed">
            NeuroLab AI is 100% free and open-access for students, teachers, and researchers worldwide. Zero subscription fees, zero paywalls.
          </p>
        </div>

        {/* Pricing Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-16">
          {plans.map((p, i) => (
            <motion.div
              key={p.name}
              initial={{ opacity: 0, y: 15 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.05 }}
              className={`p-6 rounded-2xl border flex flex-col justify-between relative transition-all hover:scale-[1.01] ${
                p.popular 
                  ? 'bg-gradient-to-b from-[#131326] to-[#0c0c16] border-cyan-500/40 shadow-lg shadow-cyan-500/10' 
                  : 'bg-white/[0.02] border-white/5'
              }`}
            >
              {p.popular && (
                <span className="absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-1 bg-cyan-500 text-black text-[9px] font-black uppercase rounded-full tracking-widest shadow-md">
                  Recommended
                </span>
              )}
              
              <div>
                <h3 className="text-white font-bold text-lg mb-2">{p.name}</h3>
                <p className="text-gray-500 text-xs mb-5 min-h-[32px]">{p.desc}</p>
                <div className="flex items-baseline gap-1 mb-6">
                  <span className="text-4xl font-black text-white">{p.price}</span>
                  <span className="text-gray-500 text-xs">/ {p.period}</span>
                </div>
                
                <ul className="space-y-3 mb-8">
                  {p.features.map((f) => (
                    <li key={f} className="flex gap-2.5 items-start text-xs text-gray-300">
                      <Check className="w-4 h-4 text-cyan-400 flex-shrink-0 mt-0.5" />
                      <span>{f}</span>
                    </li>
                  ))}
                </ul>
              </div>

              <button 
                onClick={() => {
                  if (p.name === 'Academic Institutions') {
                    navigate('/docs');
                  } else if (p.name === 'Classroom & Teachers' || p.name === 'Open Science Researchers') {
                    navigate('/dashboard/experiments');
                  } else {
                    navigate('/dashboard');
                  }
                }}
                className={`w-full py-2.5 rounded-xl font-bold text-xs transition-all ${
                  p.popular 
                    ? 'bg-gradient-to-r from-cyan-500 to-blue-600 text-white shadow-md shadow-cyan-500/20 hover:shadow-cyan-500/35 hover:scale-[1.02]' 
                    : 'bg-white/5 border border-white/10 text-white hover:bg-white/10'
                }`}
              >
                {p.cta}
              </button>
            </motion.div>
          ))}
        </div>

        {/* FAQ section banner */}
        <div className="p-6 bg-white/[0.02] border border-white/5 rounded-2xl flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <HelpCircle className="w-5 h-5 text-purple-400" />
            <div className="text-left">
              <h4 className="text-white font-bold text-sm">Need educational onboarding or workshop materials?</h4>
              <p className="text-gray-500 text-xs">We provide free curriculum alignment guides, lesson plans, and laboratory worksheets for educators.</p>
            </div>
          </div>
          <button onClick={() => navigate('/contact')} className="px-4 py-2 bg-white/5 border border-white/10 rounded-xl text-gray-300 hover:text-white text-xs font-semibold hover:bg-white/8 transition-all flex items-center gap-1.5">
            <Mail className="w-3.5 h-3.5" />
            Contact Team
          </button>
        </div>
      </div>
    </div>
  );
}
