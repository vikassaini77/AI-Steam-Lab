import { motion } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, Sparkles, Check, HelpCircle, Mail } from 'lucide-react';

export default function PricingPage() {
  const navigate = useNavigate();

  const plans = [
    {
      name: "Free Student",
      price: "$0",
      period: "forever",
      desc: "For young scientists exploring basic mechanics.",
      features: [
        "10 monthly Live Lab sessions",
        "Professor Nova AI STEM responses",
        "HSV Color Tracking model",
        "Basic Kinetic/Potential energy graphs",
        "Standard achievements & badges"
      ],
      cta: "Get Started Free",
      popular: false
    },
    {
      name: "Student Pro",
      price: "$9",
      period: "monthly",
      desc: "Our most popular tier for advanced researchers.",
      features: [
        "Unlimited Live Lab sessions",
        "Uncapped high-priority Professor Nova",
        "YOLOv8 Deep Learning object tracker",
        "FastAPI scientific PDF downloads",
        "Extended trajectory analytics",
        "Exclusive Gravity Pioneer badges"
      ],
      cta: "Go Pro Now",
      popular: true
    },
    {
      name: "Institution",
      price: "$49",
      period: "monthly",
      desc: "Designed for school departments and STEM labs.",
      features: [
        "Up to 50 active students accounts",
        "Teacher dashboard & grading analytics",
        "Classroom challenges & XP leaderboards",
        "Shared cloud experimental reports",
        "CSV analytical data logs export",
        "Dedicated onboarding support"
      ],
      cta: "Upgrade Classroom",
      popular: false
    },
    {
      name: "Enterprise",
      price: "Custom",
      period: "yearly pricing",
      desc: "Custom deployment for university boards.",
      features: [
        "Unlimited campus-wide user licenses",
        "Local network hardware server hosting",
        "Custom computer vision API integrations",
        "SSO, SAML & secure school logins",
        "Dedicated account science manager",
        "Custom branding & syllabus alignment"
      ],
      cta: "Contact Enterprise",
      popular: false
    }
  ];

  return (
    <div className="min-h-screen bg-[#070714] text-white relative overflow-hidden">
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
        <button onClick={() => navigate('/')} className="flex items-center gap-2 text-gray-400 hover:text-white transition-colors text-sm mb-10 group">
          <ArrowLeft className="w-4 h-4 group-hover:-translate-x-0.5 transition-transform" />
          Back to Home
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
            Harmonious SaaS Pricing
          </h1>
          <p className="text-gray-400 text-base max-w-2xl mx-auto leading-relaxed">
            Accessible price plans tailored for single students, school classrooms, and global universities.
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
                  Most Popular
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
                onClick={() => navigate('/')}
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
              <h4 className="text-white font-bold text-sm">Have specific custom requirements?</h4>
              <p className="text-gray-500 text-xs">We customize billing plans for large institutions, academies, and university blocks.</p>
            </div>
          </div>
          <button onClick={() => navigate('/contact')} className="px-4 py-2 bg-white/5 border border-white/10 rounded-xl text-gray-300 hover:text-white text-xs font-semibold hover:bg-white/8 transition-all flex items-center gap-1.5">
            <Mail className="w-3.5 h-3.5" />
            Contact Sales
          </button>
        </div>
      </div>
    </div>
  );
}
