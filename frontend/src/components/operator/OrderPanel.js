import React from "react";
import { TrendingUp, TrendingDown, Target, X } from "lucide-react";
import useOrderCooldown from "./useOrderCooldown";

const Btn = ({ children, onClick, color, locked, testId }) => (
  <button
    onClick={onClick}
    disabled={locked}
    data-testid={testId}
    className={`w-full py-2.5 px-3 text-[0.65rem] font-black uppercase tracking-wider rounded-sm transition-all flex items-center justify-center gap-1.5 ${
      locked ? "opacity-40 cursor-not-allowed" : "hover:brightness-125 active:scale-[0.98]"
    }`}
    style={{
      backgroundColor: `${color}25`,
      color,
      border: `1px solid ${color}55`,
    }}
  >
    {children}
  </button>
);

export default function OrderPanel({ side, onOrder, disabled, snipeMode = false }) {
  const isLong = side === "LONG";
  const color = isLong ? "#34C759" : "#FF3B30";
  const { locked, arm } = useOrderCooldown(snipeMode ? 0 : 1500);

  const send = async (action, type) => {
    if (locked || disabled) return;
    if (!snipeMode) arm();
    await onOrder({ action, order_type: type });
  };

  return (
    <div
      className="bg-[#121212] border rounded-sm p-3 space-y-2"
      style={{ borderColor: `${color}40` }}
      data-testid={`order-panel-${side.toLowerCase()}`}
    >
      <div className="flex items-center justify-between">
        <h3 className="text-[0.65rem] font-black uppercase tracking-wider flex items-center gap-1.5" style={{ color }}>
          {isLong ? <TrendingUp className="w-3.5 h-3.5" /> : <TrendingDown className="w-3.5 h-3.5" />}
          {side}
        </h3>
        <span className="text-[0.55rem] text-zinc-500 font-mono">QTY 1</span>
      </div>

      <div className="grid grid-cols-2 gap-2">
        <Btn
          color={color}
          locked={locked || disabled}
          onClick={() => send(isLong ? "BUY" : "SELL", "MARKET")}
          testId={`${side.toLowerCase()}-market`}
        >
          {isLong ? "BUY" : "SELL"} MARKET
        </Btn>
        <Btn
          color={color}
          locked={locked || disabled}
          onClick={() => send(isLong ? "BUY" : "SELL", "LIMIT")}
          testId={`${side.toLowerCase()}-limit`}
        >
          {isLong ? "BUY" : "SELL"} LIMIT
        </Btn>
      </div>

      <div className="grid grid-cols-2 gap-2">
        <Btn
          color="#FFCC00"
          locked={locked || disabled}
          onClick={() => send("BREAK_EVEN", "MARKET")}
          testId={`${side.toLowerCase()}-be`}
        >
          <Target className="w-3 h-3" /> BREAK EVEN
        </Btn>
        <Btn
          color="#9ca3af"
          locked={locked || disabled}
          onClick={() => send(isLong ? "CLOSE_LONG" : "CLOSE_SHORT", "MARKET")}
          testId={`${side.toLowerCase()}-close`}
        >
          <X className="w-3 h-3" /> CLOSE {side}
        </Btn>
      </div>

      {locked && !snipeMode && (
        <div className="text-center text-[0.55rem] text-[#FFCC00] font-bold tracking-wider animate-pulse">
          ⏱ COOLDOWN 1500ms
        </div>
      )}
      {snipeMode && (
        <div className="text-center text-[0.55rem] text-[#FF3B30] font-black tracking-wider">
          ◉ SNIPE — INSTANT
        </div>
      )}
    </div>
  );
}
