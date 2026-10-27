import React, { useCallback, useEffect, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import { BookOpen, Trash2 } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const MODES = ["TEST", "PAPER", "LIVE"];
const DISCLAIMER =
  "Futures trading involves substantial risk of loss and is not suitable for all investors. This is education and structured practice, not financial advice. Past performance is not indicative of future results.";
const fmt = (n) => (n === null || n === undefined ? "—" : `${n < 0 ? "-" : ""}$${Math.abs(n).toFixed(2)}`);

// Manual journal only. This card never places, routes, or simulates trades.
export const ApexPnlJournal = () => {
  const [mode, setMode] = useState("TEST");
  const [data, setData] = useState({ entries: [], stats: null });
  const [form, setForm] = useState({ date: "", daily_pnl: "", note: "" });

  const load = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/pnl-journal`, { params: { mode }, withCredentials: true });
      setData(res.data);
    } catch (e) {
      setData({ entries: [], stats: null });
      if (e?.response?.status === 401) toast.error("Sign in to use the P&L journal");
    }
  }, [mode]);

  useEffect(() => { load(); }, [load]);

  const submit = async (ev) => {
    ev.preventDefault();
    if (!form.date || form.daily_pnl === "" || isNaN(parseFloat(form.daily_pnl))) return toast.error("Date and daily P&L required");
    try {
      await axios.post(`${API}/pnl-journal`, { date: form.date, daily_pnl: parseFloat(form.daily_pnl), mode, note: form.note || null }, { withCredentials: true });
      setForm({ date: "", daily_pnl: "", note: "" });
      load();
    } catch { toast.error("Could not save entry"); }
  };

  const remove = async (id) => {
    try { await axios.delete(`${API}/pnl-journal/${id}`, { withCredentials: true }); load(); }
    catch { toast.error("Could not delete entry"); }
  };

  const s = data.stats;
  const inputCls = "bg-black/40 border border-white/10 rounded px-2 py-1 text-sm text-white";
  return (
    <div className="widget-panel col-span-1 md:col-span-4 lg:col-span-8 p-4" data-testid="apex-pnl-journal">
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-semibold text-white flex items-center gap-2"><BookOpen className="w-4 h-4" /> Apex 50K Eval — Daily P&L Journal</h3>
        <div className="flex gap-1" role="tablist">
          {MODES.map((m) => (
            <button key={m} onClick={() => setMode(m)} data-testid={`journal-mode-${m}`}
              className={`text-xs px-2 py-1 rounded ${mode === m ? "bg-cyan-600 text-white" : "bg-white/5 text-gray-400"}`}>{m}</button>
          ))}
        </div>
      </div>
      <p className="text-xs text-gray-400 mb-3">Manual log of your own results. Showing <b className="text-white">{mode}</b> entries only (modes are not mixed).</p>

      <form onSubmit={submit} className="flex flex-wrap gap-2 mb-3">
        <input type="date" className={inputCls} value={form.date} onChange={(e) => setForm({ ...form, date: e.target.value })} data-testid="journal-date" />
        <input type="number" step="0.01" placeholder="Daily P&L ($)" className={inputCls} value={form.daily_pnl} onChange={(e) => setForm({ ...form, daily_pnl: e.target.value })} data-testid="journal-pnl" />
        <input type="text" maxLength={500} placeholder="Note (optional)" className={`${inputCls} flex-1 min-w-[120px]`} value={form.note} onChange={(e) => setForm({ ...form, note: e.target.value })} />
        <button type="submit" className="text-sm px-3 py-1 rounded bg-cyan-700 text-white" data-testid="journal-add">Log {mode} day</button>
      </form>

      {s && s.days > 0 && (
        <div className="grid grid-cols-3 gap-2 mb-3 text-center text-sm">
          <div><div className="text-gray-400 text-xs">Net profit</div><div className="text-white" data-testid="journal-total">{fmt(s.total)}</div></div>
          <div><div className="text-gray-400 text-xs">Best day</div><div className="text-white">{fmt(s.best_day)}</div></div>
          <div><div className="text-gray-400 text-xs">Best day % of total</div><div className="text-white" data-testid="journal-pct">{s.best_day_pct === "N/A" ? "N/A" : `${s.best_day_pct}%`}</div></div>
          <div className="col-span-3 text-xs text-gray-400">Progress to ${s.target.toLocaleString()} target: {s.target_progress_pct}% · {s.eval_days} calendar days · ${s.trailing_drawdown.toLocaleString()} trailing drawdown (informational)</div>
        </div>
      )}

      {data.entries.length === 0 ? (
        <p className="text-sm text-gray-500 py-4 text-center" data-testid="journal-empty">No entries yet</p>
      ) : (
        <table className="w-full text-sm text-left">
          <thead className="text-xs text-gray-400"><tr><th>Date</th><th>Mode</th><th>Daily P&L</th><th>Running total</th><th>Note</th><th></th></tr></thead>
          <tbody>
            {data.entries.map((e) => (
              <tr key={e.entry_id} className="border-t border-white/5 text-white">
                <td>{e.date}</td><td>{e.mode}</td>
                <td className={e.daily_pnl < 0 ? "text-red-400" : "text-green-400"}>{fmt(e.daily_pnl)}</td>
                <td>{fmt(e.running_total)}</td><td className="text-gray-400">{e.note}</td>
                <td><button onClick={() => remove(e.entry_id)} aria-label="Delete entry"><Trash2 className="w-3 h-3 text-gray-500" /></button></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <p className="text-xs text-amber-300/80 mt-3">Funded PA payout gate: best single day must be under 50% of net profit since last approved payout.</p>
      <p className="text-[11px] text-gray-500 mt-2" data-testid="journal-disclaimer">{DISCLAIMER}</p>
    </div>
  );
};

export default ApexPnlJournal;
