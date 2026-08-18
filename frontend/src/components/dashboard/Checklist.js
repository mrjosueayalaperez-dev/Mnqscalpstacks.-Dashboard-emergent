import React, { useState } from "react";
import { CheckSquare, Plus } from "lucide-react";

export const Checklist = ({ items, onToggle, onReset, onAdd }) => {
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
    <div className="widget-panel col-span-1 md:col-span-2 lg:col-span-6" data-testid="checklist-panel">
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
