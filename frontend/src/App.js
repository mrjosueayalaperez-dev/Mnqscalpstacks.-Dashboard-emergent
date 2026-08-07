import React from "react";
import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate, useLocation } from "react-router-dom";
import LandingPage from "@/components/LandingPage";
import PerformancePage from "@/components/PerformancePage";
import AdminPanel from "@/components/AdminPanel";
import OperatorCockpit from "@/components/operator/OperatorCockpit";
import Dashboard from "@/pages/Dashboard";
import AuthPage from "@/pages/AuthPage";
import AuthCallback from "@/components/AuthCallback";
import ProtectedRoute from "@/components/ProtectedRoute";
import { AuthProvider } from "@/context/AuthContext";

function AppRoutes() {
  const location = useLocation(); // read hash from here, not window.location.hash (not reactive)
  // Google OAuth returns with #session_id= — process it before any route/auth check
  if (location.hash?.includes("session_id=")) {
    return <AuthCallback />;
  }
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/auth" element={<AuthPage />} />
      <Route path="/performance" element={<PerformancePage />} />
      <Route path="/dashboard" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
      <Route path="/operator" element={<ProtectedRoute adminOnly><OperatorCockpit /></ProtectedRoute>} />
      <Route path="/admin" element={<ProtectedRoute adminOnly><AdminPanel /></ProtectedRoute>} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default function AppRouter() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </BrowserRouter>
  );
}
