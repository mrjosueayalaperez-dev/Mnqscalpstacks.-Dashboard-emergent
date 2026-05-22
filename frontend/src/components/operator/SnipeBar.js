import React from "react";
import { Crosshair, Volume2, VolumeX, Keyboard } from "lucide-react";

const KeyCap = ({ k }) => (
  <kbd className="inline-block min-w-[1.4rem] text-center px-1.5 py-0.5 text-[0.55rem] font-mono font-black bg-white/10 border border-white/20 rounded text-white shadow-[0_1px_0_rgba(255,255,255,0.1)_inset]">
    {k}
  </kbd>
);

export default function SnipeBar({ snipe, onToggleSnipe, sound, onToggleSound, showHelp, onToggleHelp }) {
  return (
    <div
      data-testid="snipe-bar"
      className={`flex items-center justify-between gap-3 px-3 py-2 border rounded-sm transition-all ${
        snipe
          ? "border-[#FF3B30]/60 bg-[#FF3B30]/5 shadow-[0_0_20px_rgba(255,59,48,0.15)_inset]"
          : "border-white/10 bg-[#121212]"
      }`}
    >
      <div className="flex items-center gap-2 min-w-0">
        <Crosshair className={`w-3.5 h-3.5 ${snipe ? "text-[#FF3B30] animate-pulse" : "text-zinc-500"}`} />
        <span className={`text-[0.65rem] font-black uppercase tracking-wider ${snipe ? "text-[#FF3B30]" : "text-zinc-400"}`}>
          {snipe ? "SNIPE MODE ARMED" : "Snipe Mode"}
        </span>
        <span className="hidden md:inline text-[0.55rem] text-zinc-600 truncate">
          {snipe ? "Hotkeys hot • UI cooldown bypassed (server still enforces 1500ms)" : "Press S to arm"}
        </span>
      </div>

      <div className="flex items-center gap-1.5 shrink-0">
        <button
          onClick={onToggleHelp}
          data-testid="snipe-help-toggle"
          className={`px-2 py-1 text-[0.55rem] font-bold rounded-sm flex items-center gap-1 transition-colors ${
            showHelp ? "bg-white/15 text-white" : "bg-white/5 text-zinc-400 hover:text-white"
          }`}
          title="Toggle hotkey help (?)"
        >
          <Keyboard className="w-3 h-3" />
          <span className="hidden sm:inline">HOTKEYS</span>
          <KeyCap k="?" />
        </button>

        <button
          onClick={onToggleSound}
          data-testid="snipe-sound-toggle"
          className={`px-2 py-1 text-[0.55rem] font-bold rounded-sm flex items-center gap-1 transition-colors ${
            sound ? "bg-[#34C759]/15 text-[#34C759]" : "bg-white/5 text-zinc-500"
          }`}
          title="Toggle audio confirmations (M)"
        >
          {sound ? <Volume2 className="w-3 h-3" /> : <VolumeX className="w-3 h-3" />}
          <span className="hidden sm:inline">{sound ? "SOUND" : "MUTED"}</span>
        </button>

        <button
          onClick={onToggleSnipe}
          data-testid="snipe-arm-toggle"
          className={`px-3 py-1 text-[0.6rem] font-black uppercase tracking-wider rounded-sm flex items-center gap-1.5 transition-all ${
            snipe
              ? "bg-[#FF3B30] text-white shadow-[0_0_15px_rgba(255,59,48,0.5)]"
              : "bg-white/10 text-zinc-300 hover:bg-white/20"
          }`}
        >
          {snipe ? "DISARM" : "ARM SNIPE"}
        </button>
      </div>
    </div>
  );
}

export const HotkeyHelp = ({ onClose }) => (
  <div
    data-testid="hotkey-help"
    className="fixed inset-0 bg-black/80 backdrop-blur-sm z-[60] flex items-center justify-center p-4"
    onClick={onClose}
  >
    <div
      className="bg-[#121212] border border-white/20 rounded-sm p-5 max-w-md w-full shadow-2xl"
      onClick={(e) => e.stopPropagation()}
    >
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-sm font-black tracking-wider text-white flex items-center gap-2">
          <Keyboard className="w-4 h-4 text-[#FFCC00]" /> COCKPIT HOTKEYS
        </h2>
        <button
          onClick={onClose}
          data-testid="hotkey-help-close"
          className="text-zinc-500 hover:text-white text-xs font-bold"
        >
          ESC
        </button>
      </div>

      <div className="space-y-3 text-[0.7rem]">
        {[
          { title: "Execution", rows: [
            ["B", "BUY MARKET"],
            ["N", "SELL MARKET (short)"],
            ["L", "BUY LIMIT"],
            [";", "SELL LIMIT"],
            ["C", "CLOSE current position"],
            ["E", "BREAK EVEN"],
          ]},
          { title: "Master", rows: [
            ["F", "FLATTEN ALL"],
            ["P", "PAUSE / RESUME automation"],
            ["K", "KILL SWITCH toggle"],
            ["R", "RESET session"],
            ["S", "Toggle Snipe Mode"],
            ["M", "Mute / unmute audio"],
          ]},
          { title: "Bracket Presets", rows: [
            ["7", "Snipe 1R (40t SL / 60t TP)"],
            ["8", "Snipe 2R (40t SL / 120t TP)"],
            ["9", "Runner (40t SL / 200t TP)"],
            ["0", "Toggle attach brackets on/off"],
          ]},
          { title: "Chart", rows: [
            ["1", "1m timeframe"],
            ["2", "5m timeframe"],
            ["3", "15m timeframe"],
            ["?", "Show / hide this help"],
            ["Escape", "Close help"],
          ]},
        ].map((group) => (
          <div key={group.title}>
            <h3 className="text-[0.55rem] font-black uppercase tracking-wider text-zinc-500 mb-1.5">{group.title}</h3>
            <div className="space-y-1">
              {group.rows.map(([k, label]) => (
                <div key={k} className="flex items-center justify-between">
                  <KeyCap k={k} />
                  <span className="text-zinc-400 ml-3 flex-1 text-right">{label}</span>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      <p className="text-[0.55rem] text-zinc-600 italic mt-4 leading-snug">
        Server still enforces 1500ms cooldown, kill switch, daily loss & max trade caps — Snipe Mode just removes the UI delay so your reflexes match the engine.
      </p>
    </div>
  </div>
);
