import React, { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { Toaster, toast } from "sonner";
import SignalDashboard from "@/components/SignalDashboard";
import SafetySentinel from "@/components/SafetySentinel";
import HydroPilot from "@/components/HydroPilot";
import DualGate from "@/components/DualGate";
import SimulationTemple from "@/components/SimulationTemple";
import PerformanceEngine from "@/components/PerformanceEngine";
import KnowledgeVault from "@/components/KnowledgeVault";
import ExecutionHub from "@/components/ExecutionHub";
import AutoSignalEngine from "@/components/AutoSignalEngine";
import { FreemiumGate, AdBanner } from "@/components/FreemiumGate";
import { TradingViewPanel, MarketSidebar } from "@/components/PromoModules";
import LiveTerminalChart from "@/components/LiveTerminalChart";
import { Header } from "@/components/dashboard/Header";
import ExecutionPanel from "@/components/dashboard/ExecutionPanel";
import { MNQTracker } from "@/components/dashboard/MNQTracker";
import { Checklist } from "@/components/dashboard/Checklist";
import { AIAnalysis } from "@/components/dashboard/AIAnalysis";
import { PositionCalculator } from "@/components/dashboard/PositionCalculator";
import { AlertsPanel } from "@/components/dashboard/AlertsPanel";
import { MoreTools, BottomNav, RiskDisclaimer } from "@/components/dashboard/MobileShell";
import { ReferralCard } from "@/components/ReferralCard";
import { CopilotChat } from "@/components/CopilotChat";
import OrderFlowChart from "@/components/dashboard/OrderFlowChart";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const TOAST_OPTIONS = {
  style: {
    background: "#121212",
    border: "1px solid rgba(255,255,255,0.1)",
    color: "#fff",
  },
};

export default function Dashboard() {
  const [mnqData, setMnqData] = useState(null);
  const [checklist, setChecklist] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [aiResult, setAiResult] = useState(null);
  const [lastUpdate, setLastUpdate] = useState(null);
  const [loading, setLoading] = useState({ mnq: false, ai: false });
  const [safeMode, setSafeMode] = useState(true);
  const [chartMode, setChartMode] = useState("standard");

  // Fetch functions
  const fetchMNQData = useCallback(async () => {
    setLoading((l) => ({ ...l, mnq: true }));
    try {
      const res = await axios.get(`${API}/futures/mnq`);
      setMnqData(res.data);
    } catch (e) {
      console.error("Error fetching MNQ:", e);
    }
    setLoading((l) => ({ ...l, mnq: false }));
  }, []);

  const fetchChecklist = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/checklist`);
      setChecklist(res.data);
    } catch (e) {
      console.error("Error fetching checklist:", e);
    }
  }, []);

  const fetchAlerts = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/alerts`);
      setAlerts(res.data);
    } catch (e) {
      console.error("Error fetching alerts:", e);
    }
  }, []);

  const seedData = useCallback(async () => {
    try {
      await axios.post(`${API}/seed`);
      await fetchChecklist();
      toast.success("Data initialized!");
    } catch (e) {
      console.error("Error seeding:", e);
    }
  }, [fetchChecklist]);

  // Initial load + 30s auto-refresh
  useEffect(() => {
    const init = async () => {
      await Promise.all([fetchMNQData(), fetchChecklist(), fetchAlerts()]);
      setLastUpdate(new Date().toLocaleTimeString());
    };
    init();

    const interval = setInterval(() => {
      fetchMNQData();
      setLastUpdate(new Date().toLocaleTimeString());
    }, 30000);

    return () => clearInterval(interval);
  }, [fetchMNQData, fetchChecklist, fetchAlerts]);

  // Seed defaults when fresh database
  useEffect(() => {
    if (checklist.length === 0) {
      seedData();
    }
  }, [checklist.length, seedData]);

  // Action handlers
  const handleRefreshAll = async () => {
    await Promise.all([fetchMNQData(), fetchChecklist(), fetchAlerts()]);
    setLastUpdate(new Date().toLocaleTimeString());
    toast.success("Data refreshed!");
  };

  const handleToggleChecklist = async (id, completed) => {
    try {
      await axios.patch(`${API}/checklist/${id}?completed=${completed}`);
      setChecklist((items) =>
        items.map((item) => (item.id === id ? { ...item, completed } : item))
      );
    } catch (e) {
      console.error("Error toggling:", e);
    }
  };

  const handleResetChecklist = async () => {
    try {
      await axios.post(`${API}/checklist/reset`);
      await fetchChecklist();
      toast.success("Checklist reset");
    } catch (e) {
      console.error("Error resetting:", e);
    }
  };

  const handleAddChecklist = async (item) => {
    try {
      await axios.post(`${API}/checklist`, item);
      await fetchChecklist();
    } catch (e) {
      console.error("Error adding checklist:", e);
    }
  };

  const handleAddAlert = async (alert) => {
    try {
      await axios.post(`${API}/alerts`, alert);
      await fetchAlerts();
      toast.success(`Alert set for ${alert.symbol}`);
    } catch (e) {
      console.error("Error adding alert:", e);
      toast.error("Failed to add alert");
    }
  };

  const handleDeleteAlert = async (id) => {
    try {
      await axios.delete(`${API}/alerts/${id}`);
      await fetchAlerts();
    } catch (e) {
      console.error("Error deleting alert:", e);
    }
  };

  const handleAIAnalyze = async (symbol, type) => {
    setLoading((l) => ({ ...l, ai: true }));
    setAiResult(null);
    try {
      const res = await axios.post(`${API}/ai/analyze`, { symbol, analysis_type: type });
      setAiResult(res.data);
    } catch (e) {
      console.error("Error analyzing:", e);
      toast.error("AI analysis failed");
    }
    setLoading((l) => ({ ...l, ai: false }));
  };

  return (
    <div className="min-h-screen bg-[#0A0A0A]" data-testid="trading-app">
      <Toaster
        position="bottom-center"
        toastOptions={TOAST_OPTIONS}
      />
      <Header onRefresh={handleRefreshAll} lastUpdate={lastUpdate} />

      <main className="p-3 md:p-4">
        <div className="grid grid-cols-1 md:grid-cols-4 lg:grid-cols-12 gap-3 md:gap-4">
          {/* ROW -1: MOBILE-FIRST EXECUTION STRIP — live price + one-thumb trading + signal card */}
          <div id="exec-top" className="col-span-1 md:col-span-4 lg:col-span-12 grid grid-cols-1 md:grid-cols-4 lg:grid-cols-12 gap-3 md:gap-4">
            <ExecutionPanel
              checklistDone={checklist.filter((i) => i.completed).length}
              checklistTotal={checklist.length}
              chartMode={chartMode}
              onChartMode={setChartMode}
            />
            <RiskDisclaimer />
          </div>

          {/* ROW 0: MAIN CHART — Standard (TradingView) or order-flow view via blue-circle switcher */}
          <div id="chart-section" className="col-span-1 md:col-span-4 lg:col-span-12 grid grid-cols-1 md:grid-cols-4 lg:grid-cols-12 gap-3 md:gap-4">
            {chartMode === "standard" ? <LiveTerminalChart /> : <OrderFlowChart mode={chartMode} />}
          </div>

          {/* ROW 1: SIGNAL ENGINE — prominent stats + live feed */}
          <SignalDashboard />

          {/* AI COPILOT — streaming GPT chat with live desk context */}
          <CopilotChat />

          {/* ROW 2: DAILY CHECKLIST (prominent) + SUBSCRIPTION PLANS */}
          <Checklist
            items={checklist}
            onToggle={handleToggleChecklist}
            onReset={handleResetChecklist}
            onAdd={handleAddChecklist}
          />
          <FreemiumGate />

          {/* SHARE & EARN — referral link strip */}
          <ReferralCard />

          {/* Plans anchor for bottom nav */}
          <div id="plans-section" className="col-span-1 md:col-span-4 lg:col-span-12 h-0" />

          {/* MORE TOOLS — secondary panels collapsed for a clean home screen */}
          <MoreTools>
            <MNQTracker data={mnqData} loading={loading.mnq} />
            <DualGate safeMode={safeMode} onToggleSafe={setSafeMode} />
            <SimulationTemple />
            <MarketSidebar mnqData={mnqData} />
            <ExecutionHub mnqPrice={mnqData?.close || mnqData?.price} safeMode={safeMode} />
            <AutoSignalEngine mnqData={mnqData} />
            <HydroPilot />
            <PerformanceEngine />
            <AlertsPanel alerts={alerts} onAdd={handleAddAlert} onDelete={handleDeleteAlert} />
            <PositionCalculator />
            <TradingViewPanel />
            <SafetySentinel />
            <AIAnalysis onAnalyze={handleAIAnalyze} loading={loading.ai} result={aiResult} />
            <KnowledgeVault />
            <RiskDisclaimer />
          </MoreTools>

          <RiskDisclaimer />

          {/* Ad Placements (Free tier) */}
          <AdBanner position="bottom" />
        </div>
      </main>

      {/* Mobile bottom navigation (replaces floating wallet FAB) */}
      <BottomNav />
      <div className="h-12 md:hidden" />
    </div>
  );
}
