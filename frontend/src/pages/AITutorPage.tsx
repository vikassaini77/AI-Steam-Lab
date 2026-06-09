import React, { useState } from 'react';
import { motion } from 'framer-motion';
import AITutorSidebar from '../components/ai-tutor/AITutorSidebar';
import AITutorPanel from '../components/ai-tutor/AITutorPanel';

export default function AITutorPage() {
  const [sidebarOpen, setSidebarOpen] = useState(true);

  return (
    <div className="fixed inset-0 flex overflow-hidden bg-[#070714] text-gray-100 font-sans">
      {/* Sidebar Component */}
      <AITutorSidebar 
        isOpen={sidebarOpen} 
        onToggle={() => setSidebarOpen(!sidebarOpen)} 
      />

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col relative h-full bg-[#070714]">
        {/* Animated Background Layers */}
        <div className="absolute inset-0 z-0 overflow-hidden pointer-events-none">
          {/* Animated floating orbs */}
          <motion.div
            animate={{
              x: [0, 100, -50, 0],
              y: [0, -100, 50, 0],
              scale: [1, 1.2, 0.8, 1],
            }}
            transition={{ duration: 25, repeat: Infinity, ease: "easeInOut" }}
            className="absolute top-1/4 left-1/4 w-[40vw] h-[40vw] bg-cyan-500/10 rounded-full blur-[100px]"
          />
          <motion.div
            animate={{
              x: [0, -100, 50, 0],
              y: [0, 100, -50, 0],
              scale: [1, 1.5, 0.9, 1],
            }}
            transition={{ duration: 30, repeat: Infinity, ease: "easeInOut", delay: 2 }}
            className="absolute bottom-1/4 right-1/4 w-[35vw] h-[35vw] bg-blue-600/10 rounded-full blur-[120px]"
          />
          <motion.div
            animate={{
              x: [0, 50, -100, 0],
              y: [0, 50, 100, 0],
              scale: [1, 0.8, 1.2, 1],
            }}
            transition={{ duration: 20, repeat: Infinity, ease: "easeInOut", delay: 5 }}
            className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[30vw] h-[30vw] bg-purple-500/10 rounded-full blur-[90px]"
          />
          
          {/* Subtle grid overlay */}
          <div className="absolute inset-0 bg-[url('/grid.svg')] bg-center [mask-image:linear-gradient(180deg,rgba(0,0,0,0.8),transparent)] opacity-10" />
        </div>

        {/* Foreground Panel */}
        <div className="relative z-10 w-full flex-1 flex flex-col">
          <AITutorPanel />
        </div>
      </div>
    </div>
  );
}
