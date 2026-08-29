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
      <div className="mb-6 text-center z-10 space-y-1">
        <div className="flex items-center justify-center space-x-2 rtl:space-x-reverse">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-indigo-600 to-cyan-500 flex items-center justify-center text-white font-black text-xl shadow-lg shadow-indigo-500/30">
            ⚡
          </div>
          <span className="text-2xl font-black text-white tracking-tight">TeleTips <span className="text-cyan-400 text-xs px-2 py-0.5 rounded-md bg-cyan-500/10 border border-cyan-500/30">PRO</span></span>
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
