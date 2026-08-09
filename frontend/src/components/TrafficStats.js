import React, { useEffect, useState } from "react";
import axios from "axios";
import { BarChart3, DollarSign, Eye, TrendingUp, Users } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const Stat = ({ icon: Icon, label, value, accent = "text-white", testId }) => (
  <div className="bg-[#121212] border border-white/10 rounded-sm p-3" data-testid={testId}>
    <div className="flex items-center gap-1.5 mb-1">
      <Icon className="w-3.5 h-3.5 text-zinc-500" />
      <span className="text-[0.55rem] uppercase tracking-wider text-zinc-500">{label}</span>
    </div>
    <span className={`text-lg font-black font-mono ${accent}`}>{value}</span>
  </div>
);

/** Owner-only traffic + business KPIs (visitors, users, MRR, conversion). */
export default function TrafficStats() {
  const [stats, setStats] = useState(null);

  useEffect(() => {
    const load = () =>
      axios.get(`${API}/analytics/stats`)
        .then((r) => setStats(r.data))
        .catch((e) => console.error("Analytics stats error:", e));
    load();
    const t = setInterval(load, 30000);
    return () => clearInterval(t);
  }, []);

  if (!stats) return null;

  return (
    <div data-testid="traffic-stats">
      <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-500 mb-2">Traffic & Growth</h3>
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-8 gap-2 mb-4">
        <Stat icon={Eye} label="Unique Visitors" value={stats.visitors_total} testId="stat-visitors-total" />
        <Stat icon={Eye} label="Visitors Today" value={stats.visitors_today} accent="text-[#34C759]" testId="stat-visitors-today" />
        <Stat icon={BarChart3} label="Page Views" value={stats.page_views} testId="stat-page-views" />
        <Stat icon={Users} label="Registered Users" value={stats.total_users} accent="text-[#007AFF]" testId="stat-users" />
        <Stat icon={Users} label="Subscribers" value={stats.total_subscribers} testId="stat-subscribers" />
        <Stat icon={DollarSign} label="Paying (Pro/Elite)" value={`${stats.paying_subscribers} (${stats.pro_count}/${stats.elite_count})`} accent="text-[#FFCC00]" testId="stat-paying" />
        <Stat icon={DollarSign} label="MRR" value={`$${stats.mrr.toLocaleString()}`} accent="text-[#34C759]" testId="stat-mrr" />
        <Stat icon={TrendingUp} label="Conversion" value={`${stats.conversion_rate}%`} testId="stat-conversion" />
      </div>
    </div>
  );
}
