import React from 'react';
import { SignedIn, SignedOut, RedirectToSignIn } from '@clerk/clerk-react';

/**
 * ProtectedRoute Component
 * ------------------------
 * Ensures that only authenticated Clerk users can access protected views (e.g. Dashboard).
 * Automatically redirects unauthenticated visitors to the /sign-in route.
 */
export const ProtectedRoute = ({ children }) => {
  return (
    <>
      <SignedIn>{children}</SignedIn>
      <SignedOut>
        <RedirectToSignIn />
      </SignedOut>
    </>
  );
};

export default ProtectedRoute;
