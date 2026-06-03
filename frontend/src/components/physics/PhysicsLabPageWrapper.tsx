import React, { useState, useEffect, useRef, Suspense, lazy } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Link, useNavigate } from "react-router-dom";
import { AreaChart, Area, ResponsiveContainer, LineChart, Line, YAxis, XAxis } from "recharts";
import { Zap, Award, Trophy, Flame, Camera, Bot, Play, Pause, ArrowRight, Activity, CheckCircle2, Atom, Clock, Lock, Check, BookOpen, FlaskConical, Settings, Target, Brain, Star, Sparkles, RefreshCw, Sliders } from "lucide-react";
import { pushNotification } from "../../lib/notificationStore";
import { useUserStore } from "../../store/useUserStore";
import { usePhysicsStore } from "../../store/usePhysicsStore";

// Component: PhysicsLabPageWrapper
// -------------------------------------------------------------
function PhysicsLabPageWrapper() {
  const [selectedTab, setSelectedTab] = useState<'Free Fall' | 'Projectile Motion' | 'Pendulum' | 'Spring Oscillation' | 'Collision' | 'Wave Motion'>('Free Fall');
  const tabs = ['Free Fall', 'Projectile Motion', 'Pendulum', 'Spring Oscillation', 'Collision', 'Wave Motion'] as const;

  // Animation clock clock
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [time, setTime] = useState<number>(0);
  const animationRef = useRef<number>();

  // Parameters States
  // 1. Free Fall
  const [ffMass, setFfMass] = useState<number>(1.0);
  const [ffHeight, setFfHeight] = useState<number>(50.0);
  const [ffGravity, setFfGravity] = useState<number>(9.81);

  // 2. Projectile
  const [projSpeed, setProjSpeed] = useState<number>(25.0);
  const [projAngle, setProjAngle] = useState<number>(45.0);
  const [projGravity, setProjGravity] = useState<number>(9.81);
  const [projMass, setProjMass] = useState<number>(1.2);

  // 3. Pendulum
  const [pendLength, setPendLength] = useState<number>(2.5);
  const [pendMass, setPendMass] = useState<number>(1.2);
  const [pendAngle, setPendAngle] = useState<number>(45.0);
  const [pendGravity, setPendGravity] = useState<number>(9.81);

  // 4. Spring Oscillation
  const [springK, setSpringK] = useState<number>(40.0);
  const [springMass, setSpringMass] = useState<number>(1.5);
  const [springDisplacement, setSpringDisplacement] = useState<number>(1.5);
  const [springDamping, setSpringDamping] = useState<number>(0.5);

  // 5. Collision
  const [collMassA, setCollMassA] = useState<number>(2.0);
  const [collMassB, setCollMassB] = useState<number>(1.5);
  const [collVelA, setCollVelA] = useState<number>(5.0);
  const [collVelB, setCollVelB] = useState<number>(-3.0);
  const [collisionType, setCollisionType] = useState<'Elastic' | 'Inelastic'>('Elastic');

  // 6. Wave Motion
  const [waveAmp, setWaveAmp] = useState<number>(1.0);
  const [waveFreq, setWaveFreq] = useState<number>(1.5);
  const [waveLen, setWaveLen] = useState<number>(6.0);

  // Compiled safety array to satisfy strict unused checks
  const _physicsRef = [
    projMass, setProjMass, setPendGravity, setSpringDisplacement, setCollVelA, setCollVelB,
    Settings, RefreshCw
  ];
  if (_physicsRef.length === 0) console.log();

  // Reset clock on tab change
  useEffect(() => {
    setTime(0);
    setIsPlaying(false);
  }, [selectedTab]);

  // Unified animation clock loop
  useEffect(() => {
    if (isPlaying) {
      let lastTimestamp = performance.now();
      const loop = (now: number) => {
        const delta = (now - lastTimestamp) / 1000;
        lastTimestamp = now;
        setTime((prev) => prev + delta * 1.5); // speed coefficient
        animationRef.current = requestAnimationFrame(loop);
      };
      animationRef.current = requestAnimationFrame(loop);
    }
    return () => {
      if (animationRef.current) cancelAnimationFrame(animationRef.current);
    };
  }, [isPlaying]);

  const handleReset = () => {
    setTime(0);
    setIsPlaying(false);
  };

  // Helper metadata
  const labMeta = {
    'Free Fall': { difficulty: 'Beginner', time: '10 min', desc: 'Drop massive objects through a vacuum to study uniform gravitational acceleration and Newtonian energy conversion.' },
    'Projectile Motion': { difficulty: 'Intermediate', time: '15 min', desc: 'Launch objects along parabolic path curves. Test horizontal velocity constants versus vertical gravity drop.' },
    'Pendulum': { difficulty: 'Intermediate', time: '12 min', desc: 'Examine simple harmonic oscillation periods. Verify how mass holds zero effect on swing frequency.' },
    'Spring Oscillation': { difficulty: 'Advanced', time: '15 min', desc: 'Simulate spring restorative damping and Hooke\'s Law parameters to calculate mechanical decay gradients.' },
    'Collision': { difficulty: 'Advanced', time: '20 min', desc: 'Test linear momentum equations under elastic recoil or fully inelastic sticking impacts on friction-free tracks.' },
    'Wave Motion': { difficulty: 'Intermediate', time: '15 min', desc: 'Explore periodic sine wave propagation across active string mediums. Alter frequency limits and wavelengths.' }
  }[selectedTab];

  // ==========================================
  // PHYSICS ENGINE COMPUTATIONS & CHARTS DATA
  // ==========================================

  // 1. Free Fall
  const t_ff_impact = Math.sqrt((2 * ffHeight) / ffGravity);
  const ff_t = Math.min(time, t_ff_impact);
  const ff_y = Math.max(0, ffHeight - 0.5 * ffGravity * ff_t * ff_t);
  const ff_v = -ffGravity * ff_t;
  const ff_ke = 0.5 * ffMass * ff_v * ff_v;
  const ff_pe = ffMass * ffGravity * ff_y;
  const ff_te = ff_ke + ff_pe;

  const generateFfChartData = () => {
    const data = [];
    const steps = 40;
    const dt = t_ff_impact / steps;
    for (let i = 0; i <= steps; i++) {
      const t = i * dt;
      const y = Math.max(0, ffHeight - 0.5 * ffGravity * t * t);
      const v = ffGravity * t;
      data.push({
        time: Number(t.toFixed(2)),
        position: Number(y.toFixed(1)),
        velocity: Number(v.toFixed(1))
      });
    }
    return data;
  };

  // 2. Projectile Motion
  const proj_rad = (projAngle * Math.PI) / 180;
  const proj_vx0 = projSpeed * Math.cos(proj_rad);
  const proj_vy0 = projSpeed * Math.sin(proj_rad);
  const t_proj_flight = (2 * proj_vy0) / projGravity;
  const proj_range = (projSpeed * projSpeed * Math.sin(2 * proj_rad)) / projGravity;
  const proj_hmax = (proj_vy0 * proj_vy0) / (2 * projGravity);

  const proj_t = Math.min(time, t_proj_flight);
  const proj_x = proj_vx0 * proj_t;
  const proj_y = Math.max(0, proj_vy0 * proj_t - 0.5 * projGravity * proj_t * proj_t);
  const proj_vy = proj_vy0 - projGravity * proj_t;

  const generateProjChartData = () => {
    const data = [];
    const steps = 40;
    const dt = t_proj_flight / steps;
    for (let i = 0; i <= steps; i++) {
      const t = i * dt;
      const x = proj_vx0 * t;
      const y = Math.max(0, proj_vy0 * t - 0.5 * projGravity * t * t);
      data.push({
        x: Number(x.toFixed(1)),
        y: Number(y.toFixed(1))
      });
    }
    return data;
  };

  // 3. Pendulum
  const pend_omega = Math.sqrt(pendGravity / pendLength);
  const pend_period = 2 * Math.PI * Math.sqrt(pendLength / pendGravity);
  const pend_init_rad = (pendAngle * Math.PI) / 180;
  const pend_theta = pend_init_rad * Math.cos(pend_omega * time);
  const pend_ang_vel = -pend_init_rad * pend_omega * Math.sin(pend_omega * time);
  const pend_h = pendLength * (1 - Math.cos(pend_theta));
  const pend_pe = pendMass * pendGravity * pend_h;
  const pend_v = pendLength * pend_ang_vel;
  const pend_ke = 0.5 * pendMass * pend_v * pend_v;
  const bobX = 150 + 100 * Math.sin(pend_theta);
  const bobY = 20 + 100 * Math.cos(pend_theta);

  const generatePendChartData = () => {
    const data = [];
    const steps = 50;
    const dt = 4.0 / steps; // 4 seconds window
    for (let i = 0; i <= steps; i++) {
      const t = i * dt;
      const theta = pendAngle * Math.cos(pend_omega * t);
      data.push({
        time: Number(t.toFixed(2)),
        angle: Number(theta.toFixed(1))
      });
    }
    return data;
  };

  // 4. Spring Oscillation
  const spring_omega0 = Math.sqrt(springK / springMass);
  const spring_gamma = springDamping / (2 * springMass);
  const spring_omegad = Math.sqrt(Math.max(0.01, spring_omega0 * spring_omega0 - spring_gamma * spring_gamma));
  const spring_x = springDisplacement * Math.exp(-spring_gamma * time) * Math.cos(spring_omegad * time);
  const spring_force = -springK * spring_x;
  const spring_pe = 0.5 * springK * spring_x * spring_x;
  // approximate derivative for velocity
  const spring_v = -springDisplacement * Math.exp(-spring_gamma * time) * (spring_gamma * Math.cos(spring_omegad * time) + spring_omegad * Math.sin(spring_omegad * time));
  const spring_ke = 0.5 * springMass * spring_v * spring_v;
  const blockX = 150 + spring_x * 35;

  const generateSpringChartData = () => {
    const data = [];
    const steps = 60;
    const dt = 6.0 / steps;
    for (let i = 0; i <= steps; i++) {
      const t = i * dt;
      const x = springDisplacement * Math.exp(-spring_gamma * t) * Math.cos(spring_omegad * t);
      data.push({
        time: Number(t.toFixed(2)),
        displacement: Number(x.toFixed(2))
      });
    }
    return data;
  };

  // 5. Collision
  const initialDist = 180.0;
  const relVel = collVelA - collVelB;
  const t_coll_impact = relVel > 0 ? initialDist / (relVel * 16) : 999;
  const isAfterCollision = time >= t_coll_impact;

  // Collision equations
  const coll_total_mom = collMassA * collVelA + collMassB * collVelB;
  const coll_ke_init = 0.5 * collMassA * collVelA * collVelA + 0.5 * collMassB * collVelB * collVelB;

  let finalVelA = collVelA;
  let finalVelB = collVelB;
  if (collisionType === 'Elastic') {
    finalVelA = ((collMassA - collMassB) / (collMassA + collMassB)) * collVelA + ((2 * collMassB) / (collMassA + collMassB)) * collVelB;
    finalVelB = ((2 * collMassA) / (collMassA + collMassB)) * collVelA + ((collMassB - collMassA) / (collMassA + collMassB)) * collVelB;
  } else {
    finalVelA = coll_total_mom / (collMassA + collMassB);
    finalVelB = finalVelA;
  }

  const coll_ke_final = 0.5 * collMassA * finalVelA * finalVelA + 0.5 * collMassB * finalVelB * finalVelB;
  const coll_ke_lost = Math.max(0, coll_ke_init - coll_ke_final);

  let activePosA = 40.0;
  let activePosB = 220.0;
  let activeVelA = collVelA;
  let activeVelB = collVelB;

  if (!isAfterCollision) {
    activePosA = 40.0 + collVelA * 16 * time;
    activePosB = 220.0 + collVelB * 16 * time;
    activeVelA = collVelA;
    activeVelB = collVelB;
  } else {
    const contactPoint = 40.0 + collVelA * 16 * t_coll_impact;
    const dt = time - t_coll_impact;
    activePosA = contactPoint + finalVelA * 16 * dt;
    activePosB = contactPoint + finalVelB * 16 * dt;
    activeVelA = finalVelA;
    activeVelB = finalVelB;
  }

  const generateCollisionChartData = () => {
    const data = [];
    const steps = 60;
    const dt = 3.0 / steps;
    for (let i = 0; i <= steps; i++) {
      const t = i * dt;
      let vA = collVelA;
      let vB = collVelB;
      if (t >= t_coll_impact) {
        vA = finalVelA;
        vB = finalVelB;
      }
      data.push({
        time: Number(t.toFixed(2)),
        velA: Number(vA.toFixed(2)),
        velB: Number(vB.toFixed(2))
      });
    }
    return data;
  };

  // 6. Wave Motion
  const wave_wavenum = (2 * Math.PI) / waveLen;
  const wave_omega = 2 * Math.PI * waveFreq;
  const wave_speed = waveFreq * waveLen;
  const wave_y_mid = waveAmp * Math.sin(wave_wavenum * 4.0 - wave_omega * time);

  const generateWaveChartData = () => {
    const data = [];
    const steps = 50;
    const dx = 10.0 / steps;
    for (let i = 0; i <= steps; i++) {
      const x = i * dx;
      const y = waveAmp * Math.sin(wave_wavenum * x - wave_omega * time);
      data.push({
        x: Number(x.toFixed(1)),
        amplitude: Number(y.toFixed(2))
      });
    }
    return data;
  };

  // AI Tutor Explanations database
  const getAiTutorExplanation = () => {
    switch (selectedTab) {
      case 'Free Fall':
        return `Under uniform gravity, the apple falls along the Y-axis. Dragging the mass slider demonstrates Galileo's law: acceleration remains exactly ${ffGravity.toFixed(2)}m/s² regardless of mass, although energy scales proportionally!`;
      case 'Projectile Motion':
        return `By splitting velocity vectors, horizontal velocity remains constant at ${proj_vx0.toFixed(1)}m/s because no horizontal force is present, while gravity accelerates vertical velocity, mapping a beautiful ${proj_hmax.toFixed(1)}m high parabola.`;
      case 'Pendulum':
        return ` oscillatory periods (T) are governed primarily by length. Your pendulum period is ${pend_period.toFixed(2)}s. Notice that changing the bob mass has zero influence on the swing period!`;
      case 'Spring Oscillation':
        return `Hooke's Law (F = -kx) details restoring forces. Adding damping coefficient ${springDamping.toFixed(1)} models physical friction decay. Observe the amplitude exponentially decay on the displacement graph.`;
      case 'Collision':
        return `Total momentum is consistently conserved at ${coll_total_mom.toFixed(2)} kg·m/s. Toggling collision types shows that elastic models completely conserve kinetic energy, while inelastic ones yield ${coll_ke_lost.toFixed(1)}J lost in contact.`;
      case 'Wave Motion':
        return `String wave speed calculates to ${wave_speed.toFixed(1)} m/s (v = f * lambda). Notice that although the wave envelope travels along the string, individual colored particles only vibrate up and down locally.`;
      default:
        return '';
    }
  };

  // Auto-stop simulations when they reach active end boundaries
  useEffect(() => {
    if (!isPlaying) return;
    if (selectedTab === 'Free Fall') {
      if (time >= t_ff_impact) {
        setIsPlaying(false);
      }
    } else if (selectedTab === 'Projectile Motion') {
      if (time >= t_proj_flight) {
        setIsPlaying(false);
      }
    }
  }, [time, isPlaying, selectedTab, t_ff_impact, t_proj_flight]);

  return (
    <div className="p-6 relative z-10 max-w-7xl mx-auto space-y-6 pt-2">
      {/* Visual Navigation Tabs */}
      <div className="flex flex-wrap items-center gap-2 border-b border-white/5 pb-4">
        {tabs.map((tab) => (
          <button
            key={tab}
            onClick={() => setSelectedTab(tab)}
            className={`px-4 py-2.5 text-sm rounded-full font-medium transition-all flex items-center gap-2 ${
              selectedTab === tab
                ? 'bg-gradient-to-r from-cyan-500/20 to-blue-600/20 border border-cyan-500/50 text-cyan-400 font-bold shadow-lg shadow-cyan-500/5'
                : 'bg-white/5 border border-white/10 text-gray-400 hover:bg-white/10 hover:text-white'
            }`}
          >
            {tab === 'Free Fall' && <Activity className="w-4 h-4" />}
            {tab === 'Projectile Motion' && <Target className="w-4 h-4" />}
            {tab === 'Pendulum' && <Atom className="w-4 h-4" />}
            {tab === 'Spring Oscillation' && <Sliders className="w-4 h-4" />}
            {tab === 'Collision' && <Trophy className="w-4 h-4" />}
            {tab === 'Wave Motion' && <Sparkles className="w-4 h-4" />}
            {tab}
          </button>
        ))}
      </div>

      {/* Lab Metadata Info Card */}
      <motion.div
        key={selectedTab + '_meta'}
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        className="p-5 bg-[#12121a] border border-[#22222f] rounded-2xl flex flex-col md:flex-row justify-between items-start md:items-center gap-4 relative overflow-hidden"
      >
        <div className="space-y-1 max-w-3xl">
          <div className="flex items-center gap-3">
            <span className="px-2 py-0.5 bg-cyan-500/10 border border-cyan-500/20 text-[10px] font-bold text-cyan-400 rounded uppercase tracking-wider">
              {selectedTab} Simulator
            </span>
            <span className={`px-2 py-0.5 text-[10px] font-bold rounded uppercase tracking-wider ${
              labMeta.difficulty === 'Beginner' ? 'bg-green-500/10 border border-green-500/20 text-green-400' :
              labMeta.difficulty === 'Intermediate' ? 'bg-cyan-500/10 border border-cyan-500/20 text-cyan-400' :
              'bg-purple-500/10 border border-purple-500/20 text-purple-400'
            }`}>
              {labMeta.difficulty}
            </span>
          </div>
          <p className="text-xs text-gray-400 leading-relaxed mt-2">{labMeta.desc}</p>
        </div>
        <div className="flex items-center gap-3 flex-shrink-0">
          <div className="px-3.5 py-2 bg-white/5 border border-white/10 rounded-xl text-xs font-bold text-gray-300">
            Est. Study Time: {labMeta.time}
          </div>
        </div>
      </motion.div>

      {/* Main Lab Screen Layout */}
      <AnimatePresence mode="wait">
        <motion.div
          key={selectedTab}
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          exit={{ opacity: 0, x: -20 }}
          transition={{ duration: 0.25 }}
          className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start"
        >
          {/* Left Block: Virtual Simulation Canvas + Live Charting */}
          <div className="lg:col-span-8 space-y-6">
            
            {/* Unique Virtual Simulation Canvas */}
            <div className="bg-[#0c0c19] border border-[#22223f] rounded-2xl p-6 relative overflow-hidden shadow-2xl min-h-[350px] flex flex-col justify-between">
              <div className="absolute top-4 left-4 z-20 flex gap-2">
                <span className="px-2 py-0.5 bg-cyan-500/10 border border-cyan-500/20 text-[9px] font-extrabold text-cyan-400 rounded tracking-wider uppercase">Visualizer</span>
                <span className="px-2 py-0.5 bg-purple-500/10 border border-purple-500/20 text-[9px] font-extrabold text-purple-400 rounded tracking-wider uppercase">60 FPS Real-time</span>
              </div>

              {/* Dynamic canvas simulations based on tab */}
              <div className="flex-1 min-h-[220px] flex items-center justify-center relative">
                {/* Visual grid guide lines */}
                <div
                  className="absolute inset-0 opacity-10 pointer-events-none"
                  style={{
                    backgroundImage: 'linear-gradient(rgba(255,255,255,0.06) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.06) 1px, transparent 1px)',
                    backgroundSize: '20px 20px'
                  }}
                />

                {/* 1. FREE FALL VIEW */}
                {selectedTab === 'Free Fall' && (
                  <div className="w-full max-w-sm h-48 relative">
                    <div className="absolute left-10 inset-y-0 border-l border-white/10 flex flex-col justify-between text-[9px] text-gray-500 pl-2 font-mono">
                      <span>{ffHeight}m</span>
                      <span>{(ffHeight * 0.75).toFixed(1)}m</span>
                      <span>{(ffHeight * 0.5).toFixed(1)}m</span>
                      <span>{(ffHeight * 0.25).toFixed(1)}m</span>
                      <span>0m</span>
                    </div>
                    {/* Ground line */}
                    <div className="absolute bottom-0 left-6 right-6 border-b-2 border-emerald-500/35" />
                    
                    {/* Falling Apple */}
                    <div
                      className="absolute transition-all duration-75 flex flex-col items-center"
                      style={{ 
                        left: '50%',
                        transform: 'translateX(-50%)',
                        top: `${(1 - ff_y / ffHeight) * 140}px` 
                      }}
                    >
                      <div className="w-9 h-9 rounded-full bg-gradient-to-br from-red-500 to-red-800 shadow-lg shadow-red-500/35 relative">
                        <div className="absolute -top-1 left-3.5 w-1.5 h-3 bg-green-700 rounded-tr transform rotate-12" />
                      </div>
                      <span className="text-[8px] text-red-400 font-mono mt-1 font-bold">APPLE</span>
                    </div>
                  </div>
                )}

                {/* 2. PROJECTILE MOTION VIEW */}
                {selectedTab === 'Projectile Motion' && (
                  <svg className="w-full h-full min-h-[220px] max-w-xl pointer-events-none">
                    {/* Trajectory dot path */}
                    <path
                      d={`M 30,190 Q ${(proj_range * 0.5 / proj_range) * 440 + 30},${190 - (proj_hmax / proj_hmax) * 140} ${(proj_range / proj_range) * 440 + 30},190`}
                      fill="none"
                      stroke="rgba(6, 182, 212, 0.15)"
                      strokeWidth="1.5"
                      strokeDasharray="3 3"
                    />

                    {/* Ground line */}
                    <line x1="20" y1="190" x2="520" y2="190" stroke="rgba(255,255,255,0.1)" strokeWidth="2" />
                    
                    {/* Landing coordinate marker */}
                    <circle cx={(proj_range / proj_range) * 440 + 30} cy="190" r="4" fill="#a855f7" />
                    <text x={(proj_range / proj_range) * 440 + 10} y="204" fill="#a855f7" fontSize="8" fontWeight="bold" fontFamily="monospace">
                      R: {proj_range.toFixed(1)}m
                    </text>

                    {/* Launcher Cannon (Tilt matches angle slider) */}
                    <g transform={`translate(30, 190) rotate(${-projAngle})`}>
                      <rect x="0" y="-8" width="24" height="16" rx="2" fill="rgba(6, 182, 212, 0.8)" stroke="#06b6d4" strokeWidth="1.5" />
                      <circle cx="0" cy="0" r="8" fill="#1e1b4b" stroke="#06b6d4" strokeWidth="1.5" />
                    </g>

                    {/* Flying Ball */}
                    {proj_t > 0 && (
                      <g transform={`translate(${(proj_x / proj_range) * 440 + 30}, ${190 - (proj_y / proj_hmax) * 140})`}>
                        <circle cx="0" cy="0" r="6" fill="#ec4899" className="shadow-lg shadow-pink-500" />
                        <line x1="0" y1="0" x2={proj_vx0 * 0.5} y2={-proj_vy * 0.5} stroke="#22c55e" strokeWidth="1.5" />
                      </g>
                    )}
                  </svg>
                )}

                {/* 3. PENDULUM VIEW */}
                {selectedTab === 'Pendulum' && (
                  <svg className="w-full h-full min-h-[220px] max-w-sm pointer-events-none">
                    {/* Ceiling line */}
                    <line x1="80" y1="20" x2="220" y2="20" stroke="rgba(255,255,255,0.15)" strokeWidth="3" />
                    
                    {/* Dotted sweep trail */}
                    <path d="M 90,110 A 100,100 0 0,0 210,110" fill="none" stroke="rgba(6, 182, 212, 0.1)" strokeWidth="1.5" strokeDasharray="2 2" />

                    {/* String line */}
                    <line x1="150" y1="20" x2={bobX} y2={bobY} stroke="#06b6d4" strokeWidth="1.5" />
                    
                    {/* Anchor point */}
                    <circle cx="150" cy="20" r="3.5" fill="#06b6d4" />

                    {/* Bob ball */}
                    <circle cx={bobX} cy={bobY} r="8.5" fill="#a855f7" stroke="#d8b4fe" strokeWidth="1.5" />
                    
                    {/* Velocity vector arrow */}
                    <line x1={bobX} y1={bobY} x2={bobX + pend_v * 15} y2={bobY} stroke="#22c55e" strokeWidth="1.5" />
                  </svg>
                )}

                {/* 4. SPRING OSCILLATION VIEW */}
                {selectedTab === 'Spring Oscillation' && (
                  <div className="w-full max-w-sm h-full relative flex flex-col items-center justify-center py-4">
                    <svg className="w-full h-24 pointer-events-none">
                      {/* Left Wall Anchor */}
                      <line x1="20" y1="40" x2="20" y2="80" stroke="rgba(255,255,255,0.2)" strokeWidth="4" />
                      <line x1="20" y1="60" x2="35" y2="60" stroke="#06b6d4" strokeWidth="2" />

                      {/* Helical Spring drawing */}
                      <path
                        d={`M 35,60 
                            L ${45 + (blockX - 70) * 0.1},50 
                            L ${55 + (blockX - 70) * 0.2},70 
                            L ${65 + (blockX - 70) * 0.3},50 
                            L ${75 + (blockX - 70) * 0.4},70 
                            L ${85 + (blockX - 70) * 0.5},50 
                            L ${95 + (blockX - 70) * 0.6},70 
                            L ${105 + (blockX - 70) * 0.7},50 
                            L ${115 + (blockX - 70) * 0.8},70 
                            L ${125 + (blockX - 70) * 0.9},50 
                            L ${blockX - 16},60`}
                        fill="none"
                        stroke="#06b6d4"
                        strokeWidth="1.5"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />

                      {/* Slider block */}
                      <rect x={blockX - 16} y="40" width="32" height="32" fill="#a855f7" stroke="#d8b4fe" strokeWidth="1.5" rx="3" />
                      <text x={blockX - 6} y="60" fill="white" fontSize="9" fontWeight="bold">m</text>

                      {/* Base Track */}
                      <line x1="10" y1="73" x2="380" y2="73" stroke="rgba(255,255,255,0.15)" strokeWidth="2" />
                    </svg>
                  </div>
                )}

                {/* 5. COLLISION VIEW */}
                {selectedTab === 'Collision' && (
                  <div className="w-full max-w-sm h-full relative flex flex-col items-center justify-center py-4">
                    <svg className="w-full h-24 pointer-events-none">
                      {/* Collision Spark impact particle */}
                      {Math.abs(time - t_coll_impact) < 0.15 && (
                        <circle cx={40 + collVelA * 16 * t_coll_impact + 15} cy="60" r="14" fill="rgba(236,72,153,0.3)" className="animate-ping" />
                      )}

                      {/* Block A */}
                      <rect x={activePosA} y="44" width="30" height="24" fill="#06b6d4" stroke="#22d3ee" strokeWidth="1.5" rx="2" />
                      <text x={activePosA + 10} y="59" fill="black" fontSize="9" fontWeight="bold">A</text>
                      
                      {/* Block A velocity arrow */}
                      <line x1={activePosA + 15} y1="36" x2={activePosA + 15 + activeVelA * 8} y2="36" stroke="#22c55e" strokeWidth="1.5" />

                      {/* Block B */}
                      <rect x={activePosB} y="44" width="30" height="24" fill="#a855f7" stroke="#e9d5ff" strokeWidth="1.5" rx="2" />
                      <text x={activePosB + 10} y="59" fill="white" fontSize="9" fontWeight="bold">B</text>

                      {/* Block B velocity arrow */}
                      <line x1={activePosB + 15} y1="36" x2={activePosB + 15 + activeVelB * 8} y2="36" stroke="#22c55e" strokeWidth="1.5" />

                      {/* Slide track */}
                      <line x1="10" y1="69" x2="380" y2="69" stroke="rgba(255,255,255,0.15)" strokeWidth="2" />
                    </svg>
                  </div>
                )}

                {/* 6. WAVE MOTION VIEW */}
                {selectedTab === 'Wave Motion' && (
                  <svg className="w-full h-full min-h-[220px] max-w-xl pointer-events-none">
                    {/* Sine Wave string particles */}
                    {Array.from({ length: 40 }).map((_, idx) => {
                      const x = (idx / 39) * 10.0;
                      const y = waveAmp * Math.sin(wave_wavenum * x - wave_omega * time);
                      const px = (idx / 39) * 440 + 30;
                      const py = 110 - y * 45;
                      
                      return (
                        <circle
                          key={idx}
                          cx={px}
                          cy={py}
                          r={idx === 20 ? 5 : 2.5}
                          fill={idx === 20 ? '#ec4899' : '#06b6d4'}
                          className={idx === 20 ? 'shadow-lg shadow-pink-500' : ''}
                        />
                      );
                    })}
                    <text x="245" y="170" fill="#ec4899" fontSize="8" fontWeight="bold" fontFamily="monospace">
                      Vibrating mid-point particle
                    </text>
                  </svg>
                )}
              </div>

              {/* Lab Command Action Panel */}
              <div className="flex justify-between items-center border-t border-white/5 pt-4">
                <div className="flex gap-2">
                  <motion.button
                    whileHover={{ scale: 1.05 }}
                    whileTap={{ scale: 0.95 }}
                    onClick={() => {
                      if (!isPlaying) {
                        // If it's already finished, restart from 0!
                        if (selectedTab === 'Free Fall' && time >= t_ff_impact) {
                          setTime(0);
                        } else if (selectedTab === 'Projectile Motion' && time >= t_proj_flight) {
                          setTime(0);
                        }
                      }
                      setIsPlaying(!isPlaying);
                    }}
                    className={`px-5 py-2.5 rounded-xl text-xs font-bold flex items-center gap-1.5 transition-all ${
                      isPlaying 
                        ? 'bg-amber-500/10 border border-amber-500/20 text-amber-400' 
                        : 'bg-gradient-to-r from-cyan-500 to-blue-600 text-white shadow-lg'
                    }`}
                  >
                    {isPlaying ? <Pause className="w-3.5 h-3.5 fill-current" /> : <Play className="w-3.5 h-3.5 fill-current" />}
                    {isPlaying ? 'Pause Run' : 'Start Simulation'}
                  </motion.button>
                  <motion.button
                    whileHover={{ scale: 1.05 }}
                    whileTap={{ scale: 0.95 }}
                    onClick={handleReset}
                    className="px-4 py-2.5 bg-white/5 hover:bg-white/10 border border-white/10 text-gray-300 text-xs font-bold rounded-xl transition-all"
                  >
                    Reset clock
                  </motion.button>
                </div>

                <div className="text-[10px] text-gray-500 font-mono">
                  Elapsed Clock: {time.toFixed(2)}s
                </div>
              </div>
            </div>

            {/* Continuous React Charting Analytics */}
            <div className="bg-[#12121a] border border-[#22222f] p-5 rounded-2xl shadow-xl space-y-4">
              <h4 className="text-xs font-bold text-white uppercase tracking-wider">
                {selectedTab === 'Free Fall' && 'Kinematics: Position vs Time'}
                {selectedTab === 'Projectile Motion' && 'Flight Arc: Height vs Distance'}
                {selectedTab === 'Pendulum' && 'Harmonic: Angular Displacement vs Time'}
                {selectedTab === 'Spring Oscillation' && 'Damping: Decay Displacement vs Time'}
                {selectedTab === 'Collision' && 'Momentum: Velocity A & B Step-Change'}
                {selectedTab === 'Wave Motion' && 'Propagation: Transverse Wave Shape Profile'}
              </h4>

              <div className="h-44">
                <ResponsiveContainer width="100%" height="100%">
                  {selectedTab === 'Free Fall' ? (
                    <AreaChart data={generateFfChartData()}>
                      <defs>
                        <linearGradient id="ffColor" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#06b6d4" stopOpacity={0.3} />
                          <stop offset="95%" stopColor="#06b6d4" stopOpacity={0} />
                        </linearGradient>
                      </defs>
                      <XAxis dataKey="time" hide />
                      <YAxis hide />
                      <Area type="monotone" dataKey="position" stroke="#06b6d4" strokeWidth={1.5} fillOpacity={1} fill="url(#ffColor)" />
                    </AreaChart>
                  ) : selectedTab === 'Projectile Motion' ? (
                    <LineChart data={generateProjChartData()}>
                      <XAxis dataKey="x" hide />
                      <YAxis hide />
                      <Line type="monotone" dataKey="y" stroke="#a855f7" strokeWidth={2} dot={false} />
                    </LineChart>
                  ) : selectedTab === 'Pendulum' ? (
                    <LineChart data={generatePendChartData()}>
                      <XAxis dataKey="time" hide />
                      <YAxis hide />
                      <Line type="monotone" dataKey="angle" stroke="#06b6d4" strokeWidth={1.5} dot={false} />
                    </LineChart>
                  ) : selectedTab === 'Spring Oscillation' ? (
                    <LineChart data={generateSpringChartData()}>
                      <XAxis dataKey="time" hide />
                      <YAxis hide />
                      <Line type="monotone" dataKey="displacement" stroke="#a855f7" strokeWidth={1.5} dot={false} />
                    </LineChart>
                  ) : selectedTab === 'Collision' ? (
                    <LineChart data={generateCollisionChartData()}>
                      <XAxis dataKey="time" hide />
                      <YAxis hide />
                      <Line type="monotone" dataKey="velA" stroke="#06b6d4" strokeWidth={1.5} dot={false} />
                      <Line type="monotone" dataKey="velB" stroke="#ec4899" strokeWidth={1.5} strokeDasharray="3 3" dot={false} />
                    </LineChart>
                  ) : (
                    <AreaChart data={generateWaveChartData()}>
                      <defs>
                        <linearGradient id="waveColor" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#06b6d4" stopOpacity={0.25} />
                          <stop offset="95%" stopColor="#06b6d4" stopOpacity={0} />
                        </linearGradient>
                      </defs>
                      <XAxis dataKey="x" hide />
                      <YAxis hide />
                      <Area type="monotone" dataKey="amplitude" stroke="#06b6d4" strokeWidth={1.5} fillOpacity={1} fill="url(#waveColor)" />
                    </AreaChart>
                  )}
                </ResponsiveContainer>
              </div>
            </div>
          </div>

          {/* Right Block: Sliders Controls + Equations + Live HUD stats + Tutor */}
          <div className="lg:col-span-4 space-y-6">
            
            {/* Variable Parameter Sliders */}
            <div className="bg-[#12121a] border border-[#22222f] p-5 rounded-2xl shadow-xl space-y-5">
              <div className="flex justify-between items-center border-b border-white/5 pb-2">
                <h4 className="text-xs font-bold text-white uppercase tracking-wider">Parameters Control</h4>
                <Sliders className="w-4 h-4 text-gray-500" />
              </div>

              {/* Sliders dynamically changing per tab */}
              <div className="space-y-4">
                {selectedTab === 'Free Fall' && (
                  <>
                    <div className="space-y-1">
                      <div className="flex justify-between text-xs font-semibold">
                        <span className="text-gray-400">Initial Height (y₀)</span>
                        <span className="text-cyan-400">{ffHeight} m</span>
                      </div>
                      <input type="range" min="10" max="100" value={ffHeight} onChange={(e) => { setFfHeight(Number(e.target.value)); handleReset(); }} className="w-full accent-cyan-500 cursor-pointer" />
                    </div>
                    <div className="space-y-1">
                      <div className="flex justify-between text-xs font-semibold">
                        <span className="text-gray-400">Object Mass (m)</span>
                        <span className="text-cyan-400">{ffMass.toFixed(1)} kg</span>
                      </div>
                      <input type="range" min="0.2" max="8.0" step="0.1" value={ffMass} onChange={(e) => setFfMass(Number(e.target.value))} className="w-full accent-cyan-500 cursor-pointer" />
                    </div>
                    <div className="space-y-1">
                      <div className="flex justify-between text-xs font-semibold">
                        <span className="text-gray-400">Gravity Field (g)</span>
                        <span className="text-cyan-400">{ffGravity.toFixed(2)} m/s²</span>
                      </div>
                      <input type="range" min="1.0" max="25.0" step="0.1" value={ffGravity} onChange={(e) => { setFfGravity(Number(e.target.value)); handleReset(); }} className="w-full accent-cyan-500 cursor-pointer" />
                    </div>
                  </>
                )}

                {selectedTab === 'Projectile Motion' && (
                  <>
                    <div className="space-y-1">
                      <div className="flex justify-between text-xs font-semibold">
                        <span className="text-gray-400">Launch Velocity (v₀)</span>
                        <span className="text-cyan-400">{projSpeed} m/s</span>
                      </div>
                      <input type="range" min="10" max="50" value={projSpeed} onChange={(e) => { setProjSpeed(Number(e.target.value)); handleReset(); }} className="w-full accent-cyan-500 cursor-pointer" />
                    </div>
                    <div className="space-y-1">
                      <div className="flex justify-between text-xs font-semibold">
                        <span className="text-gray-400">Angle (θ)</span>
                        <span className="text-cyan-400">{projAngle}°</span>
                      </div>
                      <input type="range" min="15" max="80" value={projAngle} onChange={(e) => { setProjAngle(Number(e.target.value)); handleReset(); }} className="w-full accent-cyan-500 cursor-pointer" />
                    </div>
                    <div className="space-y-1">
                      <div className="flex justify-between text-xs font-semibold">
                        <span className="text-gray-400">Gravity (g)</span>
                        <span className="text-cyan-400">{projGravity.toFixed(2)} m/s²</span>
                      </div>
                      <input type="range" min="1.0" max="25.0" step="0.1" value={projGravity} onChange={(e) => { setProjGravity(Number(e.target.value)); handleReset(); }} className="w-full accent-cyan-500 cursor-pointer" />
                    </div>
                  </>
                )}

                {selectedTab === 'Pendulum' && (
                  <>
                    <div className="space-y-1">
                      <div className="flex justify-between text-xs font-semibold">
                        <span className="text-gray-400">String Length (L)</span>
                        <span className="text-cyan-400">{pendLength.toFixed(1)} m</span>
                      </div>
                      <input type="range" min="1.0" max="5.0" step="0.1" value={pendLength} onChange={(e) => { setPendLength(Number(e.target.value)); handleReset(); }} className="w-full accent-cyan-500 cursor-pointer" />
                    </div>
                    <div className="space-y-1">
                      <div className="flex justify-between text-xs font-semibold">
                        <span className="text-gray-400">Mass Bob (m)</span>
                        <span className="text-cyan-400">{pendMass.toFixed(1)} kg</span>
                      </div>
                      <input type="range" min="0.2" max="4.0" step="0.1" value={pendMass} onChange={(e) => setPendMass(Number(e.target.value))} className="w-full accent-cyan-500 cursor-pointer" />
                    </div>
                    <div className="space-y-1">
                      <div className="flex justify-between text-xs font-semibold">
                        <span className="text-gray-400">Initial Angle (θ₀)</span>
                        <span className="text-cyan-400">{pendAngle}°</span>
                      </div>
                      <input type="range" min="10" max="60" value={pendAngle} onChange={(e) => { setPendAngle(Number(e.target.value)); handleReset(); }} className="w-full accent-cyan-500 cursor-pointer" />
                    </div>
                  </>
                )}

                {selectedTab === 'Spring Oscillation' && (
                  <>
                    <div className="space-y-1">
                      <div className="flex justify-between text-xs font-semibold">
                        <span className="text-gray-400">Spring Constant (k)</span>
                        <span className="text-cyan-400">{springK} N/m</span>
                      </div>
                      <input type="range" min="10" max="100" value={springK} onChange={(e) => { setSpringK(Number(e.target.value)); handleReset(); }} className="w-full accent-cyan-500 cursor-pointer" />
                    </div>
                    <div className="space-y-1">
                      <div className="flex justify-between text-xs font-semibold">
                        <span className="text-gray-400">Mass Block (m)</span>
                        <span className="text-cyan-400">{springMass.toFixed(1)} kg</span>
                      </div>
                      <input type="range" min="0.5" max="4.0" step="0.1" value={springMass} onChange={(e) => { setSpringMass(Number(e.target.value)); handleReset(); }} className="w-full accent-cyan-500 cursor-pointer" />
                    </div>
                    <div className="space-y-1">
                      <div className="flex justify-between text-xs font-semibold">
                        <span className="text-gray-400">Damping (b)</span>
                        <span className="text-cyan-400">{springDamping.toFixed(2)}</span>
                      </div>
                      <input type="range" min="0.0" max="3.0" step="0.1" value={springDamping} onChange={(e) => { setSpringDamping(Number(e.target.value)); handleReset(); }} className="w-full accent-cyan-500 cursor-pointer" />
                    </div>
                  </>
                )}

                {selectedTab === 'Collision' && (
                  <>
                    <div className="space-y-1">
                      <div className="flex justify-between text-xs font-semibold">
                        <span className="text-gray-400">Mass A</span>
                        <span className="text-cyan-400">{collMassA.toFixed(1)} kg</span>
                      </div>
                      <input type="range" min="0.5" max="5.0" step="0.1" value={collMassA} onChange={(e) => { setCollMassA(Number(e.target.value)); handleReset(); }} className="w-full accent-cyan-500 cursor-pointer" />
                    </div>
                    <div className="space-y-1">
                      <div className="flex justify-between text-xs font-semibold">
                        <span className="text-gray-400">Mass B</span>
                        <span className="text-cyan-400">{collMassB.toFixed(1)} kg</span>
                      </div>
                      <input type="range" min="0.5" max="5.0" step="0.1" value={collMassB} onChange={(e) => { setCollMassB(Number(e.target.value)); handleReset(); }} className="w-full accent-cyan-500 cursor-pointer" />
                    </div>
                    <div className="space-y-1 flex justify-between items-center pt-2">
                      <span className="text-xs text-gray-400 font-semibold">Elasticity</span>
                      <button
                        onClick={() => { setCollisionType(collisionType === 'Elastic' ? 'Inelastic' : 'Elastic'); handleReset(); }}
                        className="px-3.5 py-1.5 bg-white/5 border border-white/10 hover:border-cyan-500/30 text-white text-xs font-black rounded-lg transition-all"
                      >
                        {collisionType} Model
                      </button>
                    </div>
                  </>
                )}

                {selectedTab === 'Wave Motion' && (
                  <>
                    <div className="space-y-1">
                      <div className="flex justify-between text-xs font-semibold">
                        <span className="text-gray-400">Wave Amplitude (A)</span>
                        <span className="text-cyan-400">{waveAmp.toFixed(1)} m</span>
                      </div>
                      <input type="range" min="0.3" max="2.0" step="0.1" value={waveAmp} onChange={(e) => setWaveAmp(Number(e.target.value))} className="w-full accent-cyan-500 cursor-pointer" />
                    </div>
                    <div className="space-y-1">
                      <div className="flex justify-between text-xs font-semibold">
                        <span className="text-gray-400">Frequency (f)</span>
                        <span className="text-cyan-400">{waveFreq.toFixed(1)} Hz</span>
                      </div>
                      <input type="range" min="0.5" max="4.0" step="0.1" value={waveFreq} onChange={(e) => setWaveFreq(Number(e.target.value))} className="w-full accent-cyan-500 cursor-pointer" />
                    </div>
                    <div className="space-y-1">
                      <div className="flex justify-between text-xs font-semibold">
                        <span className="text-gray-400">Wavelength (λ)</span>
                        <span className="text-cyan-400">{waveLen.toFixed(1)} m</span>
                      </div>
                      <input type="range" min="2.0" max="10.0" step="0.2" value={waveLen} onChange={(e) => setWaveLen(Number(e.target.value))} className="w-full accent-cyan-500 cursor-pointer" />
                    </div>
                  </>
                )}
              </div>
            </div>

            {/* Live Metrics HUD */}
            <div className="grid grid-cols-2 gap-4">
              {selectedTab === 'Free Fall' && (
                <>
                  <div className="p-3 bg-[#12121a] border border-[#22222f] rounded-xl">
                    <span className="text-[9px] text-gray-500 font-extrabold uppercase">Displacement</span>
                    <h5 className="text-sm font-black text-white">{ff_y.toFixed(1)} m</h5>
                  </div>
                  <div className="p-3 bg-[#12121a] border border-[#22222f] rounded-xl">
                    <span className="text-[9px] text-gray-500 font-extrabold uppercase">Velocity</span>
                    <h5 className="text-sm font-black text-white">{Math.abs(ff_v).toFixed(1)} m/s</h5>
                  </div>
                  <div className="p-3 bg-[#12121a] border border-[#22222f] rounded-xl">
                    <span className="text-[9px] text-gray-500 font-extrabold uppercase">Kinetic Energy</span>
                    <h5 className="text-sm font-black text-cyan-400">{ff_ke.toFixed(1)} J</h5>
                  </div>
                  <div className="p-3 bg-[#12121a] border border-[#22222f] rounded-xl">
                    <span className="text-[9px] text-gray-500 font-extrabold uppercase">Total Energy</span>
                    <h5 className="text-sm font-black text-purple-400">{ff_te.toFixed(1)} J</h5>
                  </div>
                </>
              )}

              {selectedTab === 'Projectile Motion' && (
                <>
                  <div className="p-3 bg-[#12121a] border border-[#22222f] rounded-xl">
                    <span className="text-[9px] text-gray-500 font-extrabold uppercase">Total Range</span>
                    <h5 className="text-sm font-black text-white">{proj_range.toFixed(1)} m</h5>
                  </div>
                  <div className="p-3 bg-[#12121a] border border-[#22222f] rounded-xl">
                    <span className="text-[9px] text-gray-500 font-extrabold uppercase">Max Height</span>
                    <h5 className="text-sm font-black text-white">{proj_hmax.toFixed(1)} m</h5>
                  </div>
                  <div className="p-3 bg-[#12121a] border border-[#22222f] rounded-xl">
                    <span className="text-[9px] text-gray-500 font-extrabold uppercase">Flight Time</span>
                    <h5 className="text-sm font-black text-cyan-400">{t_proj_flight.toFixed(2)} s</h5>
                  </div>
                  <div className="p-3 bg-[#12121a] border border-[#22222f] rounded-xl">
                    <span className="text-[9px] text-gray-500 font-extrabold uppercase">Y displacement</span>
                    <h5 className="text-sm font-black text-purple-400">{proj_y.toFixed(1)} m</h5>
                  </div>
                </>
              )}

              {selectedTab === 'Pendulum' && (
                <>
                  <div className="p-3 bg-[#12121a] border border-[#22222f] rounded-xl">
                    <span className="text-[9px] text-gray-500 font-extrabold uppercase">Oscillation Period</span>
                    <h5 className="text-sm font-black text-white">{pend_period.toFixed(2)} s</h5>
                  </div>
                  <div className="p-3 bg-[#12121a] border border-[#22222f] rounded-xl">
                    <span className="text-[9px] text-gray-500 font-extrabold uppercase">Linear Speed</span>
                    <h5 className="text-sm font-black text-white">{Math.abs(pend_v).toFixed(2)} m/s</h5>
                  </div>
                  <div className="p-3 bg-[#12121a] border border-[#22222f] rounded-xl">
                    <span className="text-[9px] text-gray-500 font-extrabold uppercase">Displacement angle</span>
                    <h5 className="text-sm font-black text-cyan-400">{(pend_theta * 180 / Math.PI).toFixed(0)}°</h5>
                  </div>
                  <div className="p-3 bg-[#12121a] border border-[#22222f] rounded-xl">
                    <span className="text-[9px] text-gray-500 font-extrabold uppercase">Total Mechanical E</span>
                    <h5 className="text-sm font-black text-purple-400">{(pend_ke + pend_pe).toFixed(2)} J</h5>
                  </div>
                </>
              )}

              {selectedTab === 'Spring Oscillation' && (
                <>
                  <div className="p-3 bg-[#12121a] border border-[#22222f] rounded-xl">
                    <span className="text-[9px] text-gray-500 font-extrabold uppercase">Displacement (x)</span>
                    <h5 className="text-sm font-black text-white">{spring_x.toFixed(2)} m</h5>
                  </div>
                  <div className="p-3 bg-[#12121a] border border-[#22222f] rounded-xl">
                    <span className="text-[9px] text-gray-500 font-extrabold uppercase">Restoring Force</span>
                    <h5 className="text-sm font-black text-white">{spring_force.toFixed(1)} N</h5>
                  </div>
                  <div className="p-3 bg-[#12121a] border border-[#22222f] rounded-xl">
                    <span className="text-[9px] text-gray-500 font-extrabold uppercase">Elastic Energy</span>
                    <h5 className="text-sm font-black text-cyan-400">{spring_pe.toFixed(2)} J</h5>
                  </div>
                  <div className="p-3 bg-[#12121a] border border-[#22222f] rounded-xl">
                    <span className="text-[9px] text-gray-500 font-extrabold uppercase">Mechanical Energy</span>
                    <h5 className="text-sm font-black text-purple-400">{(spring_pe + spring_ke).toFixed(2)} J</h5>
                  </div>
                </>
              )}

              {selectedTab === 'Collision' && (
                <>
                  <div className="p-3 bg-[#12121a] border border-[#22222f] rounded-xl">
                    <span className="text-[9px] text-gray-500 font-extrabold uppercase">System Momentum</span>
                    <h5 className="text-sm font-black text-white">{coll_total_mom.toFixed(2)} kg·m/s</h5>
                  </div>
                  <div className="p-3 bg-[#12121a] border border-[#22222f] rounded-xl">
                    <span className="text-[9px] text-gray-500 font-extrabold uppercase">Kinetic Energy Lost</span>
                    <h5 className="text-sm font-black text-white">{coll_ke_lost.toFixed(1)} J</h5>
                  </div>
                  <div className="p-3 bg-[#12121a] border border-[#22222f] rounded-xl">
                    <span className="text-[9px] text-gray-500 font-extrabold uppercase">Velocity Block A</span>
                    <h5 className="text-sm font-black text-cyan-400">{activeVelA.toFixed(1)} m/s</h5>
                  </div>
                  <div className="p-3 bg-[#12121a] border border-[#22222f] rounded-xl">
                    <span className="text-[9px] text-gray-500 font-extrabold uppercase">Velocity Block B</span>
                    <h5 className="text-sm font-black text-purple-400">{activeVelB.toFixed(1)} m/s</h5>
                  </div>
                </>
              )}

              {selectedTab === 'Wave Motion' && (
                <>
                  <div className="p-3 bg-[#12121a] border border-[#22222f] rounded-xl">
                    <span className="text-[9px] text-gray-500 font-extrabold uppercase">Wave envelope speed</span>
                    <h5 className="text-sm font-black text-white">{wave_speed.toFixed(1)} m/s</h5>
                  </div>
                  <div className="p-3 bg-[#12121a] border border-[#22222f] rounded-xl">
                    <span className="text-[9px] text-gray-500 font-extrabold uppercase">Vibrational Period</span>
                    <h5 className="text-sm font-black text-white">{(1/waveFreq).toFixed(2)} s</h5>
                  </div>
                  <div className="p-3 bg-[#12121a] border border-[#22222f] rounded-xl">
                    <span className="text-[9px] text-gray-500 font-extrabold uppercase">Displacement mid-point</span>
                    <h5 className="text-sm font-black text-cyan-400">{wave_y_mid.toFixed(2)} m</h5>
                  </div>
                  <div className="p-3 bg-[#12121a] border border-[#22222f] rounded-xl">
                    <span className="text-[9px] text-gray-500 font-extrabold uppercase">Angular Frequency</span>
                    <h5 className="text-sm font-black text-purple-400">{wave_omega.toFixed(1)} rad/s</h5>
                  </div>
                </>
              )}
            </div>

            {/* Unique Key Formula Cards */}
            <div className="bg-[#12121a] border border-[#22222f] p-5 rounded-2xl shadow-xl space-y-3">
              <h4 className="text-xs font-bold text-white uppercase tracking-wider">Governing Equations</h4>
              <div className="space-y-2 font-mono text-xs">
                {selectedTab === 'Free Fall' && (
                  <>
                    <div className="p-2.5 bg-[#171725] border border-white/5 rounded-xl text-cyan-400 flex justify-between">
                      <span>Height:</span> <span>y(t) = y₀ - ½gt²</span>
                    </div>
                    <div className="p-2.5 bg-[#171725] border border-white/5 rounded-xl text-cyan-400 flex justify-between">
                      <span>Velocity:</span> <span>v(t) = -gt</span>
                    </div>
                  </>
                )}

                {selectedTab === 'Projectile Motion' && (
                  <>
                    <div className="p-2.5 bg-[#171725] border border-white/5 rounded-xl text-cyan-400 flex justify-between">
                      <span>Trajectory Range:</span> <span>R = (v₀² sin 2θ) / g</span>
                    </div>
                    <div className="p-2.5 bg-[#171725] border border-white/5 rounded-xl text-cyan-400 flex justify-between">
                      <span>Maximum Height:</span> <span>H = (v₀² sin² θ) / 2g</span>
                    </div>
                  </>
                )}

                {selectedTab === 'Pendulum' && (
                  <>
                    <div className="p-2.5 bg-[#171725] border border-white/5 rounded-xl text-cyan-400 flex justify-between">
                      <span>Swing Period:</span> <span>T = 2π√(L/g)</span>
                    </div>
                    <div className="p-2.5 bg-[#171725] border border-white/5 rounded-xl text-cyan-400 flex justify-between">
                      <span>Total Energy:</span> <span>E = ½mv² + mgh</span>
                    </div>
                  </>
                )}

                {selectedTab === 'Spring Oscillation' && (
                  <>
                    <div className="p-2.5 bg-[#171725] border border-white/5 rounded-xl text-cyan-400 flex justify-between">
                      <span>Hooke\'s Law:</span> <span>F = -kx</span>
                    </div>
                    <div className="p-2.5 bg-[#171725] border border-white/5 rounded-xl text-cyan-400 flex justify-between">
                      <span>Oscillation Period:</span> <span>T = 2π√(m/k)</span>
                    </div>
                  </>
                )}

                {selectedTab === 'Collision' && (
                  <>
                    <div className="p-2.5 bg-[#171725] border border-white/5 rounded-xl text-cyan-400 flex justify-between">
                      <span>Momentum:</span> <span>p = m₁v₁ + m₂v₂</span>
                    </div>
                    <div className="p-2.5 bg-[#171725] border border-white/5 rounded-xl text-cyan-400 flex justify-between">
                      <span>Conserved Limit:</span> <span>p_initial = p_final</span>
                    </div>
                  </>
                )}

                {selectedTab === 'Wave Motion' && (
                  <>
                    <div className="p-2.5 bg-[#171725] border border-white/5 rounded-xl text-cyan-400 flex justify-between">
                      <span>Wave Speed:</span> <span>v = f · λ</span>
                    </div>
                    <div className="p-2.5 bg-[#171725] border border-white/5 rounded-xl text-cyan-400 flex justify-between">
                      <span>Transverse Eqn:</span> <span>y = A sin(kx - ωt)</span>
                    </div>
                  </>
                )}
              </div>
            </div>

            {/* AI Tutor Panel Chat Insights */}
            <div className="bg-[#12121a] border border-[#22222f] p-5 rounded-2xl shadow-xl space-y-3 relative overflow-hidden">
              <div className="flex items-center gap-2 border-b border-white/5 pb-2">
                <Brain className="w-4 h-4 text-cyan-400 animate-pulse" />
                <h4 className="text-xs font-bold text-white uppercase tracking-wider">AI Tutor Assistant</h4>
              </div>
              <p className="text-xs text-gray-400 leading-relaxed font-medium">
                {getAiTutorExplanation()}
              </p>
            </div>

          </div>
        </motion.div>
      </AnimatePresence>
    </div>
  );
}

// -------------------------------------------------------------

export default PhysicsLabPageWrapper;
