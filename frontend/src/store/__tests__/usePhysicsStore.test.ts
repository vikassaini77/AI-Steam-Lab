import { describe, it, expect } from 'vitest';
import { usePhysicsStore } from '../usePhysicsStore';

describe('usePhysicsStore', () => {
  it('should initialize with correct default values for Free Fall', () => {
    const state = usePhysicsStore.getState();
    expect(state.ffMass).toBe(1.0);
    expect(state.ffHeight).toBe(50.0);
    expect(state.ffGravity).toBe(9.81);
  });

  it('should update free fall mass correctly', () => {
    const { setFfMass } = usePhysicsStore.getState();
    setFfMass(5.0);
    expect(usePhysicsStore.getState().ffMass).toBe(5.0);
  });

  it('should update wave motion attributes correctly', () => {
    const { setWaveAmp, setWaveFreq } = usePhysicsStore.getState();
    setWaveAmp(2.5);
    setWaveFreq(4.0);
    const state = usePhysicsStore.getState();
    expect(state.waveAmp).toBe(2.5);
    expect(state.waveFreq).toBe(4.0);
  });
});
