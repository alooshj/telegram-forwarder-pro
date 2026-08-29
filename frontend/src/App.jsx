import React, { useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ClerkProvider, useUser } from '@clerk/clerk-react';
import { teletipsClerkAppearance } from './theme/clerkTheme';
import { ProtectedRoute } from './components/ProtectedRoute';
import { SignInPage } from './components/SignInPage';
import { SignUpPage } from './components/SignUpPage';
import { DashboardLayout } from './components/layout/DashboardLayout';
import { OverviewView } from './components/dashboard/OverviewView';
import { PipelinesStudio } from './components/dashboard/PipelinesStudio';
import { SessionManager } from './components/dashboard/SessionManager';
import { LiveLogsTerminal } from './components/dashboard/LiveLogsTerminal';
import { BillingPayments } from './components/dashboard/BillingPayments';

const clerkPubKey =
  (typeof process !== 'undefined' && process.env && (process.env.REACT_APP_CLERK_PUBLISHABLE_KEY || process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY)) ||
  (typeof import.meta !== 'undefined' && import.meta.env && (import.meta.env.VITE_CLERK_PUBLISHABLE_KEY || import.meta.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY)) ||
  'pk_test_b3JpZW50ZWQtbXVsbGV0LTU2ODEuY2xlcmsuYWNjb3VudHMuZGV2JA';

if (!clerkPubKey) {
  throw new Error("Missing Clerk Publishable Key");
}

function MainDashboard() {
  const { user } = useUser();
  const [activeTab, setActiveTab] = useState('overview');
  const [isEngineRunning, setIsEngineRunning] = useState(true);

  // Auto-elevate super admin
  const userRole = user?.primaryEmailAddress?.emailAddress === 'alooshpal@gmail.com' ? 'super_admin' : 'client';

  return (
    <DashboardLayout
      activeTab={activeTab}
      onTabChange={setActiveTab}
      isEngineRunning={isEngineRunning}
      connectedSessionsCount={2}
      userRole={userRole}
    >
      {activeTab === 'overview' && (
        <OverviewView
          isEngineRunning={isEngineRunning}
          onNavigate={setActiveTab}
        />
      )}
      {activeTab === 'pipelines' && (
        <PipelinesStudio />
      )}
      {activeTab === 'sessions' && (
        <SessionManager />
      )}
      {activeTab === 'logs' && (
        <LiveLogsTerminal />
      )}
      {activeTab === 'pricing' && (
        <BillingPayments />
      )}
    </DashboardLayout>
  );
}

export function App() {
  return (
    <ClerkProvider publishableKey={clerkPubKey} appearance={teletipsClerkAppearance}>
      <BrowserRouter>
        <Routes>
          <Route path="/sign-in/*" element={<SignInPage />} />
          <Route path="/sign-up/*" element={<SignUpPage />} />
          <Route
            path="/dashboard/*"
            element={
              <ProtectedRoute>
                <MainDashboard />
              </ProtectedRoute>
            }
          />
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </BrowserRouter>
    </ClerkProvider>
  );
}

export default App;
