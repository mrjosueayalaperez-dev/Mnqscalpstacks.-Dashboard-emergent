import React, { useCallback, useEffect, useState } from "react";
import axios from "axios";
import { toast, Toaster } from "sonner";

import TopStatusBar from "./TopStatusBar";
import LiveChart from "./LiveChart";
import OrderPanel from "./OrderPanel";
import PositionInfo from "./PositionInfo";
import RiskPanel from "./RiskPanel";
import SignalPanel from "./SignalPanel";
import JournalPanel from "./JournalPanel";
import MasterControls from "./MasterControls";
import SnipeBar, { HotkeyHelp } from "./SnipeBar";
import BracketPresets, { PRESETS, presetById } from "./BracketPresets";
import useHotkeys from "./useHotkeys";
import { sounds, unlockAudio } from "./useAudio";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const LS_SNIPE = "operator.snipe";
const LS_SOUND = "operator.sound";
const LS_PRESET = "operator.preset";
const LS_BRACKETS = "operator.brackets";

export default function OperatorCockpit() {
  const [state, setState] = useState(null);
  const [mnq, setMnq] = useState(null);
  const [journal, setJournal] = useState([]);

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

  const refreshMNQ = useCallback(async () => {
    try {
      const { data } = await axios.get(`${API}/futures/mnq`);
      setMnq(data);
    } catch (e) { /* ignore */ }
  }, []);

  const refreshJournal = useCallback(async () => {
    try {
      const { data } = await axios.get(`${API}/operator/journal`, { params: { limit: 15 } });
      setJournal(data.entries || []);
    } catch (e) { /* ignore */ }
  }, []);

  useEffect(() => {
    refreshState(); refreshMNQ(); refreshJournal();
    const s = setInterval(refreshState, 2000);
    const m = setInterval(refreshMNQ, 4000);
    const j = setInterval(refreshJournal, 5000);
    return () => { clearInterval(s); clearInterval(m); clearInterval(j); };
  }, [refreshState, refreshMNQ, refreshJournal]);

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
        limit_price: order_type === "LIMIT" ? (mnq?.close || 18500) : null,
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

  const lastPrice = mnq?.close || mnq?.price;
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
          <LiveChart />
        </div>

        <div className="col-span-12 lg:col-span-3 space-y-3">
          <PositionInfo state={state} lastPrice={lastPrice} />
          <SignalPanel mnqData={mnq} />
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
          <div className="px-3 py-2 border border-[#FFCC00]/30 bg-[#FFCC00]/5 rounded-sm flex items-center justify-between text-[0.6rem]">
            <span className="text-[#FFCC00] font-bold">PHASE 1 — SIMULATED LOG ONLY</span>
            <span className="text-zinc-500">Orders are validated server-side and logged. No broker connection is active yet.</span>
          </div>
        </div>
      </main>

      {showHelp && <HotkeyHelp onClose={() => setShowHelp(false)} />}
    </div>
  );
}
