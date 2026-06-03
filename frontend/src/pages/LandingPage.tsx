import { Suspense, lazy } from 'react';
import ParticleBackground from '../components/landing/ParticleBackground';
import HeroSection from '../components/landing/HeroSection';
import FeatureSection from '../components/landing/FeatureSection';
import DemoPreview from '../components/landing/DemoPreview';
import Footer from '../components/landing/Footer';

const FloatingElements = lazy(() => import('../components/landing/FloatingElements'));

interface LandingPageProps {
  onLaunchLab: () => void;
}

export default function LandingPage({ onLaunchLab }: LandingPageProps) {
  return (
    <div className="relative min-h-screen bg-[#0a0a1a] overflow-x-hidden">
      {/* Particle background */}
      <ParticleBackground />

      {/* 3D floating elements */}
      <div className="fixed inset-0 z-0">
        <Suspense fallback={<div />}>
          <FloatingElements />
        </Suspense>
      </div>

      {/* Main content */}
      <div className="relative z-10">
        <HeroSection onLaunchLab={onLaunchLab} />
        <FeatureSection />
        <DemoPreview onLaunchLab={onLaunchLab} />
        <Footer />
      </div>
    </div>
  );
}
