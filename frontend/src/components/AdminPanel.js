import React, { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast, Toaster } from "sonner";
import {
  Users, DollarSign, Zap, BarChart3, Crown, Star, Trash2,
  ChevronUp, ChevronDown, Shield, Activity, TrendingUp, RefreshCw,
} from "lucide-react";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const AdminPanel = () => {
  const [overview, setOverview] = useState(null);
  const [subscribers, setSubscribers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showSubs, setShowSubs] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      const [ovRes, subRes] = await Promise.all([
        axios.get(`${API}/admin/overview`),
        axios.get(`${API}/admin/subscribers?limit=20`),
      ]);
      setOverview(ovRes.data);
      setSubscribers(subRes.data);
    } catch (e) { console.error(e); }
    setLoading(false);
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  const handleTierChange = async (subId, newTier) => {
    try {
      await axios.patch(`${API}/admin/subscribers/${subId}/tier`, null, { params: { tier: newTier } });
      toast.success(`Tier updated to ${newTier}`);
      await fetchData();
    } catch (e) { toast.error("Failed"); }
  };

  const handleDelete = async (subId) => {
    if (!window.confirm("Delete this subscriber?")) return;
    try {
      await axios.delete(`${API}/admin/subscribers/${subId}`);
      toast.success("Subscriber removed");
      await fetchData();
    } catch (e) { toast.error("Failed"); }
  };

  if (loading) return (
    <div className="min-h-screen bg-[#0A0A0A] flex items-center justify-center">
      <RefreshCw className="w-8 h-8 text-[#007AFF] animate-spin" />
    </div>
  );

  const ov = overview || {};
  const subs = ov.subscribers || {};
  const rev = ov.revenue || {};

  return (
    <div className="min-h-screen bg-[#0A0A0A]" data-testid="admin-panel">
      <Toaster position="top-right" toastOptions={{ style: { background: "#121212", border: "1px solid rgba(255,255,255,0.1)", color: "#fff" } }} />

      {/* Header */}
      <header className="h-14 border-b border-white/10 bg-[#0A0A0A]/90 backdrop-blur-xl flex items-center justify-between px-4 md:px-6 sticky top-0 z-50">
        <div className="flex items-center gap-3">
          <Shield className="w-5 h-5 text-[#FF3B30]" />
          <h1 className="text-base md:text-lg font-black tracking-tight text-white">ADMIN PANEL</h1>
        </div>
        <div className="flex items-center gap-3">
          <a href="/" className="text-xs text-zinc-500 hover:text-white transition-colors">Landing</a>
          <a href="/dashboard" className="text-xs text-zinc-500 hover:text-white transition-colors">Dashboard</a>
          <button onClick={fetchData} className="p-2 hover:bg-white/5 rounded"><RefreshCw className="w-4 h-4 text-zinc-400" /></button>
        </div>
      </header>

      <main className="p-4 md:p-6 max-w-6xl mx-auto space-y-6">
        {/* KPI Cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 md:gap-4">
          {[
            { label: "Subscribers", value: subs.total || 0, icon: Users, color: "text-[#007AFF]" },
            { label: "MRR", value: `$${rev.mrr || 0}`, icon: DollarSign, color: "text-[#34C759]" },
            { label: "Total Signals", value: ov.signals?.total || 0, icon: Zap, color: "text-[#FFCC00]" },
            { label: "Total Trades", value: ov.trades?.total || 0, icon: BarChart3, color: "text-white" },
          ].map((kpi, i) => (
            <div key={i} className="bg-[#121212] border border-white/10 rounded-sm p-4" data-testid={`admin-kpi-${kpi.label.toLowerCase().replace(/\s/g, "-")}`}>
              <kpi.icon className={`w-5 h-5 mb-2 ${kpi.color}`} />
              <span className="text-[0.6rem] font-bold uppercase tracking-[0.15em] text-zinc-500 block">{kpi.label}</span>
              <span className={`text-2xl md:text-3xl font-mono font-bold ${kpi.color}`}>{kpi.value}</span>
            </div>
          ))}
        </div>

        {/* Tier Breakdown */}
        <div className="bg-[#121212] border border-white/10 rounded-sm p-4">
          <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-500 mb-3">Subscriber Tiers</h3>
          <div className="grid grid-cols-3 gap-3">
            <div className="text-center p-3 bg-white/5 rounded-sm">
              <Zap className="w-4 h-4 text-[#007AFF] mx-auto mb-1" />
              <span className="text-xl font-mono font-bold text-white">{subs.free || 0}</span>
              <span className="block text-[0.6rem] text-zinc-500">Free</span>
            </div>
            <div className="text-center p-3 bg-[#FFCC00]/5 rounded-sm border border-[#FFCC00]/20">
              <Star className="w-4 h-4 text-[#FFCC00] mx-auto mb-1" />
              <span className="text-xl font-mono font-bold text-[#FFCC00]">{subs.pro || 0}</span>
              <span className="block text-[0.6rem] text-zinc-500">Pro ($49)</span>
            </div>
            <div className="text-center p-3 bg-[#34C759]/5 rounded-sm border border-[#34C759]/20">
              <Crown className="w-4 h-4 text-[#34C759] mx-auto mb-1" />
              <span className="text-xl font-mono font-bold text-[#34C759]">{subs.elite || 0}</span>
              <span className="block text-[0.6rem] text-zinc-500">Elite ($149)</span>
            </div>
          </div>
        </div>

        {/* Subscriber List */}
        <div className="bg-[#121212] border border-white/10 rounded-sm">
          <button onClick={() => setShowSubs(!showSubs)} className="w-full p-4 flex items-center justify-between hover:bg-white/5 transition-colors" data-testid="admin-toggle-subs">
            <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-500 flex items-center gap-2">
              <Users className="w-4 h-4" /> Manage Subscribers ({subscribers.length})
            </h3>
            {showSubs ? <ChevronUp className="w-4 h-4 text-zinc-500" /> : <ChevronDown className="w-4 h-4 text-zinc-500" />}
          </button>
          {showSubs && (
            <div className="border-t border-white/5 divide-y divide-white/5 max-h-[400px] overflow-y-auto">
              {subscribers.map((sub) => (
                <div key={sub.id} className="px-4 py-3 flex items-center justify-between hover:bg-white/[0.02]" data-testid={`admin-sub-${sub.id}`}>
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-semibold text-white truncate">{sub.name || sub.email}</span>
                      <span className={`text-[0.55rem] px-1.5 py-0.5 rounded font-bold ${
                        sub.tier === "elite" ? "bg-[#34C759]/20 text-[#34C759]" :
                        sub.tier === "pro" ? "bg-[#FFCC00]/20 text-[#FFCC00]" :
                        "bg-white/10 text-zinc-400"
                      }`}>{sub.tier?.toUpperCase()}</span>
                    </div>
                    <span className="text-xs text-zinc-600">{sub.email} | Ref: {sub.referral_code || "N/A"} ({sub.referral_count || 0} referrals)</span>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <select value={sub.tier} onChange={(e) => handleTierChange(sub.id, e.target.value)}
                      className="text-xs bg-white/5 border border-white/10 rounded-sm px-2 py-1 text-white">
                      <option value="free">Free</option>
                      <option value="pro">Pro</option>
                      <option value="elite">Elite</option>
                    </select>
                    <button onClick={() => handleDelete(sub.id)} className="p-1 text-zinc-600 hover:text-[#FF3B30] transition-colors">
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Recent Activity */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="bg-[#121212] border border-white/10 rounded-sm p-4">
            <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-500 mb-3 flex items-center gap-2">
              <Activity className="w-4 h-4" /> Recent Signups
            </h3>
            <div className="space-y-2">
              {(ov.recent_subscribers || []).map((s, i) => (
                <div key={i} className="flex justify-between text-xs">
                  <span className="text-zinc-300">{s.name || s.email?.slice(0, 15)}</span>
                  <span className={`font-bold ${s.tier === "pro" ? "text-[#FFCC00]" : s.tier === "elite" ? "text-[#34C759]" : "text-zinc-500"}`}>{s.tier}</span>
                </div>
              ))}
            </div>
          </div>
          <div className="bg-[#121212] border border-white/10 rounded-sm p-4">
            <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-500 mb-3 flex items-center gap-2">
              <TrendingUp className="w-4 h-4" /> Recent Signals
            </h3>
            <div className="space-y-2">
              {(ov.recent_signals || []).slice(0, 5).map((s, i) => (
                <div key={i} className="flex justify-between text-xs">
                  <span className={`font-bold ${s.side === "long" ? "text-[#34C759]" : "text-[#FF3B30]"}`}>
                    {s.side?.toUpperCase()} ${s.entry_price?.toFixed(2)}
                  </span>
                  <span className="text-zinc-500">{s.status}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </main>
    </div>
  );
};

export default AdminPanel;
