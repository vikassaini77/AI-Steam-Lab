import { motion } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, Briefcase, MapPin, Clock, ArrowRight, Star, Github, Mail, ExternalLink } from 'lucide-react';

export default function CareersPage() {
  const navigate = useNavigate();

  const openings = [
    {
      title: "Open Source Full-Stack & STEM Contributor",
      dept: "Core Development",
      location: "Remote (Global)",
      type: "Open Source / Community",
      badge: "Active Community",
      desc: "Contribute to React 18, TypeScript, and FastAPI physics simulations. Help build high-performance WebGL digital twins and accessible laboratory UIs."
    },
    {
      title: "Physics & STEM Curriculum Specialist",
      dept: "Educational Content",
      location: "Remote (Global)",
      type: "Academic Reviewer / Volunteer",
      badge: "Curriculum Advisory",
      desc: "Review Newtonian mechanics solvers, simple harmonic motion, and ballistic equations. Ensure pedagogical rigor aligns with international high school and college standards."
    },
    {
      title: "Computer Vision & Edge ML Researcher",
      dept: "Machine Learning & CV",
      location: "Remote (Global)",
      type: "Research Contributor",
      badge: "Edge Vision",
      desc: "Optimize on-device OpenCV WebAssembly and YOLOv8 ONNX tracking pipelines for low-latency physical centroid detection in web browsers."
    },
    {
      title: "Student & Academic Campus Ambassador",
      dept: "Student Outreach",
      location: "Campus / Remote",
      type: "Student Leadership",
      badge: "Campus Fellowship",
      desc: "Lead live interactive physics demonstrations, host STEM workshops, and introduce hands-on physical-virtual twin laboratories to your school or university."
    }
  ];

  const handleApply = (roleTitle: string) => {
    const encodedSubject = encodeURIComponent(`NeuroLab Opportunity Inquiry: ${roleTitle}`);
    const encodedBody = encodeURIComponent(`Hello NeuroLab Team,\n\nI am interested in contributing as a ${roleTitle}.\n\nGitHub Profile / Portfolio:\nLinkedIn:\nBackground & Motivation:\n\nThank you!`);
    window.open(`mailto:careers@neurolab.ai?subject=${encodedSubject}&body=${encodedBody}`, '_blank');
  };

  return (
    <div className="min-h-screen bg-[#070714] text-white relative overflow-x-hidden">
      {/* Background decoration */}
      <div className="absolute inset-0 z-0 pointer-events-none">
        <div className="absolute top-0 left-1/4 w-[500px] h-[500px] bg-cyan-500/5 rounded-full blur-3xl" />
        <div className="absolute bottom-0 right-1/4 w-[500px] h-[500px] bg-purple-500/5 rounded-full blur-3xl" />
      </div>

      <div className="relative z-10 max-w-4xl mx-auto px-6 py-16">
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
            <Briefcase className="w-7 h-7" />
          </motion.div>
          <h1 className="text-4xl md:text-5xl font-black tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-cyan-400 via-blue-400 to-purple-400">
            Contribute to NeuroLab AI
          </h1>
          <p className="text-gray-400 text-base max-w-2xl mx-auto leading-relaxed">
            Join physicists, educators, and software engineers pioneering voice-guided computer vision STEM laboratories worldwide.
          </p>
        </div>

        {/* Core Pillars Section */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-6 mb-16">
          {[
            { title: "🌍 Open Science", desc: "Openly accessible educational tools empowering students without expensive hardware." },
            { title: "💻 Real-World Impact", desc: "Directly improve STEM comprehension and hands-on laboratory accessibility globally." },
            { title: "🚀 Community Powered", desc: "Collaborate transparently with open-source contributors and academic researchers." }
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
          <div className="flex items-center justify-between border-b border-white/5 pb-3">
            <h3 className="text-lg font-black text-white">Active Research & Contributor Roles</h3>
            <a
              href="https://github.com/vikassaini77/AI-Steam-Lab"
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs text-cyan-400 hover:text-white flex items-center gap-1 transition-colors"
            >
              <Github className="w-3.5 h-3.5" />
              View on GitHub
              <ExternalLink className="w-3 h-3" />
            </a>
          </div>

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
                <div className="flex items-center gap-2">
                  <span className="px-2 py-0.5 bg-cyan-500/10 border border-cyan-500/20 text-[9px] font-extrabold text-cyan-400 rounded-md tracking-wider uppercase">{job.dept}</span>
                  <span className="px-2 py-0.5 bg-purple-500/10 border border-purple-500/20 text-[9px] font-bold text-purple-300 rounded-md tracking-wider uppercase">{job.badge}</span>
                </div>
                <h4 className="text-white font-bold text-base group-hover:text-cyan-400 transition-colors">{job.title}</h4>
                <p className="text-gray-400 text-xs leading-relaxed max-w-2xl">{job.desc}</p>
                <div className="flex flex-wrap gap-4 text-gray-500 text-[10px] pt-1">
                  <span className="flex items-center gap-1"><MapPin className="w-3.5 h-3.5" /> {job.location}</span>
                  <span className="flex items-center gap-1"><Clock className="w-3.5 h-3.5" /> {job.type}</span>
                </div>
              </div>

              <div className="flex items-center gap-2 shrink-0">
                <button 
                  onClick={() => handleApply(job.title)}
                  className="px-4 py-2.5 bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-white text-xs font-semibold rounded-xl transition-all flex items-center gap-1.5 shadow-md shadow-cyan-500/20"
                >
                  <Mail className="w-3.5 h-3.5" />
                  Express Interest
                  <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-0.5 transition-transform" />
                </button>
              </div>
            </motion.div>
          ))}
        </div>

        {/* Direct Contact Banner */}
        <div className="p-6 bg-white/[0.02] border border-white/5 rounded-2xl flex flex-col sm:flex-row items-center justify-between gap-4 text-left">
          <div>
            <h4 className="text-sm font-bold text-white">Have a unique idea or research collaboration?</h4>
            <p className="text-xs text-gray-400 mt-0.5">We welcome curriculum inquiries, university partnerships, and open-source proposals.</p>
          </div>
          <button
            onClick={() => navigate('/contact')}
            className="px-4 py-2 bg-white/5 border border-white/10 hover:border-cyan-500/30 rounded-xl text-xs font-semibold text-gray-300 hover:text-white transition-all whitespace-nowrap"
          >
            Contact the Team
          </button>
        </div>
      </div>
    </div>
  );
}
