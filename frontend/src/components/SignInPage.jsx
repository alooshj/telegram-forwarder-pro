import React from 'react';
import { SignIn, useAuth } from '@clerk/clerk-react';
import { Navigate } from 'react-router-dom';
import { LoadingSpinner } from './ProtectedRoute';

export const SignInPage = () => {
  const { isLoaded, isSignedIn } = useAuth();

  if (!isLoaded) {
    return <LoadingSpinner />;
  }

  if (isSignedIn) {
    return <Navigate to="/dashboard" replace />;
  }

  return (
    <div className="min-h-screen bg-slate-950 flex flex-col justify-center items-center p-4 relative overflow-hidden">
      {/* Background Neon Glows */}
      <div className="absolute top-1/4 -left-20 w-80 h-80 bg-indigo-600/15 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute bottom-1/4 -right-20 w-80 h-80 bg-cyan-500/15 rounded-full blur-3xl pointer-events-none" />

      {/* Brand Header */}
      <div className="mb-6 text-center z-10 space-y-2">
        <div className="flex items-center justify-center">
          <div className="p-2.5 bg-slate-900/90 rounded-2xl border border-cyan-500/30 shadow-xl shadow-cyan-950/50">
            <img src="/logo.png" alt="TeleTips Pro" className="h-10 sm:h-12 w-auto object-contain filter drop-shadow-[0_0_12px_rgba(6,182,212,0.4)]" />
          </div>
        </div>
        <p className="text-xs text-slate-400">لوحة التحكم السحابية لتوجيه قنوات تليجرام الذكية</p>
      </div>

      {/* Clerk SignIn Component */}
      <div className="z-10 w-full max-w-md">
        <SignIn routing="path" path="/sign-in" signUpUrl="/sign-up" forceRedirectUrl="/dashboard" fallbackRedirectUrl="/dashboard" />
      </div>
    </div>
  );
};

export default SignInPage;
