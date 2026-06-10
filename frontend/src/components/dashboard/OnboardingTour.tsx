import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Target, X, ChevronRight, Award, Zap, Atom } from 'lucide-react';

const steps = [
  {
    title: 'Welcome to NeuroLab AI',
    description: 'Your real-time, AI-powered STEM laboratory. We track your physical experiments using Computer Vision and synchronize them into a Digital Twin.',
    icon: <Atom className="w-8 h-8 text-cyan-400" />
  },
  {
    title: 'Interactive Labs',
    description: 'Head over to the Physics Lab to start your first experiment. Our AI Tutor, Professor Nova, will guide you through the physics principles.',
    icon: <Zap className="w-8 h-8 text-amber-400" />
  },
  {
    title: 'Earn XP & Rank Up',
    description: 'Complete calibration quests and quizzes to earn XP. Compete on the Global Leaderboard and unlock new achievements!',
    icon: <Award className="w-8 h-8 text-purple-400" />
  },
  {
    title: 'Ready to begin?',
    description: 'Dive in, explore the lab, and push the boundaries of science!',
    icon: <Target className="w-8 h-8 text-emerald-400" />
  }
];

export default function OnboardingTour() {
  const [isOpen, setIsOpen] = useState(false);
  const [currentStep, setCurrentStep] = useState(0);

  useEffect(() => {
    // Show tour if they haven't seen it yet
    const hasSeenTour = localStorage.getItem('neurolab_tour_completed');
    if (!hasSeenTour) {
      // Delay slightly for dramatic effect
      const timer = setTimeout(() => setIsOpen(true), 1500);
      return () => clearTimeout(timer);
    }
  }, []);

  const handleNext = () => {
    if (currentStep < steps.length - 1) {
      setCurrentStep(currentStep + 1);
    } else {
      closeTour();
    }
  };

  const closeTour = () => {
    setIsOpen(false);
    localStorage.setItem('neurolab_tour_completed', 'true');
  };

  if (!isOpen) return null;

  const step = steps[currentStep];

  return (
    <div className="fixed inset-0 z-[9999] flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/80 backdrop-blur-sm" onClick={closeTour} />
      
      <motion.div
        key={currentStep}
        initial={{ opacity: 0, scale: 0.9, y: 20 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.9, y: 20 }}
        className="relative bg-[#12121a] border border-[#22222f] shadow-2xl rounded-3xl p-8 max-w-md w-full overflow-hidden"
      >
        <div className="absolute inset-0 bg-gradient-to-br from-cyan-500/10 via-transparent to-purple-500/10 pointer-events-none" />
        
        <button 
          onClick={closeTour}
          className="absolute top-4 right-4 p-2 text-gray-500 hover:text-white transition-colors rounded-full hover:bg-white/5"
        >
          <X className="w-5 h-5" />
        </button>

        <div className="flex flex-col items-center text-center space-y-6 relative z-10">
          <div className="w-20 h-20 rounded-full bg-white/5 border border-white/10 flex items-center justify-center relative">
            <div className="absolute inset-0 bg-cyan-500/20 rounded-full blur-xl animate-pulse" />
            {step.icon}
          </div>

          <div className="space-y-3">
            <h2 className="text-2xl font-black text-white tracking-wide">
              {step.title}
            </h2>
            <p className="text-gray-400 leading-relaxed text-sm">
              {step.description}
            </p>
          </div>

          <div className="w-full pt-4 flex items-center justify-between">
            <div className="flex gap-2">
              {steps.map((_, i) => (
                <div 
                  key={i} 
                  className={`h-1.5 rounded-full transition-all duration-300 ${i === currentStep ? 'w-6 bg-cyan-400' : 'w-1.5 bg-white/20'}`} 
                />
              ))}
            </div>

            <button
              onClick={handleNext}
              className="px-6 py-2.5 bg-white text-black font-black rounded-xl text-sm flex items-center gap-2 hover:bg-gray-200 transition-colors"
            >
              {currentStep === steps.length - 1 ? 'Get Started' : 'Next'}
              {currentStep < steps.length - 1 && <ChevronRight className="w-4 h-4" />}
            </button>
          </div>
        </div>
      </motion.div>
    </div>
  );
}
