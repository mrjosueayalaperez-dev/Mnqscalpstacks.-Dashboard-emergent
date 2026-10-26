/** Canvas-rendered branded trade share card → PNG (Web Share API or download). */

function drawCard(trade) {
  const W = 1080, H = 1080;
  const c = document.createElement("canvas");
  c.width = W; c.height = H;
  const ctx = c.getContext("2d");

  const pnl = trade.pnl ?? 0;
  const win = pnl >= 0;
  const accent = win ? "#34C759" : "#FF3B30";

  // Background
  ctx.fillStyle = "#0A0A0A";
  ctx.fillRect(0, 0, W, H);
  ctx.strokeStyle = accent;
  ctx.lineWidth = 12;
  ctx.strokeRect(24, 24, W - 48, H - 48);
  // Subtle grid
  ctx.strokeStyle = "rgba(255,255,255,0.04)";
  ctx.lineWidth = 1;
  for (let x = 80; x < W; x += 80) { ctx.beginPath(); ctx.moveTo(x, 40); ctx.lineTo(x, H - 40); ctx.stroke(); }

  // Brand
  ctx.fillStyle = "#FFFFFF";
  ctx.font = "900 54px 'Arial Black', Arial";
  ctx.fillText("MNQ SCALP STACKS", 80, 140);
  ctx.fillStyle = "#71717a";
  ctx.font = "700 30px Arial";
  ctx.fillText("STACK. EXECUTE. PROFIT.", 80, 190);

  // Side + symbol
  ctx.fillStyle = accent;
  ctx.font = "900 64px Arial";
  ctx.fillText(`${trade.side || "TRADE"} ${trade.qty || 1}x MNQ`, 80, 330);

  // PnL — the hero
  ctx.fillStyle = accent;
  ctx.font = "900 190px 'Arial Black', Arial";
  ctx.fillText(`${win ? "+" : "-"}$${Math.abs(pnl).toFixed(2)}`, 80, 560);
  ctx.fillStyle = "#a1a1aa";
  ctx.font = "700 36px Arial";
  ctx.fillText(win ? "WIN — PAPER/SIM PRACTICE (NOT LIVE)" : "LOSS — PAPER/SIM PRACTICE (NOT LIVE)", 80, 630);

  // Details
  ctx.font = "700 40px 'Courier New', monospace";
  let y = 740;
  const line = (label, value, color = "#FFFFFF") => {
    ctx.fillStyle = "#71717a"; ctx.fillText(label, 80, y);
    ctx.fillStyle = color; ctx.fillText(value, 420, y);
    y += 70;
  };
  if (trade.entry) line("ENTRY", Number(trade.entry).toFixed(2));
  if (trade.exit) line("EXIT", Number(trade.exit).toFixed(2));
  if (trade.grade) line("GRADE", trade.grade, "#FFCC00");
  line("DATE", new Date(trade.ts || Date.now()).toLocaleDateString("en-US"));

  // Footer
  ctx.fillStyle = accent;
  ctx.font = "900 40px Arial";
  ctx.fillText("mnq-scalp-stack.emergent.host", 80, H - 90);

  return c;
}

export async function shareTradeCard(trade) {
  const canvas = drawCard(trade);
  const blob = await new Promise((res) => canvas.toBlob(res, "image/png"));
  const file = new File([blob], "mnq-scalp-stacks-trade.png", { type: "image/png" });

  if (navigator.canShare && navigator.canShare({ files: [file] })) {
    try {
      await navigator.share({
        files: [file],
        title: "MNQ Scalp Stacks",
        text: `${trade.side} MNQ ${trade.pnl >= 0 ? "+" : ""}$${(trade.pnl ?? 0).toFixed(2)} — verified on MNQ Scalp Stacks`,
      });
      return "shared";
    } catch { /* user cancelled — fall through to download */ }
  }
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "mnq-scalp-stacks-trade.png";
  a.click();
  URL.revokeObjectURL(a.href);
  return "downloaded";
}
