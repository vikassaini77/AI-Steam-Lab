import React, { Suspense, lazy } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import DashboardLayout from '../components/dashboard/DashboardLayout';
import WebcamSection from './dashboard/WebcamSection';

import DashboardHome from '../components/dashboard/DashboardHome';
import PhysicsLabPageWrapper from '../components/physics/PhysicsLabPageWrapper';
import ChallengesPage from '../components/dashboard/ChallengesPage';
import AchievementsPage from '../components/dashboard/AchievementsPage';
import ExperimentsCatalog from '../components/dashboard/ExperimentsCatalog';
import LeaderboardPage from './dashboard/LeaderboardPage';

const ProfilePage = lazy(() => import('./ProfilePage'));
const SecurityPage = lazy(() => import('./SecurityPage'));
const LabHistory = lazy(() => import('./dashboard/LabHistory'));
const AITutorPage = lazy(() => import('./AITutorPage'));

interface DashboardProps {
  session: any;
}

export default function Dashboard({ session }: DashboardProps) {
  return (
    <DashboardLayout>
      <div className="w-full min-h-screen">
        <Routes>
          <Route index element={<DashboardHome session={session} />} />
          <Route path="experiments" element={<ExperimentsCatalog />} />
          <Route path="experiments/active" element={<WebcamSection />} />
          <Route path="tutor" element={<Navigate to="/ai-tutor" replace />} />
          <Route path="physics" element={<PhysicsLabPageWrapper />} />
          <Route path="challenges" element={<ChallengesPage />} />
          <Route path="achievements" element={<AchievementsPage />} />
          <Route path="leaderboard" element={<LeaderboardPage />} />
          <Route
            path="history"
            element={
              <Suspense fallback={<div className="min-h-screen bg-[#0a0a1a]" />}>
                <LabHistory />
              </Suspense>
            }
          />
          <Route
            path="profile"
            element={
              <Suspense fallback={<div className="min-h-screen bg-[#0a0a1a]" />}>
                <ProfilePage session={session} />
              </Suspense>
            }
          />
          <Route
            path="security"
            element={
              <Suspense fallback={<div className="min-h-screen bg-[#0a0a1a]" />}>
                <SecurityPage />
              </Suspense>
            }
          />
        </Routes>
      </div>
    </DashboardLayout>
  );
}
