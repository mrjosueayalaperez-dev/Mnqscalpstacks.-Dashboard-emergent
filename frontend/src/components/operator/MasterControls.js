import React from "react";
import { Power, Pause, Play, RotateCcw, Skull } from "lucide-react";

const Big = ({ onClick, color, icon: Icon, label, sub, testId }) => (
  <button
    onClick={onClick}
    data-testid={testId}
    className="flex-1 px-3 py-2.5 rounded-sm font-black uppercase tracking-wider text-[0.65rem] transition-all hover:brightness-125 active:scale-[0.98] flex items-center justify-center gap-2"
    style={{
      backgroundColor: `${color}20`,
      color,
      border: `1px solid ${color}55`,
    }}
  >
    <Icon className="w-3.5 h-3.5" />
    <div className="text-left leading-tight">
      <div>{label}</div>
      {sub && <div className="text-[0.5rem] opacity-70 font-normal">{sub}</div>}
    </div>
  </button>
);

export default function MasterControls({ state, onControl }) {
  const paused = state?.automation_paused;
  const killed = state?.kill_switch;

  return (
    <div className="bg-[#121212] border border-white/10 rounded-sm p-3" data-testid="master-controls">
      <h3 className="text-[0.6rem] font-black uppercase tracking-wider text-zinc-500 mb-2">Master Controls</h3>
      <div className="flex flex-col sm:flex-row gap-2">
        <Big
          onClick={() => onControl("flatten")}
          color="#FF3B30"
          icon={Power}
          label="FLATTEN ALL"
          sub="Close every position"
          testId="ctrl-flatten"
        />
        <Big
          onClick={() => onControl(paused ? "resume" : "pause")}
          color="#FFCC00"
          icon={paused ? Play : Pause}
          label={paused ? "RESUME" : "PAUSE"}
          sub="Automation gate"
          testId="ctrl-pause"
        />
        <Big
          onClick={() => onControl("reset_session")}
          color="#007AFF"
          icon={RotateCcw}
          label="RESET"
          sub="Clear session"
          testId="ctrl-reset"
        />
        <Big
          onClick={() => onControl(killed ? "unkill" : "kill")}
          color={killed ? "#34C759" : "#a855f7"}
          icon={Skull}
          label={killed ? "DISARM KILL" : "KILL SWITCH"}
          sub="Block all orders"
          testId="ctrl-kill"
        />
      </div>
    </div>
  );
}
