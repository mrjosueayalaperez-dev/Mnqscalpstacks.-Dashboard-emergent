import React from "react";
import "@/App.css";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import LandingPage from "@/components/LandingPage";
import PerformancePage from "@/components/PerformancePage";
import AdminPanel from "@/components/AdminPanel";
import OperatorCockpit from "@/components/operator/OperatorCockpit";
import Dashboard from "@/pages/Dashboard";

export default function AppRouter() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/performance" element={<PerformancePage />} />
        <Route path="/admin" element={<AdminPanel />} />
        <Route path="/operator" element={<OperatorCockpit />} />
      </Routes>
    </BrowserRouter>
  );
}
