import { fmtPct, hasNum } from "@/lib/fmt";
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
  Minus,
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

// ===================== Receiver / Setup Panel =====================
const etTime = (iso) => {
  try { return new Date(iso).toLocaleTimeString("en-US", { timeZone: "America/New_York", hour: "2-digit", minute: "2-digit", second: "2-digit" }) + " ET"; }
  catch { return "—"; }
};

const ReceiverPanel = ({ rs, onTest, testing }) => {
  const [copied, setCopied] = useState("");
  if (!rs) return null;
  const copy = (label, text) => {
    navigator.clipboard.writeText(text);
    setCopied(label);
    toast.success(`${label} copied`);
    setTimeout(() => setCopied(""), 1500);
  };
  const publicWebhookUrl = `${BACKEND_URL}/api/signals/tradingview`;
  const eng = rs.engine || {};
  return (
    <div className="mb-3 p-3 bg-white/[0.03] border border-white/10 rounded-sm space-y-2" data-testid="receiver-panel">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className={`flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[0.6rem] font-black border ${
          rs.receiver_live ? "border-[#34C759]/50 text-[#34C759] bg-[#34C759]/10" : "border-[#FF3B30]/50 text-[#FF3B30] bg-[#FF3B30]/10"
        }`} data-testid="receiver-live-badge">
          <span className={`w-1.5 h-1.5 rounded-full ${rs.receiver_live ? "bg-[#34C759] animate-pulse" : "bg-[#FF3B30]"}`} />
          {rs.receiver_live ? "RECEIVER LIVE" : "NO ALERTS RECEIVED"}
        </span>
        <div className="flex items-center gap-2">
          <button
            onClick={async () => {
              try {
                const { data } = await axios.post(`${API}/signals/session-filter`, { aggressive: !eng.aggressive });
                toast.success(`Engine mode: ${data.aggressive ? "AGGRESSIVE" : "STRICT"}`);
              } catch {
                toast.error("Admin only");
              }
            }}
            className={`px-2 py-0.5 rounded-full text-[0.6rem] font-black border transition-colors ${
              eng.aggressive
                ? "border-[#FF9500]/50 text-[#FF9500] bg-[#FF9500]/10 hover:bg-[#FF9500]/20"
                : "border-white/20 text-zinc-400 bg-white/5 hover:bg-white/10"
            }`}
            data-testid="engine-mode-toggle"
          >
            {eng.aggressive ? "MODE: AGGRESSIVE" : "MODE: STRICT"}
          </button>
          <span className={`text-[0.6rem] font-mono ${eng.session_open ? "text-[#34C759]" : "text-[#FFCC00]"}`} data-testid="session-status">
            {eng.session_open ? `SESSION OPEN · ${eng.now_et}` : `SESSION CLOSED — signals paused · ${eng.now_et}`}
          </span>
        </div>
      </div>

      {rs.never_received && (
        <p className="text-[0.65rem] text-zinc-400">No TradingView alerts have hit this server yet. Copy the webhook URL + alert message below into a TradingView alert to go live.</p>
      )}

      <div className="flex flex-wrap gap-2">
        <button onClick={() => copy("Webhook URL", publicWebhookUrl)} className="flex items-center gap-1 px-2 py-1 text-[0.6rem] font-bold bg-[#007AFF]/15 text-[#007AFF] rounded-sm hover:bg-[#007AFF]/25" data-testid="copy-webhook-url-btn">
          {copied === "Webhook URL" ? <CheckCircle className="w-3 h-3" /> : <Copy className="w-3 h-3" />} Webhook URL
        </button>
        <button onClick={() => copy("Alert message", rs.alert_template)} className="flex items-center gap-1 px-2 py-1 text-[0.6rem] font-bold bg-[#007AFF]/15 text-[#007AFF] rounded-sm hover:bg-[#007AFF]/25" data-testid="copy-alert-template-btn">
          {copied === "Alert message" ? <CheckCircle className="w-3 h-3" /> : <Copy className="w-3 h-3" />} Alert Message
        </button>
        <button onClick={() => onTest("buy")} disabled={testing} className="px-2 py-1 text-[0.6rem] font-black bg-[#34C759]/15 text-[#34C759] rounded-sm hover:bg-[#34C759]/25 disabled:opacity-40" data-testid="test-buy-btn">
          SEND TEST BUY
        </button>
        <button onClick={() => onTest("sell")} disabled={testing} className="px-2 py-1 text-[0.6rem] font-black bg-[#FF3B30]/15 text-[#FF3B30] rounded-sm hover:bg-[#FF3B30]/25 disabled:opacity-40" data-testid="test-sell-btn">
          SEND TEST SELL
        </button>
        <button onClick={() => onTest("hold")} disabled={testing} className="px-2 py-1 text-[0.6rem] font-black bg-[#FFCC00]/15 text-[#FFCC00] rounded-sm hover:bg-[#FFCC00]/25 disabled:opacity-40" data-testid="test-hold-btn">
          SEND TEST HOLD
        </button>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-x-3 gap-y-0.5 text-[0.55rem] font-mono text-zinc-500">
        <span>Last inbound: <span className="text-zinc-300">{rs.last_inbound ? etTime(rs.last_inbound.ts) : "never"}</span></span>
        <span>Last punch: <span className="text-[#34C759]">{rs.last_success ? etTime(rs.last_success.ts) : "none"}</span></span>
        <span>Last failure: <span className="text-[#FF3B30]">{rs.last_failure ? `${rs.last_failure.status} ${rs.last_failure.detail}` : "none"}</span></span>
      </div>

      <div className="flex flex-wrap items-center gap-x-3 gap-y-0.5 text-[0.55rem] font-mono text-zinc-500 border-t border-white/5 pt-1.5">
        <span data-testid="engine-last-eval">ENGINE: <span className="text-zinc-300">{eng.last_eval ? eng.last_eval.reason : "waiting for first evaluation"}</span></span>
        {eng.cooldown_remaining_sec > 0 && <span className="text-[#FFCC00]">cooldown {Math.ceil(eng.cooldown_remaining_sec / 60)}m</span>}
        {!rs.discord_configured && <span className="text-[#FFCC00]">Discord not configured</span>}
        {rs.secret_configured ? <span className="text-[#34C759]">secret ✓</span> : <span className="text-[#FFCC00]">no secret set</span>}
      </div>
    </div>
  );
};

// ===================== Signal Feed =====================
const SignalFeed = ({ signals, onUpdateSignal }) => {
  if (!signals.length)
    return (
      <div className="text-center text-zinc-500 py-10">
        <Radio className="w-8 h-8 mx-auto mb-2 opacity-40" />
        <p className="text-sm">No signals yet — use SEND TEST BUY above or connect TradingView</p>
      </div>
    );

  const sorted = [...signals].sort((a, b) => (a.is_test === b.is_test ? 0 : a.is_test ? 1 : -1));
  return (
    <div className="space-y-2 max-h-[400px] overflow-y-auto pr-1">
      {sorted.map((sig) => {
        const isLong = sig.side === "long";
        const isHold = sig.side === "hold";
        return (
          <div
            key={sig.id}
            className={`p-3 rounded-sm border transition-colors ${
              isHold
                ? "border-[#FFCC00]/30 bg-[#FFCC00]/5 opacity-80"
                : sig.status === "active"
                ? isLong
                  ? "border-[#34C759]/40 bg-[#34C759]/5"
                  : "border-[#FF3B30]/40 bg-[#FF3B30]/5"
                : "border-white/5 bg-white/[0.02] opacity-60"
            }`}
            data-testid={`signal-${sig.id}`}
          >
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                {isHold ? (
                  <Minus className="w-5 h-5 text-[#FFCC00]" />
                ) : isLong ? (
                  <TrendingUp className="w-5 h-5 text-[#34C759]" />
                ) : (
                  <TrendingDown className="w-5 h-5 text-[#FF3B30]" />
                )}
                <span className={`font-bold text-sm uppercase ${isHold ? "text-[#FFCC00]" : isLong ? "text-[#34C759]" : "text-[#FF3B30]"}`}>
                  {isHold ? "HOLD / WAIT" : isLong ? "BUY" : "SELL"} MNQ1!
                </span>
                <span className="text-xs text-zinc-500 font-mono">
                  {sig.interval || "1"}m · {etTime(sig.created_at)}
                </span>
              </div>
              <div className="flex items-center gap-1">
                {sig.is_test || sig.source === "test" ? (
                  <span className="text-[0.6rem] px-1.5 py-0.5 bg-[#FFCC00]/20 text-[#FFCC00] rounded">PAPER TEST</span>
                ) : sig.source === "live_engine" ? (
                  <span className="text-[0.6rem] px-1.5 py-0.5 bg-[#BF5AF2]/20 text-[#BF5AF2] rounded">ENGINE</span>
                ) : (
                  <span className="text-[0.6rem] px-1.5 py-0.5 bg-[#007AFF]/20 text-[#007AFF] rounded">LIVE</span>
                )}
                {typeof sig.confidence === "number" && !isHold && (
                  <span className="text-[0.6rem] px-1.5 py-0.5 rounded bg-white/5 border border-white/10 text-zinc-300 font-mono" data-testid={`signal-confidence-${sig.id}`}>
                    {sig.confidence}% conf
                  </span>
                )}
                <span className={`text-[0.6rem] px-1.5 py-0.5 rounded ${
                  sig.status === "held" ? "bg-[#FFCC00]/20 text-[#FFCC00]" :
                  sig.status === "active" ? "bg-[#34C759]/20 text-[#34C759]" :
                  sig.outcome === "win" ? "bg-[#34C759]/20 text-[#34C759]" :
                  sig.outcome === "loss" ? "bg-[#FF3B30]/20 text-[#FF3B30]" :
                  "bg-zinc-700 text-zinc-400"
                }`}>
                  {sig.status.toUpperCase()}
                </span>
              </div>
            </div>

            {isHold ? (
              <p className="text-xs font-mono text-[#FFCC00]/80" data-testid={`signal-hold-note-${sig.id}`}>
                Waiting for confirmation — no trade placed.
              </p>
            ) : (
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
            )}

            {/* Reason line */}
            {(sig.reason || sig.note) && (
              <p className="mt-1.5 text-[0.6rem] text-zinc-500 font-mono truncate">{sig.reason || sig.note}</p>
            )}

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
  const [receiverStatus, setReceiverStatus] = useState(null);

  const fetchAll = useCallback(async () => {
    try {
      const [sigRes, statsRes, healthRes, killRes, pineRes, rsRes] = await Promise.all([
        axios.get(`${API}/signals?limit=20`),
        axios.get(`${API}/signals/stats`),
        axios.get(`${API}/signals/health`),
        axios.get(`${API}/signals/kill-switch`),
        axios.get(`${API}/signals/pinescript`),
        axios.get(`${API}/signals/receiver-status`),
      ]);
      setSignals(sigRes.data);
      setStats(statsRes.data);
      setHealth(healthRes.data);
      setKillSwitch(killRes.data.kill_switch);
      setPineData(pineRes.data);
      setReceiverStatus(rsRes.data);
    } catch (e) {
      console.error("Signal fetch error:", e);
    }
  }, []);

  useEffect(() => {
    fetchAll();
    const interval = setInterval(fetchAll, 5000);
    return () => clearInterval(interval);
  }, [fetchAll]);

  const handleTestPunch = async (side) => {
    setLoading(true);
    try {
      const res = await axios.post(`${API}/signals/test-punch`, { side });
      if (res.data.status === "created") {
        toast.success(`PAPER ${side.toUpperCase()} punch injected`);
        await fetchAll();
      } else if (res.data.status === "held") {
        toast.success("HOLD accepted — no trade placed.");
        await fetchAll();
      } else {
        toast.error(res.data.reason || "Punch blocked");
      }
    } catch (e) {
      toast.error(e.response?.data?.detail || "Test punch failed");
    }
    setLoading(false);
  };

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
          <ReceiverPanel rs={receiverStatus} onTest={handleTestPunch} testing={loading} />

          {/* Stats row */}
          <div className="grid grid-cols-2 md:grid-cols-5 gap-2 mb-4">
            <div className="stat-box">
              <span className="stat-label">Signals</span>
              <span className="stat-value text-lg">{stats.total_signals || 0}</span>
            </div>
            <div className="stat-box">
              <span className="stat-label">Win Rate</span>
              <span className={`stat-value text-lg ${
                !hasNum(stats.win_rate) ? "text-zinc-400" : stats.win_rate >= 50 ? "text-[#34C759]" : "text-[#FF3B30]"
              }`}>
                {fmtPct(stats.win_rate)}
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
