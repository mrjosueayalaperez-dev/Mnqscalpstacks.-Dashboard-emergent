import React, { useState, useEffect, useCallback } from "react";
import "@/App.css";
import axios from "axios";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { Toaster, toast } from "sonner";
import SignalDashboard from "@/components/SignalDashboard";
import PerformancePage from "@/components/PerformancePage";
import {
  TrendingUp,
  TrendingDown,
  Activity,
  Target,
  List,
  BarChart3,
  Brain,
  Bell,
  CheckSquare,
  Plus,
  X,
  RefreshCw,
  Search,
  ChevronRight,
  DollarSign,
  Clock,
  AlertTriangle,
  Calculator,
} from "lucide-react";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

// ============== Helper Functions ==============
const formatPrice = (price) => {
  if (typeof price !== "number") return "0.00";
  return price.toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
};

const formatVolume = (vol) => {
  if (!vol) return "0";
  if (vol >= 1000000) return (vol / 1000000).toFixed(1) + "M";
  if (vol >= 1000) return (vol / 1000).toFixed(1) + "K";
  return vol.toString();
};

// ============== Components ==============

// Header Component
const Header = ({ onRefresh, lastUpdate }) => (
  <header
    className="h-14 border-b border-white/10 bg-[#0A0A0A]/90 backdrop-blur-xl flex items-center justify-between px-4 sticky top-0 z-50"
    data-testid="main-header"
  >
    <div className="flex items-center gap-3">
      <Activity className="w-6 h-6 text-[#007AFF]" />
      <h1 className="text-lg font-black tracking-tight">
        TRADING COMMAND CENTER
      </h1>
    </div>
    <div className="flex items-center gap-4">
      <a
        href="/performance"
        className="flex items-center gap-1 px-2.5 py-1 text-xs bg-[#FFCC00]/15 text-[#FFCC00] rounded-sm hover:bg-[#FFCC00]/25 transition-colors font-bold"
        data-testid="performance-link"
      >
        <BarChart3 className="w-3 h-3" />
        Performance
      </a>
      <span className="text-xs text-zinc-500 font-mono">
        {lastUpdate ? `Updated: ${lastUpdate}` : "Loading..."}
      </span>
      <button
        onClick={onRefresh}
        className="p-2 hover:bg-white/5 rounded transition-colors"
        data-testid="refresh-all-btn"
      >
        <RefreshCw className="w-4 h-4 text-zinc-400" />
      </button>
    </div>
  </header>
);

// MNQ Tracker Component
const MNQTracker = ({ data, loading }) => {
  const isPositive = data?.change >= 0;

  return (
    <div className="widget-panel col-span-1 md:col-span-2 lg:col-span-4" data-testid="mnq-tracker">
      <div className="widget-header">
        <h3 className="flex items-center gap-2">
          <BarChart3 className="w-4 h-4 text-[#007AFF]" />
          MNQ FUTURES
        </h3>
        <span className="text-xs text-zinc-500">Micro E-mini Nasdaq-100</span>
      </div>
      <div className="widget-content">
        {loading ? (
          <div className="flex items-center justify-center h-32">
            <RefreshCw className="w-6 h-6 text-zinc-500 animate-spin" />
          </div>
        ) : (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className="stat-box">
              <span className="stat-label">Price</span>
              <span
                className={`stat-value ${
                  isPositive ? "text-[#34C759] glow-green" : "text-[#FF3B30] glow-red"
                }`}
                data-testid="mnq-price"
              >
                {formatPrice(data?.price)}
              </span>
            </div>
            <div className="stat-box">
              <span className="stat-label">Change</span>
              <span
                className={`stat-value text-lg ${
                  isPositive ? "text-[#34C759]" : "text-[#FF3B30]"
                }`}
              >
                {isPositive ? "+" : ""}
                {formatPrice(data?.change)} ({data?.change_percent || "0"}%)
              </span>
            </div>
            <div className="stat-box">
              <span className="stat-label">VWAP</span>
              <span className="stat-value text-lg text-[#007AFF]">
                {formatPrice(data?.vwap)}
              </span>
            </div>
            <div className="stat-box">
              <span className="stat-label">RSI (14)</span>
              <span
                className={`stat-value text-lg ${
                  data?.rsi > 70
                    ? "text-[#FF3B30]"
                    : data?.rsi < 30
                    ? "text-[#34C759]"
                    : "text-white"
                }`}
              >
                {data?.rsi?.toFixed(1) || "50.0"}
              </span>
            </div>
            <div className="stat-box">
              <span className="stat-label">EMA 9</span>
              <span className="stat-value text-lg">{formatPrice(data?.ema9)}</span>
            </div>
            <div className="stat-box">
              <span className="stat-label">EMA 21</span>
              <span className="stat-value text-lg">{formatPrice(data?.ema21)}</span>
            </div>
            <div className="stat-box">
              <span className="stat-label">High</span>
              <span className="stat-value text-lg text-[#34C759]">
                {formatPrice(data?.high)}
              </span>
            </div>
            <div className="stat-box">
              <span className="stat-label">Low</span>
              <span className="stat-value text-lg text-[#FF3B30]">
                {formatPrice(data?.low)}
              </span>
            </div>
          </div>
        )}
        {/* Signal Indicator */}
        {data && (
          <div className="mt-4 p-3 bg-white/5 rounded-sm border border-white/10">
            <div className="flex items-center justify-between">
              <span className="text-xs uppercase tracking-wider text-zinc-500">
                Setup Signal
              </span>
              {data?.ema9 > data?.ema21 && data?.rsi > 50 ? (
                <span className="flex items-center gap-2 text-[#34C759] text-sm font-bold">
                  <TrendingUp className="w-4 h-4" /> BULLISH SETUP
                </span>
              ) : data?.ema9 < data?.ema21 && data?.rsi < 50 ? (
                <span className="flex items-center gap-2 text-[#FF3B30] text-sm font-bold">
                  <TrendingDown className="w-4 h-4" /> BEARISH SETUP
                </span>
              ) : (
                <span className="flex items-center gap-2 text-[#FFCC00] text-sm font-bold">
                  <AlertTriangle className="w-4 h-4" /> NO CLEAR SETUP
                </span>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

// Watchlist Component
const Watchlist = ({ items, onRemove, onAdd, quotes }) => {
  const [showAdd, setShowAdd] = useState(false);
  const [newSymbol, setNewSymbol] = useState("");
  const [newName, setNewName] = useState("");

  const handleAdd = async () => {
    if (newSymbol && newName) {
      await onAdd({ symbol: newSymbol.toUpperCase(), name: newName });
      setNewSymbol("");
      setNewName("");
      setShowAdd(false);
    }
  };

  return (
    <div className="widget-panel col-span-1 md:col-span-2 lg:col-span-4" data-testid="watchlist-panel">
      <div className="widget-header">
        <h3 className="flex items-center gap-2">
          <Target className="w-4 h-4 text-[#007AFF]" />
          WATCHLIST
        </h3>
        <button
          onClick={() => setShowAdd(!showAdd)}
          className="p-1 hover:bg-white/10 rounded transition-colors"
          data-testid="add-watchlist-btn"
        >
          <Plus className="w-4 h-4" />
        </button>
      </div>
      <div className="widget-content">
        {showAdd && (
          <div className="flex gap-2 mb-3 p-2 bg-white/5 rounded-sm">
            <input
              type="text"
              placeholder="Symbol"
              value={newSymbol}
              onChange={(e) => setNewSymbol(e.target.value)}
              className="flex-1 text-sm"
              data-testid="watchlist-symbol-input"
            />
            <input
              type="text"
              placeholder="Name"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              className="flex-1 text-sm"
              data-testid="watchlist-name-input"
            />
            <button
              onClick={handleAdd}
              className="px-3 py-1 bg-[#007AFF] text-white text-sm rounded-sm hover:bg-[#3395FF] transition-colors"
              data-testid="watchlist-add-confirm-btn"
            >
              Add
            </button>
          </div>
        )}
        <table className="data-table">
          <thead>
            <tr>
              <th>Symbol</th>
              <th>Price</th>
              <th>Change</th>
              <th>Volume</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => {
              const quote = quotes[item.symbol] || {};
              const isPositive = parseFloat(quote.change_percent || 0) >= 0;
              return (
                <tr key={item.id} data-testid={`watchlist-item-${item.symbol.toLowerCase()}`}>
                  <td>
                    <div className="flex flex-col">
                      <span className="font-semibold text-white">{item.symbol}</span>
                      <span className="text-xs text-zinc-500">{item.name}</span>
                    </div>
                  </td>
                  <td className="font-mono">${formatPrice(quote.price)}</td>
                  <td
                    className={`font-mono ${
                      isPositive ? "text-[#34C759]" : "text-[#FF3B30]"
                    }`}
                  >
                    {isPositive ? "+" : ""}
                    {quote.change_percent || "0"}%
                  </td>
                  <td className="font-mono text-zinc-400">
                    {formatVolume(quote.volume)}
                  </td>
                  <td>
                    <button
                      onClick={() => onRemove(item.id)}
                      className="p-1 hover:bg-white/10 rounded opacity-50 hover:opacity-100 transition-all"
                      data-testid={`remove-watchlist-${item.symbol.toLowerCase()}`}
                    >
                      <X className="w-3 h-3" />
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};

// Stock Scanner Component
const StockScanner = ({ results, onScan, loading }) => (
  <div className="widget-panel col-span-1 md:col-span-2 lg:col-span-4" data-testid="scanner-panel">
    <div className="widget-header">
      <h3 className="flex items-center gap-2">
        <Search className="w-4 h-4 text-[#007AFF]" />
        SCANNER
      </h3>
      <button
        onClick={onScan}
        disabled={loading}
        className="flex items-center gap-1 px-2 py-1 text-xs bg-[#007AFF]/20 text-[#007AFF] rounded-sm hover:bg-[#007AFF]/30 transition-colors"
        data-testid="run-scanner-btn"
      >
        {loading ? <RefreshCw className="w-3 h-3 animate-spin" /> : <Search className="w-3 h-3" />}
        Scan
      </button>
    </div>
    <div className="widget-content">
      {results.length === 0 ? (
        <div className="text-center text-zinc-500 py-8">
          <Search className="w-8 h-8 mx-auto mb-2 opacity-50" />
          <p className="text-sm">Run scanner to find breakouts</p>
        </div>
      ) : (
        <div className="space-y-2">
          {results.map((stock, idx) => (
            <div
              key={idx}
              className={`flex items-center justify-between p-2 rounded-sm border ${
                stock.alert_type === "breakout"
                  ? "border-[#34C759]/30 bg-[#34C759]/5"
                  : "border-[#FF3B30]/30 bg-[#FF3B30]/5"
              }`}
              data-testid={`scanner-result-${stock.symbol.toLowerCase()}`}
            >
              <div className="flex items-center gap-3">
                {stock.alert_type === "breakout" ? (
                  <TrendingUp className="w-5 h-5 text-[#34C759]" />
                ) : (
                  <TrendingDown className="w-5 h-5 text-[#FF3B30]" />
                )}
                <div>
                  <span className="font-bold text-white">{stock.symbol}</span>
                  <span
                    className={`ml-2 text-sm font-mono ${
                      stock.alert_type === "breakout" ? "text-[#34C759]" : "text-[#FF3B30]"
                    }`}
                  >
                    {parseFloat(stock.change_percent) >= 0 ? "+" : ""}
                    {stock.change_percent}%
                  </span>
                </div>
              </div>
              <div className="text-right">
                <span className="font-mono text-white">${formatPrice(stock.price)}</span>
                <span className="block text-xs text-zinc-500">
                  Vol: {formatVolume(stock.volume)}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  </div>
);

// Trade Journal Component
const TradeJournal = ({ trades, stats, onAddTrade, onCloseTrade }) => {
  const [showAdd, setShowAdd] = useState(false);
  const [newTrade, setNewTrade] = useState({
    symbol: "",
    entry_price: "",
    quantity: "",
    side: "long",
    notes: "",
  });

  const handleSubmit = async () => {
    if (newTrade.symbol && newTrade.entry_price && newTrade.quantity) {
      await onAddTrade({
        ...newTrade,
        entry_price: parseFloat(newTrade.entry_price),
        quantity: parseInt(newTrade.quantity),
      });
      setNewTrade({ symbol: "", entry_price: "", quantity: "", side: "long", notes: "" });
      setShowAdd(false);
    }
  };

  return (
    <div className="widget-panel col-span-1 md:col-span-4 lg:col-span-6" data-testid="journal-panel">
      <div className="widget-header">
        <h3 className="flex items-center gap-2">
          <List className="w-4 h-4 text-[#007AFF]" />
          TRADE JOURNAL
        </h3>
        <button
          onClick={() => setShowAdd(!showAdd)}
          className="p-1 hover:bg-white/10 rounded transition-colors"
          data-testid="add-trade-btn"
        >
          <Plus className="w-4 h-4" />
        </button>
      </div>
      <div className="widget-content">
        {/* Stats Row */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mb-4">
          <div className="stat-box">
            <span className="stat-label">Total P&L</span>
            <span
              className={`stat-value ${
                stats.total_pnl >= 0 ? "text-[#34C759]" : "text-[#FF3B30]"
              }`}
              data-testid="total-pnl"
            >
              {stats.total_pnl >= 0 ? "+" : ""}${formatPrice(stats.total_pnl)}
            </span>
          </div>
          <div className="stat-box">
            <span className="stat-label">Win Rate</span>
            <span className="stat-value" data-testid="win-rate">{stats.win_rate}%</span>
          </div>
          <div className="stat-box">
            <span className="stat-label">Avg Win</span>
            <span className="stat-value text-[#34C759]">+${formatPrice(stats.avg_win)}</span>
          </div>
          <div className="stat-box">
            <span className="stat-label">Avg Loss</span>
            <span className="stat-value text-[#FF3B30]">${formatPrice(stats.avg_loss)}</span>
          </div>
        </div>

        {/* Add Trade Form */}
        {showAdd && (
          <div className="grid grid-cols-2 md:grid-cols-5 gap-2 mb-4 p-3 bg-white/5 rounded-sm">
            <input
              type="text"
              placeholder="Symbol"
              value={newTrade.symbol}
              onChange={(e) => setNewTrade({ ...newTrade, symbol: e.target.value.toUpperCase() })}
              className="text-sm"
              data-testid="trade-symbol-input"
            />
            <input
              type="number"
              placeholder="Entry Price"
              value={newTrade.entry_price}
              onChange={(e) => setNewTrade({ ...newTrade, entry_price: e.target.value })}
              className="text-sm"
              data-testid="trade-entry-price-input"
            />
            <input
              type="number"
              placeholder="Qty"
              value={newTrade.quantity}
              onChange={(e) => setNewTrade({ ...newTrade, quantity: e.target.value })}
              className="text-sm"
              data-testid="trade-quantity-input"
            />
            <select
              value={newTrade.side}
              onChange={(e) => setNewTrade({ ...newTrade, side: e.target.value })}
              className="text-sm"
              data-testid="trade-side-select"
            >
              <option value="long">Long</option>
              <option value="short">Short</option>
            </select>
            <button
              onClick={handleSubmit}
              className="btn-buy text-sm"
              data-testid="submit-trade-btn"
            >
              Log Trade
            </button>
          </div>
        )}

        {/* Trades Table */}
        <table className="data-table">
          <thead>
            <tr>
              <th>Symbol</th>
              <th>Side</th>
              <th>Entry</th>
              <th>Exit</th>
              <th>Qty</th>
              <th>P&L</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {trades.slice(0, 10).map((trade) => (
              <tr key={trade.id} data-testid={`trade-row-${trade.id}`}>
                <td className="font-semibold text-white">{trade.symbol}</td>
                <td>
                  <span
                    className={`px-2 py-0.5 text-xs rounded ${
                      trade.side === "long"
                        ? "bg-[#34C759]/20 text-[#34C759]"
                        : "bg-[#FF3B30]/20 text-[#FF3B30]"
                    }`}
                  >
                    {trade.side.toUpperCase()}
                  </span>
                </td>
                <td>${formatPrice(trade.entry_price)}</td>
                <td>{trade.exit_price ? `$${formatPrice(trade.exit_price)}` : "-"}</td>
                <td>{trade.quantity}</td>
                <td
                  className={
                    trade.pnl
                      ? trade.pnl >= 0
                        ? "text-[#34C759]"
                        : "text-[#FF3B30]"
                      : ""
                  }
                >
                  {trade.pnl ? `${trade.pnl >= 0 ? "+" : ""}$${formatPrice(trade.pnl)}` : "-"}
                </td>
                <td>
                  {trade.status === "open" ? (
                    <button
                      onClick={() => {
                        const exitPrice = prompt("Enter exit price:");
                        if (exitPrice) {
                          onCloseTrade(trade.id, parseFloat(exitPrice));
                        }
                      }}
                      className="text-xs px-2 py-1 bg-[#FFCC00]/20 text-[#FFCC00] rounded hover:bg-[#FFCC00]/30 transition-colors"
                      data-testid={`close-trade-${trade.id}`}
                    >
                      Close
                    </button>
                  ) : (
                    <span className="text-xs text-zinc-500">Closed</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

// Checklist Component
const Checklist = ({ items, onToggle, onReset, onAdd }) => {
  const [newItem, setNewItem] = useState("");
  const categories = ["premarket", "rules", "postmarket"];
  const completedCount = items.filter((i) => i.completed).length;
  const progress = items.length > 0 ? (completedCount / items.length) * 100 : 0;

  const handleAdd = async () => {
    if (newItem) {
      await onAdd({ text: newItem, category: "rules" });
      setNewItem("");
    }
  };

  return (
    <div className="widget-panel col-span-1 md:col-span-2 lg:col-span-3" data-testid="checklist-panel">
      <div className="widget-header">
        <h3 className="flex items-center gap-2">
          <CheckSquare className="w-4 h-4 text-[#007AFF]" />
          DAILY CHECKLIST
        </h3>
        <button
          onClick={onReset}
          className="text-xs text-zinc-500 hover:text-white transition-colors"
          data-testid="reset-checklist-btn"
        >
          Reset
        </button>
      </div>
      <div className="widget-content">
        {/* Progress Bar */}
        <div className="mb-4">
          <div className="flex justify-between text-xs mb-1">
            <span className="text-zinc-500">Progress</span>
            <span className="font-mono">
              {completedCount}/{items.length}
            </span>
          </div>
          <div className="h-1.5 bg-white/10 rounded-full overflow-hidden">
            <div
              className="h-full bg-[#34C759] transition-all duration-300"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>

        {/* Add New Item */}
        <div className="flex gap-2 mb-3">
          <input
            type="text"
            placeholder="Add new rule..."
            value={newItem}
            onChange={(e) => setNewItem(e.target.value)}
            className="flex-1 text-sm"
            data-testid="checklist-input"
          />
          <button
            onClick={handleAdd}
            className="px-2 py-1 bg-[#007AFF]/20 text-[#007AFF] rounded-sm hover:bg-[#007AFF]/30 transition-colors"
            data-testid="checklist-add-btn"
          >
            <Plus className="w-4 h-4" />
          </button>
        </div>

        {/* Checklist Items by Category */}
        {categories.map((cat) => {
          const catItems = items.filter((i) => i.category === cat);
          if (catItems.length === 0) return null;
          return (
            <div key={cat} className="mb-3">
              <h4 className="text-xs uppercase tracking-wider text-zinc-500 mb-2">
                {cat === "premarket" ? "Pre-Market" : cat === "postmarket" ? "Post-Market" : "Trading Rules"}
              </h4>
              <div className="space-y-1">
                {catItems.map((item) => (
                  <div
                    key={item.id}
                    className={`checklist-item ${item.completed ? "completed" : ""}`}
                    data-testid={`checklist-item-${item.id}`}
                  >
                    <button
                      onClick={() => onToggle(item.id, !item.completed)}
                      className={`w-4 h-4 rounded-sm border flex items-center justify-center transition-colors ${
                        item.completed
                          ? "bg-[#34C759] border-[#34C759]"
                          : "border-zinc-600 hover:border-[#007AFF]"
                      }`}
                      data-testid={`toggle-checklist-${item.id}`}
                    >
                      {item.completed && (
                        <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                        </svg>
                      )}
                    </button>
                    <span className="text-sm">{item.text}</span>
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

// AI Analysis Component
const AIAnalysis = ({ onAnalyze, loading, result }) => {
  const [symbol, setSymbol] = useState("MNQ");
  const [analysisType, setAnalysisType] = useState("general");

  return (
    <div className="widget-panel col-span-1 md:col-span-2 lg:col-span-3" data-testid="ai-panel">
      <div className="widget-header">
        <h3 className="flex items-center gap-2">
          <Brain className="w-4 h-4 text-[#007AFF]" />
          AI ANALYSIS
        </h3>
      </div>
      <div className="widget-content">
        <div className="flex gap-2 mb-3">
          <input
            type="text"
            placeholder="Symbol"
            value={symbol}
            onChange={(e) => setSymbol(e.target.value.toUpperCase())}
            className="w-24 text-sm"
            data-testid="ai-symbol-input"
          />
          <select
            value={analysisType}
            onChange={(e) => setAnalysisType(e.target.value)}
            className="flex-1 text-sm"
            data-testid="ai-type-select"
          >
            <option value="general">General Analysis</option>
            <option value="entry">Entry Signal</option>
            <option value="exit">Exit Signal</option>
            <option value="sentiment">Sentiment</option>
          </select>
          <button
            onClick={() => onAnalyze(symbol, analysisType)}
            disabled={loading}
            className="px-3 py-1 bg-[#007AFF] text-white text-sm rounded-sm hover:bg-[#3395FF] transition-colors disabled:opacity-50"
            data-testid="run-ai-btn"
          >
            {loading ? <RefreshCw className="w-4 h-4 animate-spin" /> : "Analyze"}
          </button>
        </div>

        {/* Result Display */}
        <div className="bg-white/5 rounded-sm p-3 min-h-[150px] max-h-[300px] overflow-y-auto">
          {loading ? (
            <div className="flex flex-col items-center justify-center h-32">
              <RefreshCw className="w-6 h-6 text-[#007AFF] animate-spin mb-2" />
              <span className="text-sm text-zinc-500">Analyzing {symbol}...</span>
            </div>
          ) : result ? (
            <div className="text-sm leading-relaxed whitespace-pre-wrap" data-testid="ai-result">
              {result.analysis}
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center h-32 text-zinc-500">
              <Brain className="w-8 h-8 mb-2 opacity-50" />
              <span className="text-sm">Enter a symbol and click Analyze</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

// Position Sizing Calculator Component
const PositionCalculator = () => {
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

// Alerts Component
const AlertsPanel = ({ alerts, onAdd, onDelete }) => {
  const [showAdd, setShowAdd] = useState(false);
  const [newAlert, setNewAlert] = useState({
    symbol: "",
    alert_type: "breakout",
    condition: "above",
    target_value: "",
  });

  const handleAdd = async () => {
    if (newAlert.symbol && newAlert.target_value) {
      await onAdd({
        ...newAlert,
        target_value: parseFloat(newAlert.target_value),
      });
      setNewAlert({ symbol: "", alert_type: "breakout", condition: "above", target_value: "" });
      setShowAdd(false);
    }
  };

  return (
    <div className="widget-panel col-span-1 md:col-span-2 lg:col-span-2" data-testid="alerts-panel">
      <div className="widget-header">
        <h3 className="flex items-center gap-2">
          <Bell className="w-4 h-4 text-[#007AFF]" />
          ALERTS
        </h3>
        <button
          onClick={() => setShowAdd(!showAdd)}
          className="p-1 hover:bg-white/10 rounded transition-colors"
          data-testid="add-alert-btn"
        >
          <Plus className="w-4 h-4" />
        </button>
      </div>
      <div className="widget-content">
        {showAdd && (
          <div className="space-y-2 mb-3 p-2 bg-white/5 rounded-sm">
            <input
              type="text"
              placeholder="Symbol"
              value={newAlert.symbol}
              onChange={(e) => setNewAlert({ ...newAlert, symbol: e.target.value.toUpperCase() })}
              className="w-full text-sm"
              data-testid="alert-symbol-input"
            />
            <div className="flex gap-2">
              <select
                value={newAlert.alert_type}
                onChange={(e) => setNewAlert({ ...newAlert, alert_type: e.target.value })}
                className="flex-1 text-sm"
                data-testid="alert-type-select"
              >
                <option value="breakout">Breakout</option>
                <option value="vwap_cross">VWAP Cross</option>
                <option value="price_target">Price Target</option>
                <option value="stop_loss">Stop Loss</option>
              </select>
              <select
                value={newAlert.condition}
                onChange={(e) => setNewAlert({ ...newAlert, condition: e.target.value })}
                className="flex-1 text-sm"
                data-testid="alert-condition-select"
              >
                <option value="above">Above</option>
                <option value="below">Below</option>
              </select>
            </div>
            <div className="flex gap-2">
              <input
                type="number"
                placeholder="Price"
                value={newAlert.target_value}
                onChange={(e) => setNewAlert({ ...newAlert, target_value: e.target.value })}
                className="flex-1 text-sm"
                data-testid="alert-price-input"
              />
              <button
                onClick={handleAdd}
                className="px-3 py-1 bg-[#007AFF] text-white text-sm rounded-sm hover:bg-[#3395FF] transition-colors"
                data-testid="submit-alert-btn"
              >
                Add
              </button>
            </div>
          </div>
        )}

        {alerts.length === 0 ? (
          <div className="text-center text-zinc-500 py-6">
            <Bell className="w-6 h-6 mx-auto mb-2 opacity-50" />
            <span className="text-xs">No active alerts</span>
          </div>
        ) : (
          <div className="space-y-2">
            {alerts.map((alert) => (
              <div
                key={alert.id}
                className="flex items-center justify-between p-2 bg-white/5 rounded-sm"
                data-testid={`alert-item-${alert.id}`}
              >
                <div>
                  <span className="font-bold text-white">{alert.symbol}</span>
                  <span className="text-xs text-zinc-500 ml-2">
                    {alert.condition} ${formatPrice(alert.target_value)}
                  </span>
                </div>
                <button
                  onClick={() => onDelete(alert.id)}
                  className="p-1 hover:bg-white/10 rounded opacity-50 hover:opacity-100"
                  data-testid={`delete-alert-${alert.id}`}
                >
                  <X className="w-3 h-3" />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

// ============== Main App ==============
function App() {
  // State
  const [mnqData, setMnqData] = useState(null);
  const [watchlist, setWatchlist] = useState([]);
  const [quotes, setQuotes] = useState({});
  const [scanResults, setScanResults] = useState([]);
  const [trades, setTrades] = useState([]);
  const [tradeStats, setTradeStats] = useState({
    total_trades: 0,
    winning_trades: 0,
    losing_trades: 0,
    win_rate: 0,
    total_pnl: 0,
    avg_win: 0,
    avg_loss: 0,
  });
  const [checklist, setChecklist] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [aiResult, setAiResult] = useState(null);
  const [lastUpdate, setLastUpdate] = useState(null);

  // Loading states
  const [loading, setLoading] = useState({
    mnq: false,
    scan: false,
    ai: false,
  });

  // Fetch functions
  const fetchMNQData = useCallback(async () => {
    setLoading((l) => ({ ...l, mnq: true }));
    try {
      const res = await axios.get(`${API}/futures/mnq`);
      setMnqData(res.data);
    } catch (e) {
      console.error("Error fetching MNQ:", e);
    }
    setLoading((l) => ({ ...l, mnq: false }));
  }, []);

  const fetchWatchlist = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/watchlist`);
      setWatchlist(res.data);
      // Fetch quotes for each
      res.data.forEach(async (item) => {
        if (item.category !== "futures") {
          const quoteRes = await axios.get(`${API}/stocks/quote/${item.symbol}`);
          setQuotes((q) => ({ ...q, [item.symbol]: quoteRes.data }));
        }
      });
    } catch (e) {
      console.error("Error fetching watchlist:", e);
    }
  }, []);

  const fetchTrades = useCallback(async () => {
    try {
      const [tradesRes, statsRes] = await Promise.all([
        axios.get(`${API}/trades`),
        axios.get(`${API}/trades/stats`),
      ]);
      setTrades(tradesRes.data);
      setTradeStats(statsRes.data);
    } catch (e) {
      console.error("Error fetching trades:", e);
    }
  }, []);

  const fetchChecklist = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/checklist`);
      setChecklist(res.data);
    } catch (e) {
      console.error("Error fetching checklist:", e);
    }
  }, []);

  const fetchAlerts = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/alerts`);
      setAlerts(res.data);
    } catch (e) {
      console.error("Error fetching alerts:", e);
    }
  }, []);

  const seedData = useCallback(async () => {
    try {
      await axios.post(`${API}/seed`);
      await Promise.all([fetchWatchlist(), fetchChecklist()]);
      toast.success("Data initialized!");
    } catch (e) {
      console.error("Error seeding:", e);
    }
  }, [fetchWatchlist, fetchChecklist]);

  // Initial load
  useEffect(() => {
    const init = async () => {
      await Promise.all([
        fetchMNQData(),
        fetchWatchlist(),
        fetchTrades(),
        fetchChecklist(),
        fetchAlerts(),
      ]);
      setLastUpdate(new Date().toLocaleTimeString());
    };
    init();

    // Auto-refresh every 30 seconds
    const interval = setInterval(() => {
      fetchMNQData();
      fetchWatchlist();
      setLastUpdate(new Date().toLocaleTimeString());
    }, 30000);

    return () => clearInterval(interval);
  }, [fetchMNQData, fetchWatchlist, fetchTrades, fetchChecklist, fetchAlerts]);

  // Check if we need to seed
  useEffect(() => {
    if (watchlist.length === 0 && checklist.length === 0) {
      seedData();
    }
  }, [watchlist.length, checklist.length, seedData]);

  // Action handlers
  const handleRefreshAll = async () => {
    await Promise.all([
      fetchMNQData(),
      fetchWatchlist(),
      fetchTrades(),
      fetchChecklist(),
      fetchAlerts(),
    ]);
    setLastUpdate(new Date().toLocaleTimeString());
    toast.success("Data refreshed!");
  };

  const handleScan = async () => {
    setLoading((l) => ({ ...l, scan: true }));
    try {
      const res = await axios.get(`${API}/stocks/scanner`);
      setScanResults(res.data.scanners || []);
      if (res.data.scanners?.length > 0) {
        res.data.scanners.forEach((s) => {
          toast(
            <div className="flex items-center gap-2">
              {s.alert_type === "breakout" ? (
                <TrendingUp className="w-4 h-4 text-[#34C759]" />
              ) : (
                <TrendingDown className="w-4 h-4 text-[#FF3B30]" />
              )}
              <span>
                <strong>{s.symbol}</strong> {s.alert_type} detected!{" "}
                {parseFloat(s.change_percent) >= 0 ? "+" : ""}
                {s.change_percent}%
              </span>
            </div>,
            {
              className:
                s.alert_type === "breakout" ? "alert-toast-bullish" : "alert-toast-bearish",
            }
          );
        });
      }
    } catch (e) {
      console.error("Error scanning:", e);
      toast.error("Scanner failed");
    }
    setLoading((l) => ({ ...l, scan: false }));
  };

  const handleAddWatchlist = async (item) => {
    try {
      await axios.post(`${API}/watchlist`, item);
      await fetchWatchlist();
      toast.success(`Added ${item.symbol} to watchlist`);
    } catch (e) {
      console.error("Error adding to watchlist:", e);
      toast.error("Failed to add");
    }
  };

  const handleRemoveWatchlist = async (id) => {
    try {
      await axios.delete(`${API}/watchlist/${id}`);
      await fetchWatchlist();
    } catch (e) {
      console.error("Error removing:", e);
    }
  };

  const handleAddTrade = async (trade) => {
    try {
      await axios.post(`${API}/trades`, trade);
      await fetchTrades();
      toast.success(`Logged ${trade.side} on ${trade.symbol}`);
    } catch (e) {
      console.error("Error adding trade:", e);
      toast.error("Failed to log trade");
    }
  };

  const handleCloseTrade = async (id, exitPrice) => {
    try {
      await axios.patch(`${API}/trades/${id}`, {
        exit_price: exitPrice,
        status: "closed",
      });
      await fetchTrades();
      toast.success("Trade closed");
    } catch (e) {
      console.error("Error closing trade:", e);
      toast.error("Failed to close trade");
    }
  };

  const handleToggleChecklist = async (id, completed) => {
    try {
      await axios.patch(`${API}/checklist/${id}?completed=${completed}`);
      setChecklist((items) =>
        items.map((item) => (item.id === id ? { ...item, completed } : item))
      );
    } catch (e) {
      console.error("Error toggling:", e);
    }
  };

  const handleResetChecklist = async () => {
    try {
      await axios.post(`${API}/checklist/reset`);
      await fetchChecklist();
      toast.success("Checklist reset");
    } catch (e) {
      console.error("Error resetting:", e);
    }
  };

  const handleAddChecklist = async (item) => {
    try {
      await axios.post(`${API}/checklist`, item);
      await fetchChecklist();
    } catch (e) {
      console.error("Error adding checklist:", e);
    }
  };

  const handleAddAlert = async (alert) => {
    try {
      await axios.post(`${API}/alerts`, alert);
      await fetchAlerts();
      toast.success(`Alert set for ${alert.symbol}`);
    } catch (e) {
      console.error("Error adding alert:", e);
      toast.error("Failed to add alert");
    }
  };

  const handleDeleteAlert = async (id) => {
    try {
      await axios.delete(`${API}/alerts/${id}`);
      await fetchAlerts();
    } catch (e) {
      console.error("Error deleting alert:", e);
    }
  };

  const handleAIAnalyze = async (symbol, type) => {
    setLoading((l) => ({ ...l, ai: true }));
    setAiResult(null);
    try {
      const res = await axios.post(`${API}/ai/analyze`, {
        symbol,
        analysis_type: type,
      });
      setAiResult(res.data);
    } catch (e) {
      console.error("Error analyzing:", e);
      toast.error("AI analysis failed");
    }
    setLoading((l) => ({ ...l, ai: false }));
  };

  return (
    <div className="min-h-screen bg-[#0A0A0A]" data-testid="trading-app">
      <Toaster
        position="top-right"
        toastOptions={{
          style: {
            background: "#121212",
            border: "1px solid rgba(255,255,255,0.1)",
            color: "#fff",
          },
        }}
      />
      <Header onRefresh={handleRefreshAll} lastUpdate={lastUpdate} />

      <main className="p-4">
        <div className="grid grid-cols-1 md:grid-cols-4 lg:grid-cols-12 gap-4">
          {/* MNQ Tracker - Full width on mobile, 4 cols on lg */}
          <MNQTracker data={mnqData} loading={loading.mnq} />

          {/* Signal Engine Dashboard */}
          <SignalDashboard />

          {/* Watchlist */}
          <Watchlist
            items={watchlist}
            quotes={quotes}
            onRemove={handleRemoveWatchlist}
            onAdd={handleAddWatchlist}
          />

          {/* Scanner */}
          <StockScanner
            results={scanResults}
            onScan={handleScan}
            loading={loading.scan}
          />

          {/* Trade Journal - Takes more space */}
          <TradeJournal
            trades={trades}
            stats={tradeStats}
            onAddTrade={handleAddTrade}
            onCloseTrade={handleCloseTrade}
          />

          {/* Checklist */}
          <Checklist
            items={checklist}
            onToggle={handleToggleChecklist}
            onReset={handleResetChecklist}
            onAdd={handleAddChecklist}
          />

          {/* AI Analysis */}
          <AIAnalysis
            onAnalyze={handleAIAnalyze}
            loading={loading.ai}
            result={aiResult}
          />

          {/* Alerts */}
          <AlertsPanel
            alerts={alerts}
            onAdd={handleAddAlert}
            onDelete={handleDeleteAlert}
          />

          {/* Position Calculator */}
          <PositionCalculator />
        </div>
      </main>
    </div>
  );
}

function AppRouter() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<App />} />
        <Route path="/performance" element={<PerformancePage />} />
      </Routes>
    </BrowserRouter>
  );
}

export default AppRouter;
