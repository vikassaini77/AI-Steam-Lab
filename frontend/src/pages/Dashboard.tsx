import { Suspense, lazy } from 'react';
import type { Session } from '@supabase/supabase-js';
import { Routes, Route, Navigate } from 'react-router-dom';
import { ErrorBoundary } from 'react-error-boundary';
import type { FallbackProps } from 'react-error-boundary';
import DashboardLayout from '../components/dashboard/DashboardLayout';
import WebcamSection from './dashboard/WebcamSection';

import DashboardHome from '../components/dashboard/DashboardHome';
import PhysicsLabPageWrapper from '../components/physics/PhysicsLabPageWrapper';
import ChallengesPage from '../components/dashboard/ChallengesPage';
import AchievementsPage from '../components/dashboard/AchievementsPage';
import ExperimentsCatalog from '../components/dashboard/ExperimentsCatalog';
import LeaderboardPage from './dashboard/LeaderboardPage';
import LabHistory from './dashboard/LabHistory';

const ProfilePage = lazy(() => import('./ProfilePage'));
const SecurityPage = lazy(() => import('./SecurityPage'));
const ExperimentWorkspace = lazy(() => import('../components/experiments/ExperimentWorkspace'));

const SectionLoader = () => (
  <div className="w-full min-h-[50vh] flex flex-col items-center justify-center space-y-3">
    <div className="w-8 h-8 border-2 border-cyan-400 border-t-transparent rounded-full animate-spin" />
    <span className="text-[11px] text-gray-400 uppercase tracking-widest font-mono">Initializing Lab...</span>
  </div>
);

function DashboardRouteFallback({ error, resetErrorBoundary }: FallbackProps) {
  const errorMessage = error instanceof Error ? error.message : String(error);
  return (
    <div className="p-8 max-w-xl mx-auto my-12 bg-[#12121a]/95 border border-cyan-500/30 rounded-3xl text-center space-y-4 shadow-2xl backdrop-blur-md">
      <div className="w-14 h-14 bg-cyan-500/10 border border-cyan-500/30 rounded-2xl flex items-center justify-center mx-auto text-2xl">
        🔬
      </div>
      <h2 className="text-xl font-bold text-white tracking-wide">Laboratory Module Interrupted</h2>
      <p className="text-xs text-gray-400 max-w-md mx-auto leading-relaxed">
        We encountered a display interruption while loading this section. Click below to reload the laboratory module.
      </p>
      {errorMessage && (
        <div className="bg-black/50 p-3 rounded-xl text-left overflow-x-auto text-[11px] font-mono text-cyan-400 border border-white/5">
          {errorMessage}
        </div>
      )}
      <div className="flex justify-center gap-3 pt-2">
        <button
          onClick={resetErrorBoundary}
          className="px-6 py-2.5 bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-white rounded-xl text-xs font-bold transition-all shadow-lg shadow-cyan-500/20"
        >
          Reload Laboratory 🔄
        </button>
      </div>
    </div>
  );
}

interface DashboardProps {
  session: Session | null;
}

export default function Dashboard({ session }: DashboardProps) {
  return (
    <DashboardLayout>
      <div className="w-full min-h-screen">
        <ErrorBoundary FallbackComponent={DashboardRouteFallback}>
          <Routes>
            <Route index element={<DashboardHome session={session} />} />
            <Route path="experiments" element={<ExperimentsCatalog />} />
            <Route path="experiments/active" element={<WebcamSection />} />
            <Route
              path="experiments/:expId"
              element={
                <Suspense fallback={<SectionLoader />}>
                  <ExperimentWorkspace />
                </Suspense>
              }
            />
            <Route path="tutor" element={<Navigate to="/ai-tutor" replace />} />
            <Route path="physics" element={<PhysicsLabPageWrapper />} />
            <Route path="challenges" element={<ChallengesPage />} />
            <Route path="achievements" element={<AchievementsPage />} />
            <Route path="leaderboard" element={<LeaderboardPage />} />
            <Route path="history" element={<LabHistory />} />
            <Route
              path="profile"
              element={
                <Suspense fallback={<SectionLoader />}>
                  <ProfilePage session={session} />
                </Suspense>
              }
            />
            <Route
              path="security"
              element={
                <Suspense fallback={<SectionLoader />}>
                  <SecurityPage />
                </Suspense>
              }
            />
          </Routes>
        </ErrorBoundary>
      </div>
    </DashboardLayout>
  );
}
