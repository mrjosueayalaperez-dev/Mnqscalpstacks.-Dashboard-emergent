import React, { useState } from "react";
import { Brain, RefreshCw } from "lucide-react";

export const AIAnalysis = ({ onAnalyze, loading, result }) => {
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
