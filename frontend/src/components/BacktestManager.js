import React, { useState, useEffect } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  FlaskConical,
  Plus,
  Trash2,
  ChevronDown,
  ChevronUp,
  Save,
} from "lucide-react";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const BacktestManager = () => {
  const [backtests, setBacktests] = useState([]);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({
    strategy_name: "MNQ Scalp Stack v2",
    timeframe: "1m",
    symbol: "MNQ",
    period_start: "",
    period_end: "",
    total_trades: "",
    winning_trades: "",
    losing_trades: "",
    profit_factor: "",
    net_profit: "",
    max_drawdown: "",
    max_drawdown_pct: "",
    sharpe_ratio: "",
    avg_trade: "",
    avg_win: "",
    avg_loss: "",
    largest_win: "",
    largest_loss: "",
    max_consecutive_wins: "",
    max_consecutive_losses: "",
    notes: "",
  });

  const fetchBacktests = async () => {
    try {
      const res = await axios.get(`${API}/backtests`);
      setBacktests(res.data);
    } catch (e) {
      console.error("Fetch backtests error:", e);
    }
  };

  useEffect(() => {
    fetchBacktests();
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    const payload = {};
    for (const [k, v] of Object.entries(form)) {
      if (v === "") continue;
      if (["total_trades", "winning_trades", "losing_trades", "max_consecutive_wins", "max_consecutive_losses"].includes(k)) {
        payload[k] = parseInt(v) || 0;
      } else if (["profit_factor", "net_profit", "max_drawdown", "max_drawdown_pct", "sharpe_ratio", "avg_trade", "avg_win", "avg_loss", "largest_win", "largest_loss"].includes(k)) {
        payload[k] = parseFloat(v) || 0;
      } else {
        payload[k] = v;
      }
    }

    try {
      await axios.post(`${API}/backtests`, payload);
      toast.success("Backtest result saved!");
      setShowForm(false);
      await fetchBacktests();
    } catch (e) {
      toast.error("Failed to save backtest");
    }
  };

  const handleDelete = async (id) => {
    try {
      await axios.delete(`${API}/backtests/${id}`);
      await fetchBacktests();
      toast.success("Backtest deleted");
    } catch (e) {
      toast.error("Delete failed");
    }
  };

  const F = ({ label, name, type = "text", half = false }) => (
    <div className={half ? "" : ""}>
      <label className="text-[0.6rem] text-zinc-500 block mb-0.5">{label}</label>
      <input
        type={type}
        value={form[name]}
        onChange={(e) => setForm({ ...form, [name]: e.target.value })}
        className="w-full text-sm py-1 px-2"
        data-testid={`bt-${name}`}
      />
    </div>
  );

  return (
    <div className="widget-panel col-span-1 md:col-span-4 lg:col-span-6" data-testid="backtest-manager">
      <div className="widget-header">
        <h3 className="flex items-center gap-2">
          <FlaskConical className="w-4 h-4 text-[#007AFF]" />
          BACKTEST RESULTS
        </h3>
        <button
          onClick={() => setShowForm(!showForm)}
          className="p-1 hover:bg-white/10 rounded transition-colors"
          data-testid="add-backtest-btn"
        >
          {showForm ? <ChevronUp className="w-4 h-4" /> : <Plus className="w-4 h-4" />}
        </button>
      </div>
      <div className="widget-content">
        {showForm && (
          <form onSubmit={handleSubmit} className="mb-4 p-3 bg-white/5 rounded-sm space-y-2">
            <div className="grid grid-cols-3 gap-2">
              <F label="Strategy" name="strategy_name" />
              <F label="Symbol" name="symbol" />
              <F label="Timeframe" name="timeframe" />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <F label="Period Start" name="period_start" type="date" />
              <F label="Period End" name="period_end" type="date" />
            </div>
            <div className="grid grid-cols-3 gap-2">
              <F label="Total Trades" name="total_trades" type="number" />
              <F label="Winners" name="winning_trades" type="number" />
              <F label="Losers" name="losing_trades" type="number" />
            </div>
            <div className="grid grid-cols-3 gap-2">
              <F label="Profit Factor" name="profit_factor" type="number" />
              <F label="Net Profit ($)" name="net_profit" type="number" />
              <F label="Sharpe Ratio" name="sharpe_ratio" type="number" />
            </div>
            <div className="grid grid-cols-3 gap-2">
              <F label="Max Drawdown ($)" name="max_drawdown" type="number" />
              <F label="Max DD (%)" name="max_drawdown_pct" type="number" />
              <F label="Avg Trade ($)" name="avg_trade" type="number" />
            </div>
            <div className="grid grid-cols-4 gap-2">
              <F label="Avg Win ($)" name="avg_win" type="number" />
              <F label="Avg Loss ($)" name="avg_loss" type="number" />
              <F label="Largest Win ($)" name="largest_win" type="number" />
              <F label="Largest Loss ($)" name="largest_loss" type="number" />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <F label="Max Consec. Wins" name="max_consecutive_wins" type="number" />
              <F label="Max Consec. Losses" name="max_consecutive_losses" type="number" />
            </div>
            <div>
              <label className="text-[0.6rem] text-zinc-500 block mb-0.5">Notes</label>
              <input
                type="text"
                value={form.notes}
                onChange={(e) => setForm({ ...form, notes: e.target.value })}
                className="w-full text-sm py-1 px-2"
                placeholder="e.g. 3.5 months | Session VWAP + Structure"
                data-testid="bt-notes"
              />
            </div>
            <button
              type="submit"
              className="w-full py-2 bg-[#007AFF] text-white text-sm font-bold rounded-sm hover:bg-[#3395FF] transition-colors flex items-center justify-center gap-2"
              data-testid="bt-submit"
            >
              <Save className="w-4 h-4" /> Save Backtest
            </button>
          </form>
        )}

        {/* List */}
        {backtests.length === 0 ? (
          <div className="text-center text-zinc-500 py-6">
            <FlaskConical className="w-6 h-6 mx-auto mb-2 opacity-40" />
            <p className="text-xs">No backtests yet. Paste results from TradingView Strategy Tester.</p>
          </div>
        ) : (
          <div className="space-y-3">
            {backtests.map((bt) => (
              <div key={bt.id} className="p-3 bg-white/5 rounded-sm border border-white/10" data-testid={`bt-item-${bt.id}`}>
                <div className="flex justify-between items-start mb-2">
                  <div>
                    <span className="text-sm font-bold text-white">{bt.strategy_name}</span>
                    <span className="text-xs text-zinc-500 ml-2">{bt.symbol} {bt.timeframe}</span>
                    {bt.is_verified && (
                      <span className="text-[0.6rem] ml-2 px-1.5 py-0.5 bg-[#34C759]/20 text-[#34C759] rounded">VERIFIED</span>
                    )}
                  </div>
                  <button onClick={() => handleDelete(bt.id)} className="p-1 opacity-40 hover:opacity-100" data-testid={`bt-delete-${bt.id}`}>
                    <Trash2 className="w-3 h-3" />
                  </button>
                </div>
                <div className="grid grid-cols-4 gap-2 text-xs font-mono">
                  <div>
                    <span className="text-zinc-500 block">Win Rate</span>
                    <span className="text-[#34C759] font-bold">{bt.win_rate}%</span>
                  </div>
                  <div>
                    <span className="text-zinc-500 block">Profit Factor</span>
                    <span className="text-white font-bold">{bt.profit_factor}</span>
                  </div>
                  <div>
                    <span className="text-zinc-500 block">Net Profit</span>
                    <span className={`font-bold ${bt.net_profit >= 0 ? "text-[#34C759]" : "text-[#FF3B30]"}`}>
                      ${bt.net_profit?.toLocaleString()}
                    </span>
                  </div>
                  <div>
                    <span className="text-zinc-500 block">Sharpe</span>
                    <span className="text-[#007AFF] font-bold">{bt.sharpe_ratio}</span>
                  </div>
                </div>
                {bt.notes && <p className="text-[0.65rem] text-zinc-500 mt-2">{bt.notes}</p>}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default BacktestManager;
