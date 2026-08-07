import React from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";

/** Gate: requires a logged-in user; `adminOnly` additionally requires role=admin. */
export default function ProtectedRoute({ children, adminOnly = false }) {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading || user === null) {
    return (
      <div className="min-h-screen bg-[#0A0A0A] flex items-center justify-center" data-testid="auth-loading">
        <div className="w-8 h-8 border-2 border-[#007AFF] border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }
  if (!user) {
    return <Navigate to="/auth" replace state={{ from: location.pathname }} />;
  }
  if (adminOnly && user.role !== "admin") {
    return (
      <div className="min-h-screen bg-[#0A0A0A] flex items-center justify-center px-4" data-testid="admin-only-block">
        <div className="text-center max-w-sm">
          <h2 className="text-base font-black text-white mb-2">OPERATOR ACCESS ONLY</h2>
          <p className="text-sm text-zinc-500 mb-4">This area is restricted to the account owner.</p>
          <a href="/dashboard" className="text-xs text-[#007AFF] hover:underline">← Back to dashboard</a>
        </div>
      </div>
    );
  }
  return children;
}
