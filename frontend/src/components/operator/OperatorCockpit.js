import React, { useCallback, useEffect, useState } from "react";
import axios from "axios";
import { toast, Toaster } from "sonner";

import TopStatusBar from "./TopStatusBar";
import TradingViewWidget from "./TradingViewWidget";
import OrderPanel from "./OrderPanel";
import PositionInfo from "./PositionInfo";
import RiskPanel from "./RiskPanel";
import SignalPanel from "./SignalPanel";
import JournalPanel from "./JournalPanel";
import MasterControls from "./MasterControls";
import MarketContext from "./MarketContext";
import SnipeBar, { HotkeyHelp } from "./SnipeBar";
import BracketPresets, { PRESETS, presetById } from "./BracketPresets";
import useHotkeys from "./useHotkeys";
import useMnqLive from "./useMnqLive";
import { sounds, unlockAudio } from "./useAudio";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const LS_SNIPE = "operator.snipe";
const LS_SOUND = "operator.sound";
const LS_PRESET = "operator.preset";
const LS_BRACKETS = "operator.brackets";

export default function OperatorCockpit() {
  const [state, setState] = useState(null);
  const [journal, setJournal] = useState([]);
  const { tick: mnq, connected: wsConnected } = useMnqLive();

  const [snipe, setSnipe] = useState(() => localStorage.getItem(LS_SNIPE) === "1");
  const [sound, setSound] = useState(() => localStorage.getItem(LS_SOUND) !== "0");
  const [presetId, setPresetId] = useState(() => localStorage.getItem(LS_PRESET) || "SNIPE_2R");
  const [brackets, setBrackets] = useState(() => localStorage.getItem(LS_BRACKETS) !== "0");
  const [showHelp, setShowHelp] = useState(false);

  const activePreset = presetById(presetId) || PRESETS[1];

  const selectPreset = useCallback((id, enable) => {
    setPresetId(id);
    setBrackets(enable);
    localStorage.setItem(LS_PRESET, id);
    localStorage.setItem(LS_BRACKETS, enable ? "1" : "0");
    if (sound) sounds.click();
  }, [sound]);

  const play = useCallback((name) => {
    if (sound && sounds[name]) sounds[name]();
  }, [sound]);

  const refreshState = useCallback(async () => {
    try {
      const { data } = await axios.get(`${API}/operator/state`);
      setState(data);
    } catch (e) { /* ignore */ }
  }, []);

  const refreshJournal = useCallback(async () => {
    try {
      const { data } = await axios.get(`${API}/operator/journal`, { params: { limit: 15 } });
      setJournal(data.entries || []);
    } catch (e) { /* ignore */ }
  }, []);

  useEffect(() => {
    refreshState(); refreshJournal();
    const s = setInterval(refreshState, 2000);
    const j = setInterval(refreshJournal, 5000);
    return () => { clearInterval(s); clearInterval(j); };
  }, [refreshState, refreshJournal]);

  // Suppress benign cross-origin "Script error." reports thrown by the
  // TradingView widget iframe — they cannot leak data into our code and
  // they spuriously trigger the CRA dev-overlay.
  useEffect(() => {
    const swallow = (e) => {
      const msg = e?.message || "";
      if (msg === "Script error." || !e?.filename) {
        e.preventDefault?.();
        return true;
      }
      return false;
    };
    window.addEventListener("error", swallow, true);
    return () => window.removeEventListener("error", swallow, true);
  }, []);

  const submitOrder = useCallback(async ({ action, order_type }) => {
    // Pick a confirmation sound based on action
    const sndMap = { BUY: "buy", SELL: "sell", CLOSE_LONG: "close", CLOSE_SHORT: "close", BREAK_EVEN: "breakEven" };
    // Attach brackets only on opening orders
    const attach = brackets && (action === "BUY" || action === "SELL");
    try {
      const body = {
        action,
        symbol: "MNQ",
        qty: 1,
        order_type,
        limit_price: order_type === "LIMIT" ? (mnq?.price || mnq?.close || null) : null,
        sl_ticks: attach ? activePreset.sl : null,
        tp_ticks: attach ? activePreset.tp : null,
        preset: attach ? activePreset.id : null,
      };
      const { data } = await axios.post(`${API}/operator/order`, body);
      play(sndMap[action] || "click");
      const bracketLine = data.order?.sl_price
        ? ` • SL ${data.order.sl_price.toFixed(2)} / TP ${data.order.tp_price.toFixed(2)} (${activePreset.label})`
        : "";
      toast.success(`${action} ${order_type} accepted`, {
        description: data.order
          ? `Fill @ ${data.order.fill_price?.toFixed(2)}${bracketLine}`
          : undefined,
      });
      refreshState();
      refreshJournal();
    } catch (e) {
      play("reject");
      const detail = e.response?.data?.detail || "Order rejected";
      toast.error(`${action} blocked`, { description: detail });
    }
  }, [mnq, refreshState, refreshJournal, play, brackets, activePreset]);

  const sendControl = useCallback(async (act) => {
    try {
      await axios.post(`${API}/operator/control/${act}`);
      const sndMap = { flatten: "flatten", pause: "pause", resume: "pause", kill: "killOn", unkill: "killOff", reset_session: "click" };
      play(sndMap[act] || "click");
      toast.success(`Control: ${act.toUpperCase()}`);
      refreshState();
      refreshJournal();
    } catch (e) {
      play("reject");
      toast.error(`Control failed: ${act}`);
    }
  }, [refreshState, refreshJournal, play]);

  // ===== Snipe + Sound toggles (persisted) =====
  const toggleSnipe = useCallback(() => {
    unlockAudio();
    setSnipe((v) => {
      const next = !v;
      localStorage.setItem(LS_SNIPE, next ? "1" : "0");
      if (sound) (next ? sounds.snipeOn : sounds.snipeOff)();
      return next;
    });
  }, [sound]);

  const toggleSound = useCallback(() => {
    setSound((v) => {
      const next = !v;
      localStorage.setItem(LS_SOUND, next ? "1" : "0");
      if (next) sounds.click();
      return next;
    });
  }, []);

  // ===== HOTKEYS =====
  const pos = state?.position;
  const hasPos = !!pos?.side;
  const isLong = pos?.side === "LONG";

  useHotkeys({
    // Execution
    b: () => submitOrder({ action: "BUY", order_type: "MARKET" }),
    n: () => submitOrder({ action: "SELL", order_type: "MARKET" }),
    l: () => submitOrder({ action: "BUY", order_type: "LIMIT" }),
    ";": () => submitOrder({ action: "SELL", order_type: "LIMIT" }),
    c: () => hasPos && submitOrder({ action: isLong ? "CLOSE_LONG" : "CLOSE_SHORT", order_type: "MARKET" }),
    e: () => submitOrder({ action: "BREAK_EVEN", order_type: "MARKET" }),

    // Master
    f: () => sendControl("flatten"),
    p: () => sendControl(state?.automation_paused ? "resume" : "pause"),
    k: () => sendControl(state?.kill_switch ? "unkill" : "kill"),
    r: () => sendControl("reset_session"),
    s: () => toggleSnipe(),
    m: () => toggleSound(),

    // Help / dismiss
    "?": () => setShowHelp((h) => !h),
    h: () => setShowHelp((h) => !h),
    escape: () => setShowHelp(false),

    // Bracket presets
    "7": () => selectPreset("SNIPE_1R", true),
    "8": () => selectPreset("SNIPE_2R", true),
    "9": () => selectPreset("RUNNER", true),
    "0": () => selectPreset(presetId, !brackets),  // toggle attach on/off
  }, true);

  const lastPrice = mnq?.price || mnq?.close;
  const orderDisabled = state?.kill_switch || (!snipe && (state?.cooldown_ms_remaining || 0) > 0);

  return (
    <div
      data-testid="operator-cockpit"
      onClick={unlockAudio}
      className={`min-h-screen flex flex-col transition-colors ${snipe ? "bg-[#0A0606]" : "bg-[#0A0A0A]"}`}
    >
      <Toaster
        position="top-right"
        toastOptions={{
          style: { background: "#121212", border: "1px solid rgba(255,255,255,0.1)", color: "#fff", fontSize: "0.75rem" },
        }}
      />

      {/* Snipe-mode glow ring */}
      {snipe && (
        <div className="pointer-events-none fixed inset-0 z-[40] ring-2 ring-inset ring-[#FF3B30]/40 animate-pulse" />
      )}

      <TopStatusBar state={state} onFlatten={() => sendControl("flatten")} />

      <main className="flex-1 p-3 grid grid-cols-12 gap-3 auto-rows-min">
        {/* SNIPE BAR */}
        <div className="col-span-12">
          <SnipeBar
            snipe={snipe}
            sound={sound}
            showHelp={showHelp}
            onToggleSnipe={toggleSnipe}
            onToggleSound={toggleSound}
            onToggleHelp={() => setShowHelp((h) => !h)}
          />
        </div>

        {/* LIVE CHART */}
        <div className="col-span-12 lg:col-span-9 h-[420px] lg:h-[520px]">
          <TradingViewWidget wsConnected={wsConnected} lastTick={mnq} />
        </div>

        <div className="col-span-12 lg:col-span-3 space-y-3">
          <PositionInfo state={state} lastPrice={lastPrice} />
          <SignalPanel mnqData={mnq} />
          <MarketContext />
        </div>

        <div className="col-span-12 md:col-span-4">
          <OrderPanel side="LONG" onOrder={submitOrder} disabled={orderDisabled} snipeMode={snipe} bracketLabel={brackets ? activePreset : null} />
        </div>
        <div className="col-span-12 md:col-span-4 space-y-3">
          <MasterControls state={state} onControl={sendControl} />
          <BracketPresets activeId={presetId} onSelect={selectPreset} brackets={brackets} />
        </div>
        <div className="col-span-12 md:col-span-4">
          <OrderPanel side="SHORT" onOrder={submitOrder} disabled={orderDisabled} snipeMode={snipe} bracketLabel={brackets ? activePreset : null} />
        </div>

        <div className="col-span-12 md:col-span-5">
          <RiskPanel state={state} />
        </div>
        <div className="col-span-12 md:col-span-7">
          <JournalPanel entries={journal} />
        </div>

        <div className="col-span-12 mt-1">
          <div className="px-3 py-2 border border-[#34C759]/30 bg-[#34C759]/5 rounded-sm flex items-center justify-between text-[0.6rem]">
            <span className="text-[#34C759] font-black">◉ LIVE FEED — CME via TradingView + Yahoo NQ=F</span>
            <span className="text-zinc-500">Chart, prices, and order fills use real MNQ data. Order execution = simulator until Phase 2 (NinjaTrader ATI bridge).</span>
          </div>
        </div>
      </main>

      {showHelp && <HotkeyHelp onClose={() => setShowHelp(false)} />}
    </div>
  );
}
