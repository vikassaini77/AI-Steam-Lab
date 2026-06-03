import { motion } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, BookOpen, Clock, ChevronRight } from 'lucide-react';

export default function BlogPage() {
  const navigate = useNavigate();

  const posts = [
    {
      title: "Pioneering the Shift to Interactive AI STEM Labs",
      category: "STEM Education",
      readTime: "6 min read",
      date: "May 28, 2026",
      desc: "Discover how voice-enabled physical-virtual twin synchronization is boosting classroom interest and mathematical comprehension globally."
    },
    {
      title: "Local on-device OpenCV Bounding Box Optimizations",
      category: "Computer Vision",
      readTime: "8 min read",
      date: "May 24, 2026",
      desc: "An in-depth look at frame-grabbing, color target thresholding and low-latency YOLOv8 integrations within direct client browser sandboxes."
    },
    {
      title: "Designing Gamified Quest Pathways for Physics Learners",
      category: "AI Learning",
      readTime: "5 min read",
      date: "May 19, 2026",
      desc: "How structured XP leaderboards, streak rewards multipliers, and physical verification triggers convert science curricula into gaming pathways."
    },
    {
      title: "Translating Complex Physics Formulas into Fluent Speech",
      category: "Physics Learning",
      readTime: "7 min read",
      date: "May 12, 2026",
      desc: "Our structural engineering approach to parsing LaTeX equations, removing robotic jargon, and rendering clear conversational tutoring voices."
    }
  ];

  return (
    <div className="min-h-screen bg-[#070714] text-white relative overflow-hidden">
      {/* Gradients */}
      <div className="absolute inset-0 z-0 pointer-events-none">
        <div className="absolute top-0 left-1/4 w-[400px] h-[400px] bg-cyan-500/5 rounded-full blur-3xl" />
        <div className="absolute bottom-0 right-1/4 w-[400px] h-[400px] bg-purple-600/5 rounded-full blur-3xl" />
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
            <BookOpen className="w-7 h-7" />
          </motion.div>
          <h1 className="text-4xl md:text-5xl font-black tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-cyan-400 via-blue-400 to-purple-400">
            NeuroLab Scientific Blog
          </h1>
          <p className="text-gray-400 text-base max-w-2xl mx-auto leading-relaxed">
            Latest insights in AI tutoring, on-device computer vision, and interactive STEM education.
          </p>
        </div>

        {/* Blog Posts Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-12 text-left">
          {posts.map((post, idx) => (
            <motion.div
              key={post.title}
              initial={{ opacity: 0, y: 15 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: idx * 0.05 }}
              className="p-6 rounded-2xl border border-white/5 bg-white/[0.02] hover:bg-white/[0.03] hover:border-cyan-500/20 transition-all flex flex-col justify-between group cursor-pointer"
              onClick={() => navigate('/docs')}
            >
              <div>
                <div className="flex justify-between items-center text-[10px] text-gray-500 font-bold uppercase tracking-wider mb-3">
                  <span className="text-cyan-400">{post.category}</span>
                  <span className="flex items-center gap-1"><Clock className="w-3 h-3" /> {post.readTime}</span>
                </div>
                <h3 className="text-white font-bold text-base mb-2 group-hover:text-cyan-400 transition-colors leading-snug">{post.title}</h3>
                <p className="text-gray-400 text-xs leading-relaxed mb-6">{post.desc}</p>
              </div>

              <div className="flex justify-between items-center border-t border-white/5 pt-4 text-[10px] text-gray-500">
                <span>{post.date}</span>
                <span className="flex items-center gap-0.5 text-cyan-400 hover:text-white font-bold uppercase tracking-wider transition-colors">
                  Read Article
                  <ChevronRight className="w-3.5 h-3.5 group-hover:translate-x-0.5 transition-transform" />
                </span>
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </div>
  );
}
