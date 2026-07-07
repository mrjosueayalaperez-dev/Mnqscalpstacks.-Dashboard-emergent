import React, { useCallback, useEffect, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Cable, Download, Radio } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/**
 * AtiBridgePanel — Phase 2 NinjaTrader ATI routing control.
 * Toggle live OIF routing, monitor the local bridge heartbeat, configure
 * account / contract / default ATM template, download the bridge script.
 */
export default function AtiBridgePanel() {
  const [status, setStatus] = useState(null);
  const [form, setForm] = useState({ account: "", instrument: "", atm_template: "" });
  const [dirty, setDirty] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const { data } = await axios.get(`${API}/ati/status`);
      setStatus(data);
      setForm((f) =>
        dirty ? f : { account: data.account, instrument: data.instrument, atm_template: data.atm_template }
      );
    } catch (e) {
      console.warn("[ATI] status failed:", e?.message || e);
    }
  }, [dirty]);

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 5000);
    return () => clearInterval(t);
  }, [refresh]);

  const sendConfig = useCallback(async (patch) => {
    try {
      const { data } = await axios.post(`${API}/ati/config`, patch);
      setStatus(data);
      setDirty(false);
      toast.success("ATI config updated");
    } catch (e) {
      toast.error("ATI config failed", { description: e.response?.data?.detail });
    }
  }, []);

  const enabled = status?.enabled;
  const online = status?.bridge_online;

  return (
    <div className="border border-white/10 bg-[#0D0D0F] rounded-sm" data-testid="ati-bridge-panel">
      <div className="flex items-center justify-between px-3 py-2 border-b border-white/10">
        <div className="flex items-center gap-2">
          <Cable className="w-3.5 h-3.5 text-[#BF5AF2]" />
          <span className="text-[0.6rem] font-black tracking-[0.15em] text-white">NINJATRADER ATI — PHASE 2</span>
        </div>
        <div className="flex items-center gap-1.5" data-testid="ati-bridge-status">
          <span className={`w-1.5 h-1.5 rounded-full ${online ? "bg-[#34C759] animate-pulse" : "bg-[#FF3B30]"}`} />
          <span className={`text-[0.5rem] font-bold tracking-wider ${online ? "text-[#34C759]" : "text-[#FF3B30]"}`}>
            BRIDGE {online ? "ONLINE" : "OFFLINE"}
          </span>
        </div>
      </div>

      <div className="p-3 space-y-2.5">
        {/* Live routing master toggle */}
        <button
          onClick={() => sendConfig({ enabled: !enabled })}
          data-testid="ati-toggle-btn"
          className={`w-full py-2 rounded-sm text-[0.65rem] font-black tracking-widest transition-colors flex items-center justify-center gap-2 ${
            enabled
              ? "bg-[#BF5AF2]/20 border border-[#BF5AF2]/60 text-[#BF5AF2]"
              : "bg-white/5 border border-white/15 text-zinc-400 hover:bg-white/10"
          }`}
        >
          <Radio className="w-3.5 h-3.5" />
          {enabled ? "LIVE ROUTING ARMED" : "SIMULATOR ONLY — TAP TO ARM"}
        </button>

        {/* Config fields */}
        <div className="grid grid-cols-2 gap-2">
          <label className="block">
            <span className="text-[0.5rem] uppercase tracking-wider text-zinc-500">Account</span>
            <input
              value={form.account}
              onChange={(e) => { setForm({ ...form, account: e.target.value }); setDirty(true); }}
              className="w-full text-xs font-mono mt-0.5"
              data-testid="ati-account-input"
            />
          </label>
          <label className="block">
            <span className="text-[0.5rem] uppercase tracking-wider text-zinc-500">Contract</span>
            <input
              value={form.instrument}
              onChange={(e) => { setForm({ ...form, instrument: e.target.value }); setDirty(true); }}
              className="w-full text-xs font-mono mt-0.5"
              data-testid="ati-instrument-input"
            />
          </label>
        </div>
        <label className="block">
          <span className="text-[0.5rem] uppercase tracking-wider text-zinc-500">Default ATM Template (blank = preset name)</span>
          <input
            value={form.atm_template}
            onChange={(e) => { setForm({ ...form, atm_template: e.target.value }); setDirty(true); }}
            placeholder="e.g. SNIPE_2R"
            className="w-full text-xs font-mono mt-0.5"
            data-testid="ati-atm-input"
          />
        </label>
        {dirty && (
          <button
            onClick={() => sendConfig(form)}
            className="w-full py-1.5 bg-[#007AFF] hover:bg-[#3395FF] text-white text-[0.6rem] font-black tracking-wider rounded-sm transition-colors"
            data-testid="ati-save-btn"
          >
            SAVE CONFIG
          </button>
        )}

        {/* Queue stats + bridge download */}
        <div className="flex items-center justify-between text-[0.55rem] font-mono text-zinc-500">
          <span data-testid="ati-queue-stats">
            QUEUE <span className="text-[#FFCC00]">{status?.pending ?? 0}</span> pending ·{" "}
            <span className="text-[#34C759]">{status?.dispatched ?? 0}</span> sent
          </span>
          <a
            href={`${API}/ati/bridge-script`}
            className="flex items-center gap-1 text-[#007AFF] hover:text-[#3395FF] transition-colors"
            data-testid="ati-download-bridge"
          >
            <Download className="w-3 h-3" /> bridge script
          </a>
        </div>
      </div>
    </div>
  );
}
