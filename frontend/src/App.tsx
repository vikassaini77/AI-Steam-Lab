import { BrowserRouter, Routes, Route, Navigate, useNavigate } from 'react-router-dom';
import { useState, useEffect, Suspense as ReactSuspense } from 'react';
import { ErrorBoundary } from 'react-error-boundary';
import { lazy } from 'react';
import { supabase } from './lib/supabase';
import LandingPage from './pages/LandingPage';
import Dashboard from './pages/Dashboard';
import IntroLoading from './pages/IntroLoading';
import CookieConsent from './components/landing/CookieConsent';

const AuthPage = lazy(() => import('./pages/AuthPage'));
const ProfilePage = lazy(() => import('./pages/ProfilePage'));
const SecurityPage = lazy(() => import('./pages/SecurityPage'));
const PrivacyPage = lazy(() => import('./pages/PrivacyPage'));
const TermsPage = lazy(() => import('./pages/TermsPage'));
const TrustPage = lazy(() => import('./pages/TrustPage'));

// Lazy load new professional SaaS footer pages
const FeaturesPage = lazy(() => import('./pages/FeaturesPage'));
const PricingPage = lazy(() => import('./pages/PricingPage'));
const DocsPage = lazy(() => import('./pages/DocsPage'));
const AboutPage = lazy(() => import('./pages/AboutPage'));
const ContactPage = lazy(() => import('./pages/ContactPage'));
const CareersPage = lazy(() => import('./pages/CareersPage'));
const BlogPage = lazy(() => import('./pages/BlogPage'));
const CookiesPage = lazy(() => import('./pages/CookiesPage'));
const AITutorPage = lazy(() => import('./pages/AITutorPage'));

const PageLoader = () => (
  <div className="min-h-screen bg-[#0a0a1a] flex items-center justify-center">
    <div className="flex flex-col items-center gap-4">
      <div className="w-10 h-10 border-2 border-cyan-500 border-t-transparent rounded-full animate-spin" />
      <span className="text-gray-500 text-sm tracking-wider uppercase">Loading</span>
    </div>
  </div>
);

function AppContent() {
  const navigate = useNavigate();
  const [session, setSession] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [currentPage, setCurrentPage] = useState<'landing' | 'intro' | 'auth'>('landing');

  useEffect(() => {
    const initAuth = async () => {
      try {
        const { data: { session } } = await supabase.auth.getSession();
        setSession(session);
      } catch (error) {
        console.error('Auth init error:', error);
      } finally {
        setLoading(false);
      }
    };

    initAuth();

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      setSession(session);
      if (session) {
        setCurrentPage('landing');
      }
    });

    return () => subscription?.unsubscribe();
  }, []);

  const handleLaunchLab = () => {
    if (session) {
      navigate('/dashboard');
    } else {
      setCurrentPage('intro');
    }
  };

  const handleIntroComplete = () => {
    setCurrentPage('auth');
  };

  const RequireAuthFallback = () => {
    useEffect(() => {
      setCurrentPage('intro');
      navigate('/', { replace: true });
    }, []);
    return <PageLoader />;
  };

  if (loading) {
    return <PageLoader />;
  }

  // Show intro loading
  if (currentPage === 'intro') {
    return <IntroLoading onComplete={handleIntroComplete} />;
  }

  // Show auth page
  if (currentPage === 'auth') {
    return (
      <ReactSuspense fallback={<PageLoader />}>
        <AuthPage onAuthSuccess={() => setCurrentPage('landing')} />
      </ReactSuspense>
    );
  }

  // Show main routes
  return (
    <>
      <CookieConsent />
      <Routes>
        <Route path="/" element={<LandingPage onLaunchLab={handleLaunchLab} />} />
        <Route path="/auth" element={<Navigate to="/" replace />} />
        
        {/* Live Lab direct routing */}
        <Route 
          path="/live-lab" 
          element={session ? <Navigate to="/dashboard" replace /> : <RequireAuthFallback />} 
        />
        <Route 
          path="/ai-tutor" 
          element={session ? <Navigate to="/dashboard/ai-tutor" replace /> : <RequireAuthFallback />} 
        />
        
        <Route
          path="/dashboard/*"
          element={session ? <Dashboard session={session} /> : <Navigate to="/" replace />}
        />
        <Route
          path="/profile"
          element={
            session ? (
              <ReactSuspense fallback={<PageLoader />}>
                <ProfilePage session={session} />
              </ReactSuspense>
            ) : (
              <Navigate to="/" replace />
            )
          }
        />
        <Route
          path="/security"
          element={
            <ReactSuspense fallback={<PageLoader />}>
              <SecurityPage />
            </ReactSuspense>
          }
        />
        <Route
          path="/reset-password"
          element={
            <ReactSuspense fallback={<PageLoader />}>
              <AuthPage onAuthSuccess={() => navigate('/')} initialView="reset" />
            </ReactSuspense>
          }
        />
        <Route
          path="/privacy"
          element={
            <ReactSuspense fallback={<PageLoader />}>
              <PrivacyPage />
            </ReactSuspense>
          }
        />
        <Route
          path="/terms"
          element={
            <ReactSuspense fallback={<PageLoader />}>
              <TermsPage />
            </ReactSuspense>
          }
        />
        <Route
          path="/trust"
          element={
            <ReactSuspense fallback={<PageLoader />}>
              <TrustPage />
            </ReactSuspense>
          }
        />
        
        {/* Dynamic SaaS pages routing config */}
        <Route
          path="/features"
          element={
            <ReactSuspense fallback={<PageLoader />}>
              <FeaturesPage />
            </ReactSuspense>
          }
        />
        <Route
          path="/pricing"
          element={
            <ReactSuspense fallback={<PageLoader />}>
              <PricingPage />
            </ReactSuspense>
          }
        />
        <Route
          path="/docs"
          element={
            <ReactSuspense fallback={<PageLoader />}>
              <DocsPage />
            </ReactSuspense>
          }
        />
        <Route
          path="/about"
          element={
            <ReactSuspense fallback={<PageLoader />}>
              <AboutPage />
            </ReactSuspense>
          }
        />
        <Route
          path="/contact"
          element={
            <ReactSuspense fallback={<PageLoader />}>
              <ContactPage />
            </ReactSuspense>
          }
        />
        <Route
          path="/careers"
          element={
            <ReactSuspense fallback={<PageLoader />}>
              <CareersPage />
            </ReactSuspense>
          }
        />
        <Route
          path="/blog"
          element={
            <ReactSuspense fallback={<PageLoader />}>
              <BlogPage />
            </ReactSuspense>
          }
        />
        <Route
          path="/cookies"
          element={
            <ReactSuspense fallback={<PageLoader />}>
              <CookiesPage />
            </ReactSuspense>
          }
        />
        <Route
          path="/ai-tutor"
          element={
            session ? (
              <ReactSuspense fallback={<PageLoader />}>
                <AITutorPage />
              </ReactSuspense>
            ) : (
              <RequireAuthFallback />
            )
          }
        />

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </>
  );
}

const GlobalErrorFallback = ({ error, resetErrorBoundary }: any) => (
  <div className="min-h-screen bg-[#0a0a1a] flex flex-col items-center justify-center p-6 text-center font-sans">
    <div className="bg-red-500/10 border border-red-500/20 p-8 rounded-2xl max-w-lg w-full">
      <div className="w-16 h-16 bg-red-500/20 rounded-full flex items-center justify-center mx-auto mb-6">
        <span className="text-red-500 text-2xl font-bold">!</span>
      </div>
      <h2 className="text-2xl font-bold text-white mb-4">System Anomaly Detected</h2>
      <p className="text-gray-400 mb-6 text-sm">We encountered a temporary disruption in the NeuroLab matrix.</p>
      <div className="bg-black/50 p-4 rounded-xl mb-6 text-left overflow-x-auto">
        <p className="text-red-400 font-mono text-xs">{error.message}</p>
      </div>
      <button 
        onClick={resetErrorBoundary}
        className="px-6 py-3 bg-gradient-to-r from-red-500 to-rose-600 hover:from-red-600 hover:to-rose-700 text-white rounded-xl font-medium transition-all shadow-lg shadow-red-500/20"
      >
        Reboot System
      </button>
    </div>
  </div>
);

export default function App() {
  return (
    <ErrorBoundary FallbackComponent={GlobalErrorFallback} onReset={() => window.location.replace('/')}>
      <BrowserRouter>
        <AppContent />
      </BrowserRouter>
    </ErrorBoundary>
  );
}
