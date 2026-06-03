import { motion, AnimatePresence } from 'framer-motion';
import { useEffect, useRef, useState, useCallback } from 'react';
import {
  Camera, CameraOff, AlertTriangle, CheckCircle, RefreshCw, Activity, Gauge, MapPin, Circle,
  WifiOff, Loader2, ShieldAlert, Smartphone, Info, X, HelpCircle, ExternalLink
} from 'lucide-react';

/* ─── Types ─────────────────────────────────────── */
type CameraState =
  | 'idle'           // initial
  | 'requesting'     // browser permission dialog
  | 'verifying'      // checking devices
  | 'initializing'   // mounting stream
  | 'active'         // working
  | 'denied'         // user denied permission
  | 'no_camera'      // no device found
  | 'busy'           // camera in use by another app
  | 'https_required' // needs HTTPS
  | 'browser_blocked'// browser policy blocked
  | 'error';         // generic error

interface Detection {
  id: number;
  label: string;
  confidence: number;
  x: number;
  y: number;
  width: number;
  height: number;
  color: string;
}

/* ─── Step Progress Indicator ─────────────────────── */
function StepProgress({ step }: { step: number }) {
  const steps = ['Request', 'Permission', 'Verify', 'Initialize', 'Active'];
  return (
    <div className="flex items-center gap-0 mb-8">
      {steps.map((label, i) => {
        const done = i < step;
        const active = i === step;
        return (
          <div key={label} className="flex items-center flex-1 min-w-0">
            <div className="flex flex-col items-center">
              <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold border transition-all duration-500 ${
                done ? 'bg-cyan-500 border-cyan-500 text-black' :
                active ? 'border-cyan-400 bg-cyan-500/15 text-cyan-400 animate-pulse' :
                'border-white/15 bg-white/5 text-gray-600'
              }`}>
                {done ? <CheckCircle className="w-4 h-4" /> : i + 1}
              </div>
              <span className={`text-[9px] mt-1 font-semibold uppercase tracking-wider whitespace-nowrap ${
                done ? 'text-cyan-400' : active ? 'text-cyan-300' : 'text-gray-600'
              }`}>{label}</span>
            </div>
            {i < steps.length - 1 && (
              <div className={`flex-1 h-px mx-1 transition-all duration-700 ${done ? 'bg-cyan-500' : 'bg-white/10'}`} />
            )}
          </div>
        );
      })}
    </div>
  );
}

/* ─── Troubleshooting Modal ───────────────────────── */
function TroubleshootingModal({ onClose, onRetry, errorType }: {
  onClose: () => void;
  onRetry: () => void;
  errorType: CameraState;
}) {
  const tips: Record<string, { title: string; steps: string[] }> = {
    denied: {
      title: 'Camera Permission Denied',
      steps: [
        'Click the camera/lock icon in your browser address bar',
        'Set Camera permission to "Allow"',
        'Refresh the page and try again',
        'Or go to Browser Settings → Privacy → Camera → Allow for this site',
      ],
    },
    no_camera: {
      title: 'No Camera Detected',
      steps: [
        'Ensure a webcam is physically connected to your device',
        'Check Device Manager (Windows) or System Preferences (Mac)',
        'Try unplugging and reconnecting your camera',
        'Update your camera drivers if needed',
        'Try a different USB port',
      ],
    },
    busy: {
      title: 'Camera Is In Use',
      steps: [
        'Close other apps using your camera (Zoom, Teams, Skype, etc.)',
        'Close other browser tabs that may be using the camera',
        'Restart your browser completely',
        'If on Windows, check Task Manager for camera-using processes',
      ],
    },
    https_required: {
      title: 'HTTPS Required',
      steps: [
        'Camera access requires a secure HTTPS connection',
        'Make sure the URL starts with https://',
        'Contact your server administrator to enable SSL',
        'For local development, use localhost (treated as secure)',
      ],
    },
    browser_blocked: {
      title: 'Browser Blocked Camera',
      steps: [
        'Your browser may have a policy blocking camera access',
        'Try using Chrome, Firefox, or Edge',
        'Disable browser extensions that may block cameras',
        'Check if a VPN or proxy is interfering',
        'Try an Incognito / Private window',
      ],
    },
    error: {
      title: 'Camera Error',
      steps: [
        'Refresh the page and try again',
        'Restart your browser',
        'Check your operating system camera permissions',
        'Ensure no other application is monopolizing the camera',
        'Try restarting your computer',
      ],
    },
  };

  const content = tips[errorType] || tips.error;

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-[200] bg-black/70 backdrop-blur-md flex items-center justify-center p-4"
      onClick={onClose}
    >
      <motion.div
        initial={{ scale: 0.9, y: 20 }}
        animate={{ scale: 1, y: 0 }}
        exit={{ scale: 0.9, y: 20 }}
        onClick={(e) => e.stopPropagation()}
        className="bg-[#0d0d20] border border-white/15 rounded-2xl p-6 max-w-md w-full shadow-2xl"
      >
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-amber-500/15 border border-amber-500/30 flex items-center justify-center">
              <HelpCircle className="w-5 h-5 text-amber-400" />
            </div>
            <h3 className="text-white font-bold">{content.title}</h3>
          </div>
          <button onClick={onClose} className="text-gray-500 hover:text-white transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>

        <p className="text-gray-400 text-sm mb-4">Follow these steps to fix the issue:</p>

        <ol className="space-y-2.5 mb-5">
          {content.steps.map((step, i) => (
            <li key={i} className="flex items-start gap-3">
              <div className="w-5 h-5 rounded-full bg-cyan-500/20 text-cyan-400 text-xs font-bold flex items-center justify-center flex-shrink-0 mt-0.5">
                {i + 1}
              </div>
              <span className="text-gray-300 text-sm leading-relaxed">{step}</span>
            </li>
          ))}
        </ol>

        <div className="flex gap-3">
          <button
            onClick={onClose}
            className="flex-1 py-2.5 bg-white/5 border border-white/10 rounded-xl text-gray-300 text-sm font-medium hover:bg-white/8 transition-all"
          >
            Cancel
          </button>
          <button
            onClick={() => { onClose(); onRetry(); }}
            className="flex-1 py-2.5 bg-gradient-to-r from-cyan-500 to-blue-600 rounded-xl text-white text-sm font-semibold flex items-center justify-center gap-2 shadow-lg shadow-cyan-500/20"
          >
            <RefreshCw className="w-4 h-4" />
            Retry
          </button>
        </div>
      </motion.div>
    </motion.div>
  );
}

/* ─── Camera Request Screen ───────────────────────── */
function CameraRequestScreen({ onRequest, state }: { onRequest: () => void; state: CameraState }) {
  const errorMessages: Partial<Record<CameraState, { icon: any; title: string; desc: string; color: string }>> = {
    denied: {
      icon: ShieldAlert,
      title: 'Camera Access Denied',
      desc: 'Please allow camera access in your browser settings to use the Live Lab.',
      color: 'text-red-400',
    },
    no_camera: {
      icon: CameraOff,
      title: 'No Camera Found',
      desc: 'No camera device was detected. Please connect a webcam and try again.',
      color: 'text-amber-400',
    },
    busy: {
      icon: WifiOff,
      title: 'Camera Is Busy',
      desc: 'Another application is using your camera. Close it and try again.',
      color: 'text-orange-400',
    },
    https_required: {
      icon: ShieldAlert,
      title: 'HTTPS Required',
      desc: 'Camera access requires a secure HTTPS connection.',
      color: 'text-amber-400',
    },
    browser_blocked: {
      icon: ShieldAlert,
      title: 'Browser Blocked Camera',
      desc: 'Your browser policy is blocking camera access. Try a different browser.',
      color: 'text-red-400',
    },
    error: {
      icon: AlertTriangle,
      title: 'Camera Error',
      desc: 'An unexpected error occurred. Please try again.',
      color: 'text-red-400',
    },
  };

  const isError = ['denied', 'no_camera', 'busy', 'https_required', 'browser_blocked', 'error'].includes(state);
  const errInfo = errorMessages[state as keyof typeof errorMessages];
  const ErrIcon = errInfo?.icon;

  const stepIndex =
    state === 'idle' ? 0 :
    state === 'requesting' ? 1 :
    state === 'verifying' ? 2 :
    state === 'initializing' ? 3 : 0;

  return (
    <div className="aspect-video bg-gradient-to-br from-[#07071a] via-[#0a0a1f] to-[#07071a] flex flex-col items-center justify-center p-8 relative overflow-hidden">
      {/* Background grid */}
      <div className="absolute inset-0 opacity-[0.04]" style={{
        backgroundImage: 'linear-gradient(rgba(6,182,212,0.5) 1px, transparent 1px), linear-gradient(90deg, rgba(6,182,212,0.5) 1px, transparent 1px)',
        backgroundSize: '40px 40px',
      }} />

      <div className="relative z-10 w-full max-w-sm">
        {/* Step progress — shown during loading states */}
        {['requesting', 'verifying', 'initializing'].includes(state) && (
          <StepProgress step={stepIndex} />
        )}

        {/* Error state */}
        {isError && errInfo && ErrIcon ? (
          <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} className="text-center">
            <div className={`w-16 h-16 rounded-2xl bg-red-500/10 border border-red-500/20 flex items-center justify-center mx-auto mb-4`}>
              <ErrIcon className={`w-8 h-8 ${errInfo.color}`} />
            </div>
            <h3 className="text-white font-bold text-lg mb-2">{errInfo.title}</h3>
            <p className="text-gray-400 text-sm mb-6 leading-relaxed">{errInfo.desc}</p>
          </motion.div>
        ) : state === 'idle' ? (
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="text-center">
            <motion.div
              animate={{ scale: [1, 1.04, 1] }}
              transition={{ duration: 2, repeat: Infinity }}
              className="w-16 h-16 rounded-2xl bg-cyan-500/15 border border-cyan-500/30 flex items-center justify-center mx-auto mb-4 shadow-lg shadow-cyan-500/10"
            >
              <Camera className="w-8 h-8 text-cyan-400" />
            </motion.div>
            <h3 className="text-white font-bold text-lg mb-2">Enable Camera for Live Lab</h3>
            <p className="text-gray-400 text-sm mb-2 leading-relaxed">
              NeuroLab AI uses your camera to track physics experiments in real time.
            </p>
            <p className="text-xs text-cyan-400/80 mb-6 flex items-center justify-center gap-1">
              <Info className="w-3 h-3" />
              Camera data is processed locally. Never stored or sent.
            </p>
          </motion.div>
        ) : (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="text-center">
            <div className="w-16 h-16 rounded-2xl bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center mx-auto mb-4">
              <Loader2 className="w-8 h-8 text-cyan-400 animate-spin" />
            </div>
            <h3 className="text-white font-bold text-lg mb-2">
              {state === 'requesting' ? 'Requesting Camera Access...' :
               state === 'verifying' ? 'Verifying Camera...' :
               'Initializing Live Lab...'}
            </h3>
            <p className="text-gray-400 text-sm">
              {state === 'requesting' ? 'Please allow camera access in the browser dialog' :
               state === 'verifying' ? 'Checking available camera devices...' :
               'Starting AI analysis...'}
            </p>
          </motion.div>
        )}

        {/* Action Button */}
        {(state === 'idle' || isError) && (
          <motion.button
            whileHover={{ scale: 1.02, boxShadow: '0 0 30px rgba(6,182,212,0.3)' }}
            whileTap={{ scale: 0.98 }}
            onClick={onRequest}
            className="w-full py-3.5 bg-gradient-to-r from-cyan-500 to-blue-600 rounded-xl text-white font-semibold flex items-center justify-center gap-2 shadow-lg shadow-cyan-500/20"
          >
            <Camera className="w-4 h-4" />
            {isError ? 'Try Again' : 'Enable Camera'}
          </motion.button>
        )}

        {/* Privacy note */}
        <div className="mt-4 flex items-center justify-center gap-4 text-xs text-gray-600">
          <span className="flex items-center gap-1"><span>🔒</span> Local only</span>
          <span className="flex items-center gap-1"><span>🛡️</span> Never stored</span>
          <span className="flex items-center gap-1"><span>✅</span> GDPR safe</span>
        </div>
      </div>
    </div>
  );
}

/* ─── Main WebcamPanel ─────────────────────────────── */
export default function WebcamPanel() {
  const [cameraState, setCameraState] = useState<CameraState>('idle');
  const [detections, setDetections] = useState<Detection[]>([]);
  const [showTroubleshooting, setShowTroubleshooting] = useState(false);
  const [physicsData, setPhysicsData] = useState({
    velocity: 2.45,
    acceleration: -9.8,
    position: { x: 0, y: 0 },
    angle: 45,
  });

  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const overlayCanvasRef = useRef<HTMLCanvasElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const animationRef = useRef<number>();
  const detectionIntervalRef = useRef<ReturnType<typeof setInterval>>();

  /* ── Request camera access ── */
  const requestCamera = useCallback(async () => {
    // Check HTTPS first (except localhost)
    if (location.protocol !== 'https:' && location.hostname !== 'localhost' && location.hostname !== '127.0.0.1') {
      setCameraState('https_required');
      setShowTroubleshooting(true);
      return;
    }

    setCameraState('requesting');

    try {
      // Step 1: Request permission
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 1280 }, height: { ideal: 720 }, facingMode: 'user' },
        audio: false,
      });

      // Step 2: Verify camera
      setCameraState('verifying');
      await new Promise((r) => setTimeout(r, 600));

      const devices = await navigator.mediaDevices.enumerateDevices();
      const videoDevices = devices.filter((d) => d.kind === 'videoinput');
      if (videoDevices.length === 0) {
        stream.getTracks().forEach((t) => t.stop());
        setCameraState('no_camera');
        setShowTroubleshooting(true);
        return;
      }

      // Step 3: Initialize
      setCameraState('initializing');
      await new Promise((r) => setTimeout(r, 400));

      streamRef.current = stream;

      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }

      // Step 4: Active!
      setCameraState('active');

    } catch (err: any) {
      console.error('Camera error:', err.name, err.message);

      if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
        setCameraState('denied');
      } else if (err.name === 'NotFoundError' || err.name === 'DevicesNotFoundError') {
        setCameraState('no_camera');
      } else if (err.name === 'NotReadableError' || err.name === 'TrackStartError') {
        setCameraState('busy');
      } else if (err.name === 'OverconstrainedError') {
        setCameraState('error');
      } else {
        setCameraState('error');
      }
      setShowTroubleshooting(true);
    }
  }, []);

  /* ── Cleanup on unmount ── */
  useEffect(() => {
    return () => {
      streamRef.current?.getTracks().forEach((t) => t.stop());
      if (animationRef.current) cancelAnimationFrame(animationRef.current);
      if (detectionIntervalRef.current) clearInterval(detectionIntervalRef.current);
    };
  }, []);

  /* ── Start AI detection loop when active ── */
  useEffect(() => {
    if (cameraState !== 'active') return;

    // Simulated AI detections overlaying real camera
    detectionIntervalRef.current = setInterval(() => {
      setDetections([
        { id: 1, label: 'Object A', confidence: 94 + Math.random() * 5, x: 15 + Math.random() * 5, y: 20 + Math.random() * 5, width: 30, height: 40, color: '#06b6d4' },
        { id: 2, label: 'Object B', confidence: 88 + Math.random() * 8, x: 55 + Math.random() * 5, y: 35 + Math.random() * 5, width: 25, height: 30, color: '#8b5cf6' },
        { id: 3, label: 'Motion', confidence: 82 + Math.random() * 10, x: 35 + Math.random() * 3, y: 10 + Math.random() * 3, width: 40, height: 70, color: '#10b981' },
      ]);

      setPhysicsData((prev) => ({
        velocity: Math.abs(prev.velocity + (Math.random() - 0.5) * 0.2),
        acceleration: -9.8 + (Math.random() - 0.5) * 0.3,
        position: {
          x: prev.position.x + (Math.random() - 0.5) * 2,
          y: prev.position.y + (Math.random() - 0.5) * 2,
        },
        angle: prev.angle + (Math.random() - 0.5) * 5,
      }));
    }, 500);

    return () => { if (detectionIntervalRef.current) clearInterval(detectionIntervalRef.current); };
  }, [cameraState]);

  /* ── Draw overlay canvas on top of video ── */
  useEffect(() => {
    const canvas = overlayCanvasRef.current;
    if (!canvas || cameraState !== 'active') return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const draw = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      // Scan line effect
      const time = Date.now() / 1000;
      const scanY = ((time * 0.3) % 1) * canvas.height;
      const scanGrad = ctx.createLinearGradient(0, scanY - 20, 0, scanY + 20);
      scanGrad.addColorStop(0, 'transparent');
      scanGrad.addColorStop(0.5, 'rgba(6,182,212,0.08)');
      scanGrad.addColorStop(1, 'transparent');
      ctx.fillStyle = scanGrad;
      ctx.fillRect(0, scanY - 20, canvas.width, 40);

      // Corner brackets
      const bSize = 24;
      const bWidth = 2;
      ctx.strokeStyle = 'rgba(6,182,212,0.5)';
      ctx.lineWidth = bWidth;
      const corners = [[12, 12], [canvas.width - 12, 12], [12, canvas.height - 12], [canvas.width - 12, canvas.height - 12]];
      corners.forEach(([cx, cy], i) => {
        ctx.beginPath();
        const dx = i % 2 === 0 ? 1 : -1;
        const dy = i < 2 ? 1 : -1;
        ctx.moveTo(cx, cy + dy * bSize);
        ctx.lineTo(cx, cy);
        ctx.lineTo(cx + dx * bSize, cy);
        ctx.stroke();
      });

      animationRef.current = requestAnimationFrame(draw);
    };

    draw();
    return () => { if (animationRef.current) cancelAnimationFrame(animationRef.current); };
  }, [cameraState]);

  const isActive = cameraState === 'active';
  const isLoading = ['requesting', 'verifying', 'initializing'].includes(cameraState);
  const isError = ['denied', 'no_camera', 'busy', 'https_required', 'browser_blocked', 'error'].includes(cameraState);

  return (
    <>
      <AnimatePresence>
        {showTroubleshooting && (
          <TroubleshootingModal
            errorType={cameraState}
            onClose={() => setShowTroubleshooting(false)}
            onRetry={() => { setShowTroubleshooting(false); requestCamera(); }}
          />
        )}
      </AnimatePresence>

      <div className="relative">
        {/* Camera feed / request screen */}
        <AnimatePresence mode="wait">
          {!isActive ? (
            <motion.div key="request" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
              <CameraRequestScreen onRequest={requestCamera} state={cameraState} />
            </motion.div>
          ) : (
            <motion.div key="active" initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="relative aspect-video bg-black overflow-hidden">
              {/* Real camera feed */}
              <video
                ref={videoRef}
                autoPlay
                playsInline
                muted
                className="absolute inset-0 w-full h-full object-cover"
                style={{ transform: 'scaleX(-1)' }} // mirror for selfie view
              />

              {/* Overlay canvas */}
              <canvas
                ref={overlayCanvasRef}
                width={640}
                height={360}
                className="absolute inset-0 w-full h-full pointer-events-none"
              />

              {/* AI Detection boxes */}
              {detections.map((d) => (
                <motion.div
                  key={d.id}
                  initial={{ opacity: 0, scale: 0.9 }}
                  animate={{ opacity: 1, scale: 1 }}
                  className="absolute border-2 rounded-lg pointer-events-none"
                  style={{
                    borderColor: d.color,
                    left: `${d.x}%`,
                    top: `${d.y}%`,
                    width: `${d.width}%`,
                    height: `${d.height}%`,
                    boxShadow: `0 0 16px ${d.color}40`,
                  }}
                >
                  <div className="absolute -top-7 left-0 px-2 py-0.5 text-[10px] font-bold rounded" style={{ backgroundColor: d.color, color: '#000' }}>
                    {d.label} {d.confidence.toFixed(1)}%
                  </div>
                  {/* Corner markers */}
                  {[['top-0 left-0 border-t-2 border-l-2 rounded-tl'], ['top-0 right-0 border-t-2 border-r-2 rounded-tr'], ['bottom-0 left-0 border-b-2 border-l-2 rounded-bl'], ['bottom-0 right-0 border-b-2 border-r-2 rounded-br']].map(([cls], i) => (
                    <div key={i} className={`absolute w-3 h-3 ${cls}`} style={{ borderColor: d.color }} />
                  ))}
                </motion.div>
              ))}

              {/* Status bar */}
              <div className="absolute top-3 left-1/2 -translate-x-1/2 flex items-center gap-2 px-3 py-1.5 bg-black/60 backdrop-blur-sm rounded-full border border-white/10">
                <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                <span className="text-xs text-gray-300 font-medium">AI Live Analysis</span>
              </div>

              {/* Live badge */}
              <div className="absolute top-3 right-3 flex items-center gap-1.5 px-2.5 py-1 bg-red-500/20 rounded-full border border-red-500/30 backdrop-blur-sm">
                <div className="w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse" />
                <span className="text-[10px] text-red-400 font-bold uppercase">LIVE</span>
              </div>

              {/* Privacy indicator */}
              <div className="absolute bottom-3 left-3 flex items-center gap-1.5 px-2.5 py-1 bg-black/60 backdrop-blur-sm rounded-full border border-white/10">
                <span className="text-[10px] text-gray-400">🔒 Local only • Not recorded</span>
              </div>

              {/* Stop camera button */}
              <button
                onClick={() => {
                  streamRef.current?.getTracks().forEach((t) => t.stop());
                  streamRef.current = null;
                  setDetections([]);
                  setCameraState('idle');
                }}
                className="absolute bottom-3 right-3 px-3 py-1.5 bg-red-500/20 border border-red-500/30 text-red-400 text-xs font-bold rounded-full backdrop-blur-sm hover:bg-red-500/30 transition-all flex items-center gap-1.5"
              >
                <CameraOff className="w-3 h-3" />
                Stop
              </button>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Stats bar */}
        <div className="grid grid-cols-4 divide-x divide-white/10 border-t border-white/10 bg-white/5 backdrop-blur-sm">
          {[
            { icon: Activity, color: 'text-cyan-400', label: 'Velocity', value: `${Math.abs(physicsData.velocity).toFixed(2)} m/s` },
            { icon: Gauge, color: 'text-violet-400', label: 'Acceleration', value: `${physicsData.acceleration.toFixed(2)} m/s²` },
            { icon: MapPin, color: 'text-emerald-400', label: 'Position', value: `(${physicsData.position.x.toFixed(0)}, ${physicsData.position.y.toFixed(0)})` },
            { icon: Circle, color: 'text-orange-400', label: 'Angle', value: `${physicsData.angle.toFixed(1)}°` },
          ].map(({ icon: Icon, color, label, value }) => (
            <div key={label} className="p-3 text-center hover:bg-white/5 transition-colors cursor-pointer">
              <div className="flex items-center justify-center gap-1.5 mb-1">
                <Icon className={`w-3.5 h-3.5 ${color}`} />
                <span className="text-xs text-gray-400">{label}</span>
              </div>
              <div className={`text-base font-semibold text-white ${!isActive ? 'opacity-30' : ''}`}>{value}</div>
            </div>
          ))}
        </div>

        {/* Error helper link */}
        {isError && (
          <div className="border-t border-white/10 bg-amber-500/5 px-4 py-2.5 flex items-center justify-between">
            <span className="text-xs text-amber-400">Camera access blocked or unavailable</span>
            <button
              onClick={() => setShowTroubleshooting(true)}
              className="text-xs text-cyan-400 hover:text-cyan-300 transition-colors flex items-center gap-1 font-medium"
            >
              <HelpCircle className="w-3.5 h-3.5" />
              Troubleshoot
            </button>
          </div>
        )}
      </div>
    </>
  );
}
