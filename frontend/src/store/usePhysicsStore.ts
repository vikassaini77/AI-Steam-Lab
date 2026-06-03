import { create } from 'zustand';

interface PhysicsState {
  // 1. Free Fall
  ffMass: number;
  ffHeight: number;
  ffGravity: number;
  setFfMass: (val: number) => void;
  setFfHeight: (val: number) => void;
  setFfGravity: (val: number) => void;

  // 2. Projectile
  projSpeed: number;
  projAngle: number;
  projGravity: number;
  projMass: number;
  setProjSpeed: (val: number) => void;
  setProjAngle: (val: number) => void;
  setProjGravity: (val: number) => void;
  setProjMass: (val: number) => void;

  // 3. Pendulum
  pendLength: number;
  pendMass: number;
  pendAngle: number;
  pendGravity: number;
  setPendLength: (val: number) => void;
  setPendMass: (val: number) => void;
  setPendAngle: (val: number) => void;
  setPendGravity: (val: number) => void;

  // 4. Spring Oscillation
  springK: number;
  springMass: number;
  springDisplacement: number;
  springDamping: number;
  setSpringK: (val: number) => void;
  setSpringMass: (val: number) => void;
  setSpringDisplacement: (val: number) => void;
  setSpringDamping: (val: number) => void;

  // 5. Collision
  collMassA: number;
  collMassB: number;
  collVelA: number;
  collVelB: number;
  collisionType: 'Elastic' | 'Inelastic';
  setCollMassA: (val: number) => void;
  setCollMassB: (val: number) => void;
  setCollVelA: (val: number) => void;
  setCollVelB: (val: number) => void;
  setCollisionType: (type: 'Elastic' | 'Inelastic') => void;

  // 6. Wave Motion
  waveAmp: number;
  waveFreq: number;
  waveLen: number;
  setWaveAmp: (val: number) => void;
  setWaveFreq: (val: number) => void;
  setWaveLen: (val: number) => void;
}

export const usePhysicsStore = create<PhysicsState>((set) => ({
  // 1. Free Fall
  ffMass: 1.0,
  ffHeight: 50.0,
  ffGravity: 9.81,
  setFfMass: (val) => set({ ffMass: val }),
  setFfHeight: (val) => set({ ffHeight: val }),
  setFfGravity: (val) => set({ ffGravity: val }),

  // 2. Projectile
  projSpeed: 25.0,
  projAngle: 45.0,
  projGravity: 9.81,
  projMass: 1.2,
  setProjSpeed: (val) => set({ projSpeed: val }),
  setProjAngle: (val) => set({ projAngle: val }),
  setProjGravity: (val) => set({ projGravity: val }),
  setProjMass: (val) => set({ projMass: val }),

  // 3. Pendulum
  pendLength: 2.5,
  pendMass: 1.2,
  pendAngle: 45.0,
  pendGravity: 9.81,
  setPendLength: (val) => set({ pendLength: val }),
  setPendMass: (val) => set({ pendMass: val }),
  setPendAngle: (val) => set({ pendAngle: val }),
  setPendGravity: (val) => set({ pendGravity: val }),

  // 4. Spring Oscillation
  springK: 40.0,
  springMass: 1.5,
  springDisplacement: 1.5,
  springDamping: 0.5,
  setSpringK: (val) => set({ springK: val }),
  setSpringMass: (val) => set({ springMass: val }),
  setSpringDisplacement: (val) => set({ springDisplacement: val }),
  setSpringDamping: (val) => set({ springDamping: val }),

  // 5. Collision
  collMassA: 2.0,
  collMassB: 1.5,
  collVelA: 5.0,
  collVelB: -3.0,
  collisionType: 'Elastic',
  setCollMassA: (val) => set({ collMassA: val }),
  setCollMassB: (val) => set({ collMassB: val }),
  setCollVelA: (val) => set({ collVelA: val }),
  setCollVelB: (val) => set({ collVelB: val }),
  setCollisionType: (val) => set({ collisionType: val }),

  // 6. Wave Motion
  waveAmp: 1.0,
  waveFreq: 1.5,
  waveLen: 6.0,
  setWaveAmp: (val) => set({ waveAmp: val }),
  setWaveFreq: (val) => set({ waveFreq: val }),
  setWaveLen: (val) => set({ waveLen: val }),
}));
