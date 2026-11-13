import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, BookOpen, Clock, ChevronRight, X, Sparkles, Share2, Check } from 'lucide-react';

interface BlogPost {
  id: string;
  title: string;
  category: string;
  readTime: string;
  date: string;
  desc: string;
  content: {
    lead: string;
    sections: {
      heading: string;
      body: string;
      takeaway?: string;
    }[];
  };
}

const POSTS: BlogPost[] = [
  {
    id: "ai-stem-labs",
    title: "Pioneering the Shift to Interactive AI STEM Labs",
    category: "STEM Education",
    readTime: "6 min read",
    date: "May 28, 2026",
    desc: "Discover how voice-enabled physical-virtual twin synchronization is boosting classroom interest and mathematical comprehension globally.",
    content: {
      lead: "For decades, secondary and collegiate physics laboratories have faced a fundamental pedagogical barrier: the disconnect between theoretical equations written on paper and physical observations gathered during hands-on experiments.",
      sections: [
        {
          heading: "The Challenge of Passive Science Education",
          body: "Traditional laboratory manuals guide students through rigid, recipe-style procedures. Learners often follow step-by-step instructions without truly engaging with the underlying mathematical models. When their measured results deviate from expected textbook values, they lack instantaneous feedback to explain why the discrepancy occurred.",
          takeaway: "Passive labs emphasize following procedural steps rather than developing experimental intuition."
        },
        {
          heading: "Physical-Virtual Twin Synchronization",
          body: "NeuroLab bridges this gap by introducing physical-virtual twin synchronization. As a student releases a pendulum bob or launches a projectile, the platform's vision engine tracks the trajectory at 60 frames per second, continuously comparing the physical state with Newtonian differential equations running in the browser.",
          takeaway: "Students see mathematical prediction curves overlaid directly on top of physical video feeds in real time."
        },
        {
          heading: "Voice-Guided Socratic Interventions",
          body: "Rather than simply highlighting errors, Professor Nova utilizes a Socratic pedagogical model. If a student's harmonic oscillator displays unexpected damping, the AI voice tutor prompts: 'Notice how the oscillation amplitude is decaying exponentially. What environmental factor could be dissipating mechanical energy?' This conversational inquiry encourages deductive problem solving.",
          takeaway: "Real-time speech feedback transforms confusion into active scientific discovery."
        }
      ]
    }
  },
  {
    id: "opencv-optimizations",
    title: "Local on-device OpenCV Bounding Box Optimizations",
    category: "Computer Vision",
    readTime: "8 min read",
    date: "May 24, 2026",
    desc: "An in-depth look at frame-grabbing, color target thresholding and low-latency YOLOv8 integrations within direct client browser sandboxes.",
    content: {
      lead: "Transmitting full HD camera feeds to a remote GPU server introduces bandwidth saturation, latency spikes, and severe student privacy vulnerabilities. Here is how we engineered high-frequency tracking directly inside client browser sandboxes.",
      sections: [
        {
          heading: "Zero-Server Video Architecture",
          body: "Student webcam frames never leave the user's local machine. All image acquisition runs through navigator.mediaDevices.getUserMedia and is rendered to an OffscreenCanvas with hardware acceleration. This guarantees complete compliance with COPPA, FERPA, and strict institutional privacy standards.",
          takeaway: "Client-side processing eliminates external server costs and safeguards student privacy."
        },
        {
          heading: "High-Speed HSV Thresholding Pipeline",
          body: "For primary motion tracking (such as brightly colored pendulum bobs and projectile markers), we execute optimized HSV color space conversions in WebGL shaders. By performing morphological erosion and dilation on the downsampled frame, we achieve centroid detection within 4 milliseconds.",
          takeaway: "Sub-pixel centroid localization runs smoothly at 60 FPS even on low-cost school Chromebooks."
        },
        {
          heading: "Deep Learning Fallback with YOLOv8 ONNX Web",
          body: "When testing irregular laboratory apparatus or varying lighting conditions, the engine falls back to a quantized YOLOv8 nano model executed via ONNX Runtime Web using WebAssembly and WebGPU backends. This hybrid approach yields robust detection confidence across diverse classroom environments.",
          takeaway: "Quantized neural networks provide robust object segmentation without requiring dedicated workstation GPUs."
        }
      ]
    }
  },
  {
    id: "gamified-pathways",
    title: "Designing Gamified Quest Pathways for Physics Learners",
    category: "AI Learning",
    readTime: "5 min read",
    date: "May 19, 2026",
    desc: "How structured XP leaderboards, streak rewards multipliers, and physical verification triggers convert science curricula into gaming pathways.",
    content: {
      lead: "Educational psychology demonstrates that self-efficacy and sustained engagement are dramatically enhanced when challenging STEM competencies are structured into incremental, rewarding progression loops.",
      sections: [
        {
          heading: "The Danger of Superficial Gamification",
          body: "Many educational apps rely on superficial rewards—arbitrary points and confetti animations that feel childish to serious secondary and collegiate students. Meaningful gamification must tie directly to verified scientific milestones rather than passive screen time.",
          takeaway: "Gamification succeeds only when rewards celebrate genuine intellectual mastery."
        },
        {
          heading: "Physical Verification Triggers",
          body: "In NeuroLab, XP is not awarded simply for reading text or watching animations. Experience points and achievement badges unlock when a student designs an experiment whose physical trajectory matches theoretical kinematics within an authentic error margin (e.g. within 5% error on gravitational acceleration g).",
          takeaway: "XP is backed by verified physical empirical data, creating genuine scientific pride."
        },
        {
          heading: "Collaborative and Competitive Dynamics",
          body: "Classroom leaderboards foster healthy academic excitement. Students collaborate to discover parameters that optimize mechanical efficiency, sharing experimental data logs with peers and teachers in real time.",
          takeaway: "Peer transparency motivates students to iterate and refine their scientific methodology."
        }
      ]
    }
  },
  {
    id: "formula-to-speech",
    title: "Translating Complex Physics Formulas into Fluent Speech",
    category: "Physics Learning",
    readTime: "7 min read",
    date: "May 12, 2026",
    desc: "Our structural engineering approach to parsing LaTeX equations, removing robotic jargon, and rendering clear conversational tutoring voices.",
    content: {
      lead: "When students are hands-on with physical apparatus, forcing them to look back and forth between equipment and a computer screen creates cognitive splintering. Voice interaction solves this—provided the AI can speak mathematical notation naturally.",
      sections: [
        {
          heading: "The LaTeX Pronunciation Problem",
          body: "Standard text-to-speech engines read raw LaTeX or mathematical equations literally: 'backslash f r a c left curly brace...'. This robotic output is incomprehensible during laboratory workflows and frustrates learners.",
          takeaway: "Literal equation readings create auditory noise rather than educational clarity."
        },
        {
          heading: "Semantic Mathematical AST Parsing",
          body: "NeuroLab parses algebraic expressions into semantic Abstract Syntax Trees (ASTs). The AST identifies physical contexts: a fraction containing m*v^2/r is translated into 'centripetal acceleration times mass' or 'mass times velocity squared over radius', adapting dynamically to the student's current grade tier.",
          takeaway: "Context-aware AST parsing ensures equations sound natural and intuitive."
        },
        {
          heading: "Conversational Laboratory Pacing",
          body: "Audio responses are throttled and phrased concisely. Rather than reciting long derivations, Professor Nova breaks insights into 15-second conversational bites, giving students time to adjust their physical apparatus between verbal hints.",
          takeaway: "Bite-sized auditory guidance preserves student focus on hands-on physical manipulation."
        }
      ]
    }
  }
];

export default function BlogPage() {
  const navigate = useNavigate();
  const [selectedPost, setSelectedPost] = useState<BlogPost | null>(null);
  const [copied, setCopied] = useState(false);

  const handleShare = (postTitle: string) => {
    if (navigator.clipboard) {
      navigator.clipboard.writeText(`${window.location.origin}/blog - ${postTitle}`);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div className="min-h-screen bg-[#070714] text-white relative overflow-x-hidden">
      {/* Gradients */}
      <div className="absolute inset-0 z-0 pointer-events-none">
        <div className="absolute top-0 left-1/4 w-[400px] h-[400px] bg-cyan-500/5 rounded-full blur-3xl" />
        <div className="absolute bottom-0 right-1/4 w-[400px] h-[400px] bg-purple-600/5 rounded-full blur-3xl" />
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
            className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-cyan-500/15 border border-cyan-500/30 text-cyan-400 mb-2"
          >
            <BookOpen className="w-7 h-7" />
          </motion.div>
          <h1 className="text-4xl md:text-5xl font-black tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-cyan-400 via-blue-400 to-purple-400">
            NeuroLab Scientific Articles
          </h1>
          <p className="text-gray-400 text-base max-w-2xl mx-auto leading-relaxed">
            In-depth pedagogical research, computer vision architecture, and the future of multimodal STEM learning.
          </p>
        </div>

        {/* Blog Posts Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-12 text-left">
          {POSTS.map((post, idx) => (
            <motion.div
              key={post.id}
              initial={{ opacity: 0, y: 15 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: idx * 0.05 }}
              className="p-6 rounded-2xl border border-white/5 bg-white/[0.02] hover:bg-white/[0.04] hover:border-cyan-500/30 transition-all flex flex-col justify-between group cursor-pointer shadow-lg shadow-black/20"
              onClick={() => setSelectedPost(post)}
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
                <span className="flex items-center gap-1 text-cyan-400 hover:text-white font-bold uppercase tracking-wider transition-colors">
                  Read Article
                  <ChevronRight className="w-3.5 h-3.5 group-hover:translate-x-0.5 transition-transform" />
                </span>
              </div>
            </motion.div>
          ))}
        </div>
      </div>

      {/* Full Article Reader Modal */}
      <AnimatePresence>
        {selectedPost && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 bg-black/80 backdrop-blur-md overflow-y-auto">
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 20 }}
              className="relative w-full max-w-3xl bg-[#0c0c1a] border border-cyan-500/30 rounded-3xl p-6 sm:p-10 shadow-2xl max-h-[90vh] overflow-y-auto my-auto text-left"
            >
              {/* Close Button */}
              <button
                onClick={() => setSelectedPost(null)}
                className="absolute top-6 right-6 p-2 rounded-xl bg-white/5 hover:bg-white/10 text-gray-400 hover:text-white transition-colors"
              >
                <X className="w-5 h-5" />
              </button>

              {/* Meta */}
              <div className="flex items-center gap-3 text-xs text-gray-400 mb-4">
                <span className="px-2.5 py-1 rounded-full bg-cyan-500/10 border border-cyan-500/20 text-cyan-400 font-semibold uppercase tracking-wider text-[10px]">
                  {selectedPost.category}
                </span>
                <span>•</span>
                <span>{selectedPost.date}</span>
                <span>•</span>
                <span className="flex items-center gap-1"><Clock className="w-3 h-3" /> {selectedPost.readTime}</span>
              </div>

              {/* Title */}
              <h2 className="text-2xl sm:text-3xl font-black text-white mb-6 leading-tight">
                {selectedPost.title}
              </h2>

              {/* Lead Paragraph */}
              <div className="p-4 rounded-2xl bg-cyan-500/5 border border-cyan-500/20 text-cyan-200 text-sm leading-relaxed mb-8 font-medium">
                {selectedPost.content.lead}
              </div>

              {/* Article Sections */}
              <div className="space-y-8 text-gray-300 text-sm leading-relaxed">
                {selectedPost.content.sections.map((sec, i) => (
                  <div key={i} className="space-y-3">
                    <h3 className="text-lg font-bold text-white flex items-center gap-2">
                      <span className="w-2 h-2 rounded-full bg-cyan-400" />
                      {sec.heading}
                    </h3>
                    <p className="text-gray-300 leading-relaxed">
                      {sec.body}
                    </p>
                    {sec.takeaway && (
                      <div className="pl-4 border-l-2 border-cyan-500/50 italic text-xs text-gray-400 py-1">
                        Key Takeaway: {sec.takeaway}
                      </div>
                    )}
                  </div>
                ))}
              </div>

              {/* Footer action bar */}
              <div className="mt-10 pt-6 border-t border-white/10 flex flex-wrap items-center justify-between gap-4">
                <button
                  onClick={() => handleShare(selectedPost.title)}
                  className="px-4 py-2 rounded-xl border border-white/10 bg-white/5 hover:bg-white/10 text-xs font-semibold text-gray-300 flex items-center gap-2 transition-all"
                >
                  {copied ? <Check className="w-4 h-4 text-green-400" /> : <Share2 className="w-4 h-4 text-cyan-400" />}
                  {copied ? 'Link Copied!' : 'Share Article'}
                </button>

                <div className="flex items-center gap-3">
                  <button
                    onClick={() => {
                      setSelectedPost(null);
                      navigate('/dashboard/experiments');
                    }}
                    className="px-5 py-2 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 text-white font-bold text-xs shadow-lg shadow-cyan-500/20 hover:scale-[1.02] transition-all flex items-center gap-1.5"
                  >
                    <Sparkles className="w-3.5 h-3.5" />
                    Try In Live Lab
                  </button>
                </div>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
}


