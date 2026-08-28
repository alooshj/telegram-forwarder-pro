import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ClerkProvider } from '@clerk/clerk-react';
import { teletipsClerkAppearance } from './theme/clerkTheme';
import { ProtectedRoute } from './components/ProtectedRoute';
import { SignInPage } from './components/SignInPage';
import { SignUpPage } from './components/SignUpPage';

// Read Clerk Publishable Key from environment variables
const CLERK_PUBLISHABLE_KEY =
  import.meta.env.VITE_CLERK_PUBLISHABLE_KEY ||
  import.meta.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY ||
  'pk_test_b3JpZW50ZWQtbXVsbGV0LTU2ODEuY2xlcmsuYWNjb3VudHMuZGV2JA';

function DashboardPlaceholder() {
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-8 flex flex-col items-center justify-center space-y-4">
      <div className="text-center space-y-2">
        <h1 className="text-3xl font-black text-white">⚡ مرحباً بك في لوحة تحكم TeleTips Pro</h1>
        <p className="text-slate-400 text-sm">تم تسجيل دخولك بنجاح عبر خدمة Clerk مع التحقق اللحظي من الهوية.</p>
      </div>
      <a
        href="/"
        className="px-6 py-3 rounded-xl font-bold text-white shadow-lg shadow-cyan-500/20 bg-gradient-to-r from-indigo-600 to-cyan-500 hover:opacity-90 transition"
      >
        الانتقال إلى الواجهة الحية (Full Live Dashboard)
      </a>
    </div>
  );
}

export function App() {
  if (!CLERK_PUBLISHABLE_KEY) {
    return (
      <div className="min-h-screen bg-slate-950 text-white flex items-center justify-center p-6">
        <div className="max-w-md bg-slate-900 border border-slate-800 p-6 rounded-2xl text-center space-y-3">
          <h2 className="text-lg font-bold text-rose-400">Missing Clerk Publishable Key</h2>
          <p className="text-xs text-slate-400">
            Please define <code>VITE_CLERK_PUBLISHABLE_KEY</code> in your <code>.env</code> file to enable Clerk Auth.
          </p>
        </div>
      </div>
    );
  }

  return (
    <ClerkProvider publishableKey={CLERK_PUBLISHABLE_KEY} appearance={teletipsClerkAppearance}>
      <BrowserRouter>
        <Routes>
          <Route path="/sign-in/*" element={<SignInPage />} />
          <Route path="/sign-up/*" element={<SignUpPage />} />
          <Route
            path="/dashboard"
            element={
              <ProtectedRoute>
                <DashboardPlaceholder />
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
