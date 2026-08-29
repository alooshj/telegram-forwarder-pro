import React from 'react';
import { useAuth } from '@clerk/clerk-react';
import { Navigate } from 'react-router-dom';

export function LoadingSpinner() {
  return (
    <div className="min-h-screen bg-slate-950 text-white flex items-center justify-center p-6">
      <div className="flex items-center space-x-3 rtl:space-x-reverse">
        <div className="w-8 h-8 rounded-full border-2 border-cyan-500 border-t-transparent animate-spin"></div>
        <span className="text-sm font-semibold text-slate-300">جارٍ التحقق من الجلسة...</span>
      </div>
    </div>
  );
}

/**
 * ProtectedRoute Component
 * ------------------------
 * Ensures that only authenticated Clerk users can access protected views.
 * Uses useAuth() to check isLoaded and isSignedIn to prevent infinite redirect loops.
 */
export const ProtectedRoute = ({ children }) => {
  const { isLoaded, isSignedIn } = useAuth();

  if (!isLoaded) {
    return <LoadingSpinner />;
  }

  if (!isSignedIn) {
    return <Navigate to="/sign-in" replace />;
  }

  return children;
};

export default ProtectedRoute;
