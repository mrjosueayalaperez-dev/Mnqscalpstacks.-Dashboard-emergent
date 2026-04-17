import React, { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  Activity,
  Zap,
  Shield,
  ShieldOff,
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  RefreshCw,
  Copy,
  CheckCircle,
  XCircle,
  Clock,
  Radio,
  Code,
  ChevronDown,
  ChevronUp,
} from "lucide-react";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const formatPrice = (p) =>
  typeof p === "number"
    ? p.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })
    : "0.00";

// ===================== Signal Feed =====================
const SignalFeed = ({ signals, onUpdateSignal }) => {
  if (!signals.length)
    return (
      <div className="text-center text-zinc-500 py-10">
        <Radio className="w-8 h-8 mx-auto mb-2 opacity-40" />
        <p className="text-sm">No signals yet — generate a test or connect TradingView</p>
      </div>
    );

  return (
    <div className="space-y-2 max-h-[400px] overflow-y-auto pr-1">
      {signals.map((sig) => {
        const isLong = sig.side === "long";
        return (
          <div
            key={sig.id}
            className={`p-3 rounded-sm border transition-colors ${
              sig.status === "active"
                ? isLong
                  ? "border-[#34C759]/40 bg-[#34C759]/5"
                  : "border-[#FF3B30]/40 bg-[#FF3B30]/5"
                : "border-white/5 bg-white/[0.02] opacity-60"
            }`}
            data-testid={`signal-${sig.id}`}
          >
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                {isLong ? (
                  <TrendingUp className="w-5 h-5 text-[#34C759]" />
                ) : (
                  <TrendingDown className="w-5 h-5 text-[#FF3B30]" />
                )}
                <span className={`font-bold text-sm uppercase ${isLong ? "text-[#34C759]" : "text-[#FF3B30]"}`}>
                  {sig.side} {sig.symbol}
                </span>
                <span className="text-xs text-zinc-500 font-mono">
                  Score: {sig.confluence_score}/3
                </span>
              </div>
              <div className="flex items-center gap-1">
                {sig.source === "test" && (
                  <span className="text-[0.6rem] px-1.5 py-0.5 bg-[#FFCC00]/20 text-[#FFCC00] rounded">TEST</span>
                )}
                {sig.source === "webhook" && (
                  <span className="text-[0.6rem] px-1.5 py-0.5 bg-[#007AFF]/20 text-[#007AFF] rounded">LIVE</span>
                )}
                <span className={`text-[0.6rem] px-1.5 py-0.5 rounded ${
                  sig.status === "active" ? "bg-[#34C759]/20 text-[#34C759]" :
                  sig.outcome === "win" ? "bg-[#34C759]/20 text-[#34C759]" :
                  sig.outcome === "loss" ? "bg-[#FF3B30]/20 text-[#FF3B30]" :
                  "bg-zinc-700 text-zinc-400"
                }`}>
                  {sig.status.toUpperCase()}
                </span>
              </div>
            </div>

            <div className="grid grid-cols-4 gap-2 text-xs font-mono">
              <div>
                <span className="text-zinc-500 block">Entry</span>
                <span className="text-white">${formatPrice(sig.entry_price)}</span>
              </div>
              <div>
                <span className="text-zinc-500 block">Stop</span>
                <span className="text-[#FF3B30]">${formatPrice(sig.stop_loss)}</span>
              </div>
              <div>
                <span className="text-zinc-500 block">TP1</span>
                <span className="text-[#34C759]">${formatPrice(sig.tp1)}</span>
              </div>
              <div>
                <span className="text-zinc-500 block">TP2</span>
                <span className="text-[#34C759] glow-green">${formatPrice(sig.tp2)}</span>
              </div>
            </div>

            {/* Components */}
            {sig.components && Object.keys(sig.components).length > 0 && (
              <div className="flex gap-1 mt-2 flex-wrap">
                {Object.entries(sig.components).map(([key, val]) => (
                  <span
                    key={key}
                    className={`text-[0.6rem] px-1.5 py-0.5 rounded ${
                      val ? "bg-[#34C759]/10 text-[#34C759]" : "bg-white/5 text-zinc-600"
                    }`}
                  >
                    {key.replace(/_/g, " ")}
                  </span>
                ))}
              </div>
            )}

            {/* Quick resolve buttons for active signals */}
            {sig.status === "active" && (
              <div className="flex gap-2 mt-2">
                <button
                  onClick={() => onUpdateSignal(sig.id, "hit_tp1", isLong ? 10 : 10)}
                  className="text-[0.65rem] px-2 py-0.5 bg-[#34C759]/10 text-[#34C759] rounded hover:bg-[#34C759]/20 transition-colors"
                  data-testid={`signal-tp1-${sig.id}`}
                >
                  Hit TP1
                </button>
                <button
                  onClick={() => onUpdateSignal(sig.id, "hit_tp2", isLong ? 20 : 20)}
                  className="text-[0.65rem] px-2 py-0.5 bg-[#34C759]/10 text-[#34C759] rounded hover:bg-[#34C759]/20 transition-colors"
                  data-testid={`signal-tp2-${sig.id}`}
                >
                  Hit TP2
                </button>
                <button
                  onClick={() => onUpdateSignal(sig.id, "stopped", -8)}
                  className="text-[0.65rem] px-2 py-0.5 bg-[#FF3B30]/10 text-[#FF3B30] rounded hover:bg-[#FF3B30]/20 transition-colors"
                  data-testid={`signal-stopped-${sig.id}`}
                >
                  Stopped
                </button>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
};

// ===================== System Health =====================
const SystemHealth = ({ health, killSwitch, onToggleKill }) => {
  const statusColors = {
    healthy: "text-[#34C759]",
    warning: "text-[#FFCC00]",
    degraded: "text-[#FF3B30]",
  };

  return (
    <div className="space-y-3">
      {/* Status bar */}
      <div className="flex items-center justify-between p-3 bg-white/5 rounded-sm border border-white/10">
        <div className="flex items-center gap-2">
          <div className={`w-2 h-2 rounded-full ${
            health.status === "healthy" ? "bg-[#34C759] animate-pulse" :
            health.status === "warning" ? "bg-[#FFCC00]" : "bg-[#FF3B30]"
          }`} />
          <span className={`text-sm font-bold uppercase ${statusColors[health.status] || "text-zinc-400"}`}>
            {health.status}
          </span>
        </div>
        <button
          onClick={() => onToggleKill(!killSwitch)}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-sm text-xs font-bold uppercase transition-all ${
            killSwitch
              ? "bg-[#FF3B30] text-white hover:bg-[#FF3B30]/80"
              : "bg-white/10 text-zinc-400 hover:bg-[#FF3B30]/20 hover:text-[#FF3B30]"
          }`}
          data-testid="kill-switch-btn"
        >
          {killSwitch ? <ShieldOff className="w-3.5 h-3.5" /> : <Shield className="w-3.5 h-3.5" />}
          {killSwitch ? "KILL ACTIVE" : "Kill Switch"}
        </button>
      </div>

      {/* Metrics grid */}
      <div className="grid grid-cols-2 gap-2">
        <div className="stat-box">
          <span className="stat-label">Signals Processed</span>
          <span className="stat-value text-lg">{health.total_signals_processed || 0}</span>
        </div>
        <div className="stat-box">
          <span className="stat-label">Error Rate</span>
          <span className={`stat-value text-lg ${
            health.error_rate_pct > 3 ? "text-[#FF3B30]" : "text-[#34C759]"
          }`}>
            {health.error_rate_pct || 0}%
          </span>
        </div>
        <div className="stat-box">
          <span className="stat-label">Discord</span>
          <span className={`text-sm font-bold ${
            health.discord_configured ? "text-[#34C759]" : "text-[#FFCC00]"
          }`}>
            {health.discord_configured ? "Connected" : "Not Set"}
          </span>
        </div>
        <div className="stat-box">
          <span className="stat-label">Last Signal</span>
          <span className="text-xs font-mono text-zinc-400">
            {health.last_signal_time
              ? new Date(health.last_signal_time).toLocaleTimeString()
              : "None"}
          </span>
        </div>
      </div>
    </div>
  );
};

// ===================== Pine Script Panel =====================
const PineScriptPanel = ({ pineData }) => {
  const [expanded, setExpanded] = useState(false);
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    if (pineData?.pine_script) {
      navigator.clipboard.writeText(pineData.pine_script);
      setCopied(true);
      toast.success("Pine Script copied to clipboard!");
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div>
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center justify-between w-full p-2 bg-white/5 rounded-sm hover:bg-white/10 transition-colors"
        data-testid="pinescript-toggle"
      >
        <span className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-zinc-400">
          <Code className="w-4 h-4 text-[#007AFF]" />
          Pine Script + Webhook Setup
        </span>
        {expanded ? <ChevronUp className="w-4 h-4 text-zinc-500" /> : <ChevronDown className="w-4 h-4 text-zinc-500" />}
      </button>

      {expanded && pineData && (
        <div className="mt-2 space-y-3">
          {/* Pine Script */}
          <div className="relative">
            <button
              onClick={handleCopy}
              className="absolute top-2 right-2 p-1.5 bg-white/10 rounded hover:bg-white/20 transition-colors z-10"
              data-testid="copy-pinescript-btn"
            >
              {copied ? <CheckCircle className="w-3.5 h-3.5 text-[#34C759]" /> : <Copy className="w-3.5 h-3.5" />}
            </button>
            <pre className="bg-[#0A0A0A] border border-white/10 rounded-sm p-3 text-xs font-mono text-zinc-300 overflow-x-auto max-h-[250px] overflow-y-auto leading-relaxed">
              {pineData.pine_script}
            </pre>
          </div>

          {/* Webhook instructions */}
          <div className="bg-[#007AFF]/5 border border-[#007AFF]/20 rounded-sm p-3">
            <pre className="text-xs text-zinc-300 whitespace-pre-wrap leading-relaxed">
              {pineData.webhook_instructions}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
};

// ===================== Main Signal Dashboard =====================
const SignalDashboard = () => {
  const [signals, setSignals] = useState([]);
  const [stats, setStats] = useState({});
  const [health, setHealth] = useState({});
  const [killSwitch, setKillSwitch] = useState(false);
  const [pineData, setPineData] = useState(null);
  const [loading, setLoading] = useState(false);

  const fetchAll = useCallback(async () => {
    try {
      const [sigRes, statsRes, healthRes, killRes, pineRes] = await Promise.all([
        axios.get(`${API}/signals?limit=20`),
        axios.get(`${API}/signals/stats`),
        axios.get(`${API}/signals/health`),
        axios.get(`${API}/signals/kill-switch`),
        axios.get(`${API}/signals/pinescript`),
      ]);
      setSignals(sigRes.data);
      setStats(statsRes.data);
      setHealth(healthRes.data);
      setKillSwitch(killRes.data.kill_switch);
      setPineData(pineRes.data);
    } catch (e) {
      console.error("Signal fetch error:", e);
    }
  }, []);

  useEffect(() => {
    fetchAll();
    const interval = setInterval(fetchAll, 10000);
    return () => clearInterval(interval);
  }, [fetchAll]);

  const handleTestSignal = async () => {
    setLoading(true);
    try {
      const res = await axios.post(`${API}/signals/test`);
      if (res.data.status === "generated") {
        toast.success("Test signal generated!");
        await fetchAll();
      } else {
        toast.error(res.data.reason || "Signal blocked");
      }
    } catch (e) {
      toast.error("Failed to generate test signal");
    }
    setLoading(false);
  };

  const handleToggleKill = async (enabled) => {
    try {
      await axios.post(`${API}/signals/kill-switch`, {
        enabled,
        reason: enabled ? "Manual kill switch" : "Re-enabled",
      });
      setKillSwitch(enabled);
      toast(enabled ? "Kill switch ACTIVATED" : "Kill switch disabled", {
        className: enabled ? "alert-toast-bearish" : "alert-toast-bullish",
      });
      await fetchAll();
    } catch (e) {
      toast.error("Failed to toggle kill switch");
    }
  };

  const handleUpdateSignal = async (signalId, status, pnlPoints) => {
    try {
      await axios.patch(`${API}/signals/${signalId}?status=${status}&pnl_points=${pnlPoints}`);
      toast.success(`Signal marked as ${status}`);
      await fetchAll();
    } catch (e) {
      toast.error("Failed to update signal");
    }
  };

  return (
    <div className="col-span-1 md:col-span-4 lg:col-span-12 grid grid-cols-1 lg:grid-cols-12 gap-4" data-testid="signal-dashboard">
      {/* Left: Signal Feed */}
      <div className="widget-panel lg:col-span-7">
        <div className="widget-header">
          <h3 className="flex items-center gap-2">
            <Zap className="w-4 h-4 text-[#FFCC00]" />
            SIGNAL ENGINE
          </h3>
          <div className="flex items-center gap-2">
            <button
              onClick={handleTestSignal}
              disabled={loading || killSwitch}
              className="flex items-center gap-1 px-2 py-1 text-xs bg-[#FFCC00]/20 text-[#FFCC00] rounded-sm hover:bg-[#FFCC00]/30 transition-colors disabled:opacity-30"
              data-testid="test-signal-btn"
            >
              {loading ? <RefreshCw className="w-3 h-3 animate-spin" /> : <Zap className="w-3 h-3" />}
              Test Signal
            </button>
            <button
              onClick={fetchAll}
              className="p-1 hover:bg-white/10 rounded transition-colors"
              data-testid="refresh-signals-btn"
            >
              <RefreshCw className="w-3.5 h-3.5 text-zinc-400" />
            </button>
          </div>
        </div>
        <div className="widget-content">
          {/* Stats row */}
          <div className="grid grid-cols-2 md:grid-cols-5 gap-2 mb-4">
            <div className="stat-box">
              <span className="stat-label">Signals</span>
              <span className="stat-value text-lg">{stats.total_signals || 0}</span>
            </div>
            <div className="stat-box">
              <span className="stat-label">Win Rate</span>
              <span className={`stat-value text-lg ${
                (stats.win_rate || 0) >= 50 ? "text-[#34C759]" : "text-[#FF3B30]"
              }`}>
                {stats.win_rate || 0}%
              </span>
            </div>
            <div className="stat-box">
              <span className="stat-label">P&L (pts)</span>
              <span className={`stat-value text-lg ${
                (stats.total_pnl_points || 0) >= 0 ? "text-[#34C759]" : "text-[#FF3B30]"
              }`}>
                {(stats.total_pnl_points || 0) >= 0 ? "+" : ""}{stats.total_pnl_points || 0}
              </span>
            </div>
            <div className="stat-box">
              <span className="stat-label">Avg R:R</span>
              <span className="stat-value text-lg">{stats.avg_rr || 0}</span>
            </div>
            <div className="stat-box">
              <span className="stat-label">Freq/Day</span>
              <span className="stat-value text-lg">{stats.signal_frequency_per_day || 0}</span>
            </div>
          </div>

          <SignalFeed signals={signals} onUpdateSignal={handleUpdateSignal} />
        </div>
      </div>

      {/* Right: Health + Pine Script */}
      <div className="lg:col-span-5 flex flex-col gap-4">
        <div className="widget-panel">
          <div className="widget-header">
            <h3 className="flex items-center gap-2">
              <Activity className="w-4 h-4 text-[#007AFF]" />
              SYSTEM HEALTH
            </h3>
          </div>
          <div className="widget-content">
            <SystemHealth health={health} killSwitch={killSwitch} onToggleKill={handleToggleKill} />
          </div>
        </div>

        <div className="widget-panel">
          <div className="widget-header">
            <h3 className="flex items-center gap-2">
              <Code className="w-4 h-4 text-[#007AFF]" />
              TRADINGVIEW SETUP
            </h3>
          </div>
          <div className="widget-content">
            <PineScriptPanel pineData={pineData} />
          </div>
        </div>
      </div>
    </div>
  );
};

export default SignalDashboard;
