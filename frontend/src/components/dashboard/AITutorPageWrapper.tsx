import React, { useState, useEffect, useRef, Suspense, lazy } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Link, useNavigate } from "react-router-dom";
import { AreaChart, Area, ResponsiveContainer, LineChart, Line, YAxis, XAxis } from "recharts";
import { Zap, Award, Trophy, Flame, Camera, Bot, Play, Pause, ArrowRight, Activity, CheckCircle2, Atom, Clock, Lock, Check, BookOpen, FlaskConical, Settings, Target, Brain, Star, Sparkles, RefreshCw, Sliders } from "lucide-react";
import { pushNotification } from "../../lib/notificationStore";
import { useUserStore } from "../../store/useUserStore";
import { usePhysicsStore } from "../../store/usePhysicsStore";
const AITutorPanel = lazy(() => import("../ai-tutor/AITutorPanel"));

// Component: AITutorPageWrapper
// -------------------------------------------------------------
function AITutorPageWrapper() {
  const suggestedTopics = [
    { title: "Newton's Laws", desc: "Learn about motion and forces", icon: BookOpen },
    { title: "Thermodynamics", desc: "Heat, energy, and entropy", icon: Flame },
    { title: "Quantum Basics", desc: "Introduction to quantum mechanics", icon: Atom },
    { title: "Chemistry 101", desc: "Atomic structure and bonding", icon: FlaskConical }
  ];

  const handleSelectTopic = (title: string) => {
    const event = new CustomEvent('ai-tutor-select-topic', { detail: title });
    window.dispatchEvent(event);
  };

  return (
    <div className="p-6 relative z-10 max-w-7xl mx-auto space-y-6 pt-2">

      {/* Split grid layout */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mt-6">
        {/* Left: Chat Panel */}
        <div className="lg:col-span-2">
          <motion.div
            initial={{ opacity: 0, y: 15 }}
            animate={{ opacity: 1, y: 0 }}
            className="bg-[#0d0d20]/80 rounded-2xl border border-white/10 overflow-hidden shadow-2xl flex flex-col h-[calc(100vh-210px)]"
          >
            <Suspense fallback={
              <div className="flex-1 flex flex-col items-center justify-center text-gray-500 gap-3">
                <div className="w-8 h-8 border-2 border-cyan-500 border-t-transparent rounded-full animate-spin" />
                <p>Initializing AI STEM tutor...</p>
              </div>
            }>
              <AITutorPanel />
            </Suspense>
          </motion.div>
        </div>

        {/* Right: Suggested Topics & Stats */}
        <div className="space-y-6 flex flex-col h-[calc(100vh-210px)] overflow-y-auto pr-1">
          {/* Suggested Topics Card */}
          <div className="bg-white/5 border border-white/10 rounded-2xl p-5 backdrop-blur-sm">
            <h3 className="text-white font-bold mb-4 text-base">Suggested Topics</h3>
            <div className="space-y-3">
              {suggestedTopics.map((topic) => (
                <div
                  key={topic.title}
                  onClick={() => handleSelectTopic(topic.title)}
                  className="p-3.5 bg-white/5 border border-white/5 hover:border-cyan-500/30 hover:bg-white/10 rounded-xl flex items-start gap-3.5 transition-all cursor-pointer group"
                >
                  <div className="w-10 h-10 rounded-lg bg-cyan-500/10 flex items-center justify-center flex-shrink-0 group-hover:bg-cyan-500/20 transition-all">
                    <topic.icon className="w-5 h-5 text-cyan-400" />
                  </div>
                  <div>
                    <h4 className="text-sm font-semibold text-white group-hover:text-cyan-300 transition-colors">
                      {topic.title}
                    </h4>
                    <p className="text-xs text-gray-500 mt-0.5">{topic.desc}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Learning Stats Card */}
          <div className="bg-white/5 border border-white/10 rounded-2xl p-5 backdrop-blur-sm flex-1 flex flex-col justify-between min-h-[200px]">
            <div>
              <h3 className="text-white font-bold mb-4 text-base">Learning Stats</h3>
              <div className="space-y-4">
                <div className="flex justify-between items-center pb-2 border-b border-white/5">
                  <span className="text-sm text-gray-400">Questions Asked</span>
                  <span className="text-base font-extrabold text-white">127</span>
                </div>
                <div className="flex justify-between items-center pb-2 border-b border-white/5">
                  <span className="text-sm text-gray-400">Topics Covered</span>
                  <span className="text-base font-extrabold text-white">24</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-sm text-gray-400">Study Time</span>
                  <span className="text-base font-extrabold text-white">18.5h</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default AITutorPageWrapper;
