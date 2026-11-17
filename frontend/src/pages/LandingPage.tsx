import { Suspense, lazy } from 'react';
import { ErrorBoundary } from 'react-error-boundary';
import LandingNavbar from '../components/landing/LandingNavbar';
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
      {/* Top Navbar */}
      <LandingNavbar onLaunchLab={onLaunchLab} />

      {/* Particle background */}
      <ParticleBackground />

      {/* 3D floating elements */}
      <div className="fixed inset-0 z-0 pointer-events-none">
        <ErrorBoundary fallback={<div className="fixed inset-0 bg-gradient-to-b from-[#0a0a1a] via-[#0d0d25] to-[#0a0a1a]" />}>
          <Suspense fallback={<div />}>
            <FloatingElements />
          </Suspense>
        </ErrorBoundary>
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
