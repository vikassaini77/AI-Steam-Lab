import { motion } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, Briefcase, MapPin, Clock, ArrowRight, Star } from 'lucide-react';

export default function CareersPage() {
  const navigate = useNavigate();

  const openings = [
    {
      title: "AI Research Scientist (Gemini / LLMs)",
      dept: "Artificial Intelligence",
      location: "San Francisco, CA (Hybrid)",
      type: "Full-Time",
      salary: "$140,000 - $185,000",
      desc: "Integrate LLM contextual graphs with raw real-time physics measurements to produce highly educational, voice-synthesized STEM dialogues."
    },
    {
      title: "Computer Vision Engineer (OpenCV / PyTorch)",
      dept: "Machine Learning / Robotics",
      location: "Remote (Global)",
      type: "Full-Time",
      salary: "$130,000 - $170,000",
      desc: "Optimize on-device WebRTC camera streaming frames processing. Refine YOLOv8 neural box networks for small-angle object tracking."
    },
    {
      title: "Full-Stack Engineer (FastAPI / React)",
      dept: "Product Development",
      location: "Silicon Valley, CA (On-site)",
      type: "Full-Time",
      salary: "$120,000 - $155,000",
      desc: "Architect clean routing endpoints and robust Supabase authentication models. Build dynamic side-by-side SVG Digital Twin dashboards."
    },
    {
      title: "STEM Curriculum Architect (Physics Specialists)",
      dept: "Educational Content",
      location: "Remote (USA/India)",
      type: "Part-Time / Contract",
      salary: "$80 - $110 / hour",
      desc: "Design detailed physical solvers properties frameworks (e.g. Hooks springs, collisions, waves) mapping to structured high school curricula."
    }
  ];

  return (
    <div className="min-h-screen bg-[#070714] text-white relative overflow-hidden">
      {/* Background decoration */}
      <div className="absolute inset-0 z-0 pointer-events-none">
        <div className="absolute top-0 left-1/4 w-[500px] h-[500px] bg-cyan-500/5 rounded-full blur-3xl" />
        <div className="absolute bottom-0 right-1/4 w-[500px] h-[500px] bg-purple-500/5 rounded-full blur-3xl" />
      </div>

      <div className="relative z-10 max-w-4xl mx-auto px-6 py-16">
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
            <Briefcase className="w-7 h-7" />
          </motion.div>
          <h1 className="text-4xl md:text-5xl font-black tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-cyan-400 via-blue-400 to-purple-400">
            Join the NeuroLab Team
          </h1>
          <p className="text-gray-400 text-base max-w-2xl mx-auto leading-relaxed">
            Build the next generation of voice-guided computer vision STEM platforms.
          </p>
        </div>

        {/* Perks Section */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-6 mb-16">
          {[
            { title: "🌍 Remote-First Work", desc: "Collaborate with talented physicists and engineers globally." },
            { title: "🏥 Premium Benefits", desc: "Comprehensive health insurance, dental coverage, and wellness support." },
            { title: "📈 Equity Packages", desc: "Own a piece of the platform with high-growth startup equity." }
          ].map((perk) => (
            <div key={perk.title} className="p-5 rounded-2xl border border-white/5 bg-white/[0.01] hover:border-cyan-500/20 transition-all text-left">
              <Star className="w-5 h-5 text-cyan-400 mb-3" />
              <h4 className="text-white font-bold text-sm mb-1">{perk.title}</h4>
              <p className="text-gray-500 text-xs leading-relaxed">{perk.desc}</p>
            </div>
          ))}
        </div>

        {/* Openings Listing */}
        <div className="space-y-6 mb-12 text-left">
          <h3 className="text-lg font-black text-white border-b border-white/5 pb-2">Active Opportunities</h3>
          {openings.map((job, idx) => (
            <motion.div
              key={job.title}
              initial={{ opacity: 0, x: -10 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true }}
              transition={{ delay: idx * 0.05 }}
              className="p-6 rounded-2xl border border-white/5 bg-white/[0.02] hover:bg-white/[0.03] hover:border-cyan-500/20 transition-all flex flex-col md:flex-row justify-between items-start md:items-center gap-4 group"
            >
              <div className="space-y-2 flex-1">
                <span className="px-2 py-0.5 bg-cyan-500/10 border border-cyan-500/20 text-[9px] font-extrabold text-cyan-400 rounded-md tracking-wider uppercase">{job.dept}</span>
                <h4 className="text-white font-bold text-base group-hover:text-cyan-400 transition-colors">{job.title}</h4>
                <p className="text-gray-400 text-xs leading-relaxed max-w-2xl">{job.desc}</p>
                <div className="flex flex-wrap gap-4 text-gray-500 text-[10px] pt-1">
                  <span className="flex items-center gap-1"><MapPin className="w-3.5 h-3.5" /> {job.location}</span>
                  <span className="flex items-center gap-1"><Clock className="w-3.5 h-3.5" /> {job.type}</span>
                  <span className="text-cyan-400/80 font-mono font-bold">{job.salary}</span>
                </div>
              </div>

              <button 
                onClick={() => navigate('/contact')}
                className="px-4 py-2.5 bg-white/5 border border-white/10 hover:border-cyan-500/40 text-white hover:text-cyan-400 text-xs font-semibold rounded-xl transition-all flex items-center gap-1 shrink-0"
              >
                Apply Now
                <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-0.5 transition-transform" />
              </button>
            </motion.div>
          ))}
        </div>
      </div>
    </div>
  );
}
