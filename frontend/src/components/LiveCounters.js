import React, { useEffect, useState } from "react";
import { Eye, Users } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/** Public social-proof strip: traders on board + site visitors. */
export default function LiveCounters() {
  const [data, setData] = useState(null);

  useEffect(() => {
    fetch(`${API}/analytics/public`)
      .then((r) => r.json())
      .then(setData)
      .catch(() => {});
  }, []);

  if (!data) return null;

  return (
    <div className="flex items-center justify-center gap-6 py-3 border-y border-white/5 bg-[#0D0D0D]" data-testid="live-counters">
      <span className="flex items-center gap-1.5 text-[0.65rem] font-mono text-zinc-400">
        <span className="w-1.5 h-1.5 rounded-full bg-[#34C759] animate-pulse" />
        <Users className="w-3 h-3 text-[#34C759]" />
        <span className="text-[#34C759] font-bold" data-testid="counter-traders">{data.traders.toLocaleString()}</span>
        traders on board
      </span>
      <span className="flex items-center gap-1.5 text-[0.65rem] font-mono text-zinc-400">
        <Eye className="w-3 h-3 text-[#007AFF]" />
        <span className="text-[#007AFF] font-bold" data-testid="counter-visitors">{data.visitors.toLocaleString()}</span>
        visitors
      </span>
    </div>
  );
}
