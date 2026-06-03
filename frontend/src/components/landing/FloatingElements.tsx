import { useRef } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { Sphere, MeshDistortMaterial, Float } from '@react-three/drei';
import * as THREE from 'three';

function Molecule({ position, color, size }: { position: [number, number, number]; color: string; size: number }) {
  const meshRef = useRef<THREE.Mesh>(null);

  useFrame((state) => {
    if (meshRef.current) {
      meshRef.current.rotation.x = state.clock.elapsedTime * 0.2;
      meshRef.current.rotation.y = state.clock.elapsedTime * 0.3;
    }
  });

  return (
    <Float speed={2} rotationIntensity={1} floatIntensity={2}>
      <Sphere ref={meshRef} args={[size, 64, 64]} position={position}>
        <MeshDistortMaterial
          color={color}
          attach="material"
          distort={0.4}
          speed={2}
          roughness={0.2}
          metalness={0.8}
          transparent
          opacity={0.7}
        />
      </Sphere>
    </Float>
  );
}

function AtomRing({ position, rotation }: { position: [number, number, number]; rotation: [number, number, number] }) {
  const ringRef = useRef<THREE.Mesh>(null);

  useFrame((state) => {
    if (ringRef.current) {
      ringRef.current.rotation.z = state.clock.elapsedTime * 0.5;
    }
  });

  return (
    <mesh ref={ringRef} position={position} rotation={rotation}>
      <torusGeometry args={[1.5, 0.02, 16, 100]} />
      <meshStandardMaterial color="#00D4FF" emissive="#00D4FF" emissiveIntensity={0.5} transparent opacity={0.6} />
    </mesh>
  );
}

function Electron({ orbitRadius, speed, offset }: { orbitRadius: number; speed: number; offset: number }) {
  const electronRef = useRef<THREE.Mesh>(null);

  useFrame((state) => {
    if (electronRef.current) {
      const time = state.clock.elapsedTime * speed + offset;
      electronRef.current.position.x = Math.cos(time) * orbitRadius;
      electronRef.current.position.z = Math.sin(time) * orbitRadius;
      electronRef.current.position.y = Math.sin(time * 2) * 0.3;
    }
  });

  return (
    <mesh ref={electronRef}>
      <sphereGeometry args={[0.08, 16, 16]} />
      <meshStandardMaterial color="#00FF88" emissive="#00FF88" emissiveIntensity={2} />
    </mesh>
  );
}

function Scene() {
  return (
    <>
      <ambientLight intensity={0.5} />
      <pointLight position={[10, 10, 10]} intensity={1} color="#00D4FF" />
      <pointLight position={[-10, -10, -10]} intensity={0.5} color="#7C3AED" />

      {/* Central atom */}
      <Molecule position={[0, 0, 0]} color="#7C3AED" size={0.8} />

      {/* Surrounding atoms */}
      <Molecule position={[3, 2, -2]} color="#00D4FF" size={0.4} />
      <Molecule position={[-2.5, -1.5, 1]} color="#06B6D4" size={0.5} />
      <Molecule position={[2, -2, 0]} color="#8B5CF6" size={0.35} />
      <Molecule position={[-1.5, 2.5, 2]} color="#0EA5E9" size={0.45} />

      {/* Atom rings */}
      <AtomRing position={[0, 0, 0]} rotation={[Math.PI / 4, 0, 0]} />
      <AtomRing position={[0, 0, 0]} rotation={[Math.PI / 2, Math.PI / 4, 0]} />

      {/* Electrons */}
      <Electron orbitRadius={2} speed={1} offset={0} />
      <Electron orbitRadius={2} speed={1} offset={Math.PI} />
      <Electron orbitRadius={2.5} speed={0.8} offset={Math.PI / 2} />
      <Electron orbitRadius={2.5} speed={0.8} offset={Math.PI * 1.5} />
    </>
  );
}

export default function FloatingElements() {
  return (
    <div className="absolute inset-0 z-0 opacity-80">
      <Canvas
        camera={{ position: [0, 0, 6], fov: 75 }}
        gl={{ antialias: true, alpha: true }}
      >
        <Scene />
      </Canvas>
    </div>
  );
}
