import React, { useState } from "react";
import { Bell, Plus, X } from "lucide-react";
import { formatPrice } from "@/lib/format";

export const AlertsPanel = ({ alerts, onAdd, onDelete }) => {
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
