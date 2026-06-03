import { motion } from 'framer-motion';
import { useEffect, useState } from 'react';
import { Video, Cpu, Gauge, MessageSquare, ArrowRight } from 'lucide-react';

const detections = [
  { label: 'Pendulum', confidence: 98, x: 20, y: 15, w: 35, h: 50 },
  { label: 'Weight', confidence: 95, x: 55, y: 40, w: 25, h: 30 },
];


const aiResponses = [
  'Analyzing pendulum motion...',
  'Period detected: 1.2 seconds',
  'Gravitational acceleration: 9.8 m/s²',
  'Energy conservation verified',
];

interface DemoPreviewProps {
  onLaunchLab?: () => void;
}

export default function DemoPreview({ onLaunchLab }: DemoPreviewProps) {
  const [responseData, setResponseData] = useState('');
  const [currentDetection, setCurrentDetection] = useState(0);
  const [showVideo, setShowVideo] = useState(false);

  useEffect(() => {
    const interval = setInterval(() => {
      setCurrentDetection((prev) => (prev + 1) % detections.length);
    }, 3000);

    const responseInterval = setInterval(() => {
      setResponseData((prev) => {
        const nextIndex = aiResponses.findIndex((r) => r === prev) + 1;
        return aiResponses[nextIndex % aiResponses.length];
      });
    }, 2000);

    setShowVideo(true);
    return () => {
      clearInterval(interval);
      clearInterval(responseInterval);
    };
  }, []);

  return (
    <section id="demo-preview" className="relative py-32 overflow-hidden">
      <div className="absolute inset-0 bg-gradient-to-b from-[#0a0a1a] to-[#0d0d20]" />

      <div className="relative container mx-auto px-6">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="text-center mb-16"
        >
          <span className="text-cyan-400 font-semibold text-lg">
            Live Demo
          </span>
          <h2 className="text-4xl md:text-6xl font-bold text-white mt-4 mb-6">
            See{' '}
            <span className="bg-clip-text text-transparent bg-gradient-to-r from-cyan-400 to-blue-400">
              AI in Action
            </span>
          </h2>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          whileInView={{ opacity: 1, scale: 1 }}
          viewport={{ once: true }}
          className="relative max-w-7xl mx-auto"
        >
          <div className="relative min-h-[500px] bg-[#0a0a1a] rounded-3xl overflow-hidden border border-white/10 backdrop-blur-sm shadow-2xl">
            {/* Grid pattern background */}
            <div className="absolute inset-0 opacity-5">
              <svg width="100%" height="100%">
                <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
                  <path d="M 40 0 L 0 0 0 40" fill="none" stroke="white" strokeWidth="0.5" />
                </pattern>
                <rect width="100%" height="100%" fill="url(#grid)" />
              </svg>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 min-h-[500px]">
              {/* Left: Webcam Section */}
              <div className="lg:col-span-2 p-6">
                <div className="relative h-full rounded-2xl overflow-hidden bg-gradient-to-br from-[#0d0d20] to-[#0a0a1a] border border-white/5">
                  {/* Webcam header */}
                  <div className="absolute top-4 left-4 right-4 flex items-center justify-between z-10">
                    <div className="flex items-center gap-2">
                      <div className="w-3 h-3 rounded-full bg-red-500 animate-pulse" />
                      <span className="text-sm text-gray-400">LIVE</span>
                    </div>
                    <div className="flex items-center gap-2 text-gray-400 text-sm">
                      <Video className="w-4 h-4" />
                      <span>Webcam Feed</span>
                    </div>
                  </div>

                  {/* Simulated video feed */}
                  <div className="absolute inset-0 flex items-center justify-center">
                    {showVideo && (
                      <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        className="relative w-full h-full"
                      >
                        {/* Simulated pendulum visualization */}
                        <div className="absolute inset-0 flex items-center justify-center">
                          <motion.div
                            animate={{ rotate: [30, -30, 30] }}
                            transition={{
                              duration: 2,
                              repeat: Infinity,
                              ease: 'easeInOut',
                            }}
                            className="origin-top"
                          >
                            <div className="w-1 h-32 bg-gradient-to-b from-cyan-500 to-blue-500 mx-auto" />
                            <div className="w-10 h-10 rounded-full bg-gradient-to-r from-cyan-400 to-blue-500 shadow-lg shadow-cyan-500/50 mt-1" />
                          </motion.div>
                        </div>

                        {/* Detection boxes */}
                        {detections.map((detection, index) => (
                          <motion.div
                            key={index}
                            initial={{ opacity: 0 }}
                            animate={{
                              opacity: currentDetection === index ? 1 : 0.3,
                              scale: currentDetection === index ? 1.05 : 1,
                            }}
                            className={`absolute border-2 rounded-lg ${
                              currentDetection === index
                                ? 'border-cyan-400'
                                : 'border-gray-500/50'
                            }`}
                            style={{
                              left: `${detection.x}%`,
                              top: `${detection.y}%`,
                              width: `${detection.w}%`,
                              height: `${detection.h}%`,
                            }}
                          >
                            <motion.div
                              animate={{ opacity: [0, 1, 0] }}
                              transition={{ duration: 2, repeat: Infinity }}
                              className="absolute -top-7 left-0 px-2 py-1 bg-cyan-400 text-black text-xs font-bold rounded rounded-bl-none"
                            >
                              {detection.label} | {detection.confidence}%
                            </motion.div>
                          </motion.div>
                        ))}
                      </motion.div>
                    )}
                  </div>

                  {/* Scan lines effect */}
                  <motion.div
                    animate={{ y: [0, 500, 0] }}
                    transition={{ duration: 3, repeat: Infinity, ease: 'linear' }}
                    className="absolute left-0 right-0 h-1 bg-gradient-to-b from-transparent via-cyan-500/10 to-transparent"
                  />
                </div>
              </div>

              {/* Right: Analysis Panel */}
              <div className="p-6 bg-white/5 border-l border-white/10">
                <div className="space-y-6">
                  {/* Detection Info */}
                  <div className="space-y-3">
                    <div className="flex items-center gap-2 text-white font-semibold">
                      <Cpu className="w-5 h-5 text-cyan-400" />
                      <span>Object Detection</span>
                    </div>
                    <motion.div
                      key={currentDetection}
                      initial={{ opacity: 0, x: -10 }}
                      animate={{ opacity: 1, x: 0 }}
                      className="p-3 bg-white/5 rounded-lg border border-white/10"
                    >
                      <div className="flex justify-between items-center mb-2">
                        <span className="text-gray-400">Object:</span>
                        <span className="text-white font-semibold">
                          {detections[currentDetection].label}
                        </span>
                      </div>
                      <div className="flex justify-between items-center mb-2">
                        <span className="text-gray-400">Confidence:</span>
                        <span className="text-cyan-400 font-semibold">
                          {detections[currentDetection].confidence}%
                        </span>
                      </div>
                      <div className="h-2 bg-white/10 rounded-full overflow-hidden">
                        <motion.div
                          initial={{ width: 0 }}
                          animate={{ width: `${detections[currentDetection].confidence}%` }}
                          className="h-full bg-gradient-to-r from-cyan-500 to-blue-500"
                        />
                      </div>
                    </motion.div>
                  </div>

                  {/* Physics Metrics */}
                  <div className="space-y-3">
                    <div className="flex items-center gap-2 text-white font-semibold">
                      <Gauge className="w-5 h-5 text-cyan-400" />
                      <span>Physics Metrics</span>
                    </div>
                    <div className="p-3 bg-white/5 rounded-lg border border-white/10 space-y-2">
                      <div className="flex justify-between">
                        <span className="text-gray-400">Velocity:</span>
                        <motion.span
                          animate={{ opacity: [1, 0.5, 1] }}
                          className="text-white"
                        >
                          2.45 m/s
                        </motion.span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-400">Acceleration:</span>
                        <span className="text-white">-9.8 m/s²</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-400">Period:</span>
                        <span className="text-white">1.2s</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-400">Angle:</span>
                        <span className="text-white">{currentDetection * 15 + 30}°</span>
                      </div>
                    </div>
                  </div>

                  {/* AI Response */}
                  <div className="space-y-3">
                    <div className="flex items-center gap-2 text-white font-semibold">
                      <MessageSquare className="w-5 h-5 text-cyan-400" />
                      <span>AI Analysis</span>
                    </div>
                    <motion.div
                      key={responseData}
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      className="p-3 bg-gradient-to-br from-cyan-500/10 to-blue-500/10 rounded-lg border border-cyan-500/20"
                    >
                      <p className="text-cyan-300 text-sm">{responseData}</p>
                    </motion.div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Floating elements */}
          <div className="absolute -top-4 -left-4 w-20 h-20 bg-gradient-to-r from-cyan-500/20 to-blue-500/20 rounded-full blur-2xl" />
          <div className="absolute -bottom-4 -right-4 w-32 h-32 bg-gradient-to-r from-violet-500/20 to-purple-500/20 rounded-full blur-2xl" />
        </motion.div>

        {/* CTA */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="text-center mt-16"
        >
          <p className="text-gray-400 mb-4">
            Ready to transform your learning experience?
          </p>
          <motion.button
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            onClick={onLaunchLab}
            className="inline-flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-cyan-500 to-blue-600 rounded-xl font-semibold text-white cursor-pointer"
          >
            Try Free for 14 Days
            <ArrowRight className="w-5 h-5" />
          </motion.button>
        </motion.div>
      </div>
    </section>
  );
}
