import React, { useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Calculator, RefreshCw } from "lucide-react";
import { formatPrice } from "@/lib/format";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export const PositionCalculator = () => {
  const [calcType, setCalcType] = useState("stock"); // stock or mnq
  const [inputs, setInputs] = useState({
    entry_price: "",
    stop_loss: "",
    risk_amount: "30",
    stop_points: "15",
  });
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  const calculateStock = async () => {
    if (!inputs.entry_price || !inputs.stop_loss) return;
    setLoading(true);
    try {
      const res = await axios.post(`${API}/calculator/position-size`, {
        entry_price: parseFloat(inputs.entry_price),
        stop_loss: parseFloat(inputs.stop_loss),
        risk_amount: parseFloat(inputs.risk_amount || 30),
      });
      setResult({ type: "stock", data: res.data });
    } catch (e) {
      console.error("Calc error:", e);
      toast.error("Calculation failed");
    }
    setLoading(false);
  };

  const calculateMNQ = async () => {
    setLoading(true);
    try {
      const res = await axios.post(
        `${API}/calculator/mnq-position?stop_points=${inputs.stop_points || 15}&risk_amount=${inputs.risk_amount || 30}`
      );
      setResult({ type: "mnq", data: res.data });
    } catch (e) {
      console.error("MNQ calc error:", e);
      toast.error("Calculation failed");
    }
    setLoading(false);
  };

  const handleCalculate = () => {
    if (calcType === "stock") {
      calculateStock();
    } else {
      calculateMNQ();
    }
  };

  return (
    <div className="widget-panel col-span-1 md:col-span-2 lg:col-span-4" data-testid="calculator-panel">
      <div className="widget-header">
        <h3 className="flex items-center gap-2">
          <Calculator className="w-4 h-4 text-[#007AFF]" />
          POSITION CALCULATOR
        </h3>
        <div className="flex gap-1">
          <button
            onClick={() => setCalcType("stock")}
            className={`px-2 py-0.5 text-xs rounded-sm transition-colors ${
              calcType === "stock" ? "bg-[#007AFF] text-white" : "bg-white/10 text-zinc-400"
            }`}
            data-testid="calc-type-stock"
          >
            Stock
          </button>
          <button
            onClick={() => setCalcType("mnq")}
            className={`px-2 py-0.5 text-xs rounded-sm transition-colors ${
              calcType === "mnq" ? "bg-[#007AFF] text-white" : "bg-white/10 text-zinc-400"
            }`}
            data-testid="calc-type-mnq"
          >
            MNQ
          </button>
        </div>
      </div>
      <div className="widget-content">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mb-3">
          {calcType === "stock" ? (
            <>
              <div>
                <label className="text-xs text-zinc-500 block mb-1">Entry Price</label>
                <input
                  type="number"
                  step="0.01"
                  value={inputs.entry_price}
                  onChange={(e) => setInputs({ ...inputs, entry_price: e.target.value })}
                  className="w-full text-sm"
                  placeholder="15.50"
                  data-testid="calc-entry-price"
                />
              </div>
              <div>
                <label className="text-xs text-zinc-500 block mb-1">Stop Loss</label>
                <input
                  type="number"
                  step="0.01"
                  value={inputs.stop_loss}
                  onChange={(e) => setInputs({ ...inputs, stop_loss: e.target.value })}
                  className="w-full text-sm"
                  placeholder="14.50"
                  data-testid="calc-stop-loss"
                />
              </div>
            </>
          ) : (
            <div>
              <label className="text-xs text-zinc-500 block mb-1">Stop Points</label>
              <input
                type="number"
                value={inputs.stop_points}
                onChange={(e) => setInputs({ ...inputs, stop_points: e.target.value })}
                className="w-full text-sm"
                placeholder="15"
                data-testid="calc-stop-points"
              />
            </div>
          )}
          <div>
            <label className="text-xs text-zinc-500 block mb-1">Risk Amount ($)</label>
            <input
              type="number"
              value={inputs.risk_amount}
              onChange={(e) => setInputs({ ...inputs, risk_amount: e.target.value })}
              className="w-full text-sm"
              placeholder="30"
              data-testid="calc-risk-amount"
            />
          </div>
          <div className="flex items-end">
            <button
              onClick={handleCalculate}
              disabled={loading}
              className="w-full px-3 py-2 bg-[#007AFF] text-white text-sm font-semibold rounded-sm hover:bg-[#3395FF] transition-colors disabled:opacity-50"
              data-testid="calc-button"
            >
              {loading ? <RefreshCw className="w-4 h-4 animate-spin mx-auto" /> : "Calculate"}
            </button>
          </div>
        </div>

        {/* Results */}
        {result && (
          <div className="bg-white/5 rounded-sm p-3">
            {result.type === "stock" ? (
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <div className="stat-box">
                  <span className="stat-label">Position Size</span>
                  <span className="stat-value text-[#007AFF]" data-testid="calc-result-shares">
                    {result.data.position_size} shares
                  </span>
                </div>
                <div className="stat-box">
                  <span className="stat-label">Total Value</span>
                  <span className="stat-value">${formatPrice(result.data.total_position_value)}</span>
                </div>
                <div className="stat-box">
                  <span className="stat-label">Max Loss</span>
                  <span className="stat-value text-[#FF3B30]">-${formatPrice(result.data.max_loss)}</span>
                </div>
                <div className="stat-box">
                  <span className="stat-label">Risk/Share</span>
                  <span className="stat-value">${result.data.risk_per_share.toFixed(2)}</span>
                </div>
                <div className="stat-box">
                  <span className="stat-label">Target 1:1</span>
                  <span className="stat-value text-[#34C759]">${formatPrice(result.data.target_1r)}</span>
                </div>
                <div className="stat-box">
                  <span className="stat-label">Profit 1:1</span>
                  <span className="stat-value text-[#34C759]">+${formatPrice(result.data.potential_profit_1r)}</span>
                </div>
                <div className="stat-box">
                  <span className="stat-label">Target 1:2</span>
                  <span className="stat-value text-[#34C759] glow-green">${formatPrice(result.data.target_2r)}</span>
                </div>
                <div className="stat-box">
                  <span className="stat-label">Profit 1:2</span>
                  <span className="stat-value text-[#34C759] glow-green">+${formatPrice(result.data.potential_profit_2r)}</span>
                </div>
              </div>
            ) : (
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <div className="stat-box">
                  <span className="stat-label">Contracts</span>
                  <span className="stat-value text-[#007AFF]" data-testid="calc-result-contracts">
                    {result.data.contracts}
                  </span>
                </div>
                <div className="stat-box">
                  <span className="stat-label">Actual Risk</span>
                  <span className="stat-value text-[#FF3B30]">-${formatPrice(result.data.actual_risk)}</span>
                </div>
                <div className="stat-box">
                  <span className="stat-label">Target 1:1</span>
                  <span className="stat-value text-[#34C759]">+{result.data.target_points_1r} pts</span>
                </div>
                <div className="stat-box">
                  <span className="stat-label">Target 1:2</span>
                  <span className="stat-value text-[#34C759] glow-green">+{result.data.target_points_2r} pts</span>
                </div>
                <div className="stat-box">
                  <span className="stat-label">Profit 1:1</span>
                  <span className="stat-value text-[#34C759]">+${formatPrice(result.data.potential_profit_1r)}</span>
                </div>
                <div className="stat-box">
                  <span className="stat-label">Profit 1:2</span>
                  <span className="stat-value text-[#34C759] glow-green">+${formatPrice(result.data.potential_profit_2r)}</span>
                </div>
                <div className="col-span-2 p-2 bg-[#007AFF]/10 rounded-sm border border-[#007AFF]/30">
                  <span className="text-xs text-zinc-400">MNQ = $2/point/contract</span>
                </div>
              </div>
            )}
          </div>
        )}

        {!result && (
          <div className="text-center text-zinc-500 py-4">
            <Calculator className="w-6 h-6 mx-auto mb-2 opacity-50" />
            <p className="text-xs">Enter your trade parameters to calculate position size</p>
            <p className="text-xs mt-1">Based on your $20-$40 risk rule with 1:2 R:R</p>
          </div>
        )}
      </div>
    </div>
  );
};
