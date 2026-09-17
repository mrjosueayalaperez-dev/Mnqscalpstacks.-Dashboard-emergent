import React, { useEffect, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Users } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const TIERS = ["free", "pro", "premium", "elite"];

const tierCls = (tier) =>
  tier === "elite" ? "bg-[#FFCC00]/15 text-[#FFCC00]"
    : tier === "premium" ? "bg-[#BF5AF2]/15 text-[#BF5AF2]"
    : tier === "pro" ? "bg-[#34C759]/15 text-[#34C759]"
    : "bg-white/10 text-zinc-400";

const fmtDate = (iso) => (iso ? new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" }) : "—");

/** Admin users table — who your members actually are, with one-tap tier editing. */
export default function UsersTable() {
  const [users, setUsers] = useState([]);

  useEffect(() => {
    axios.get(`${API}/analytics/users`)
      .then((r) => setUsers(r.data.users || []))
      .catch((e) => console.error("Users fetch error:", e));
  }, []);

  const setTier = async (email, tier) => {
    try {
      await axios.patch(`${API}/analytics/users/tier`, { email, tier }, { withCredentials: true });
      setUsers((us) => us.map((u) => (u.email === email ? { ...u, tier } : u)));
      toast.success(`${email} → ${tier.toUpperCase()}`);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Tier update failed");
    }
  };

  return (
    <div className="bg-[#121212] border border-white/10 rounded-sm p-4" data-testid="users-table">
      <h3 className="flex items-center gap-2 text-sm font-black text-white mb-3">
        <Users className="w-4 h-4 text-[#007AFF]" />
        REGISTERED USERS ({users.length})
      </h3>
      {users.length === 0 ? (
        <p className="text-xs text-zinc-600">No registered users yet.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead>
              <tr className="text-[0.55rem] uppercase tracking-wider text-zinc-500 border-b border-white/10">
                <th className="py-2 pr-3">Email</th>
                <th className="py-2 pr-3">Name</th>
                <th className="py-2 pr-3">Tier</th>
                <th className="py-2 pr-3">Role</th>
                <th className="py-2 pr-3">Joined</th>
                <th className="py-2">Last Login</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.user_id} className="border-b border-white/5 text-xs" data-testid={`user-row-${u.user_id}`}>
                  <td className="py-2 pr-3 font-mono text-white">{u.email}</td>
                  <td className="py-2 pr-3 text-zinc-400">{u.name || "—"}</td>
                  <td className="py-2 pr-3">
                    <select
                      value={u.tier}
                      onChange={(e) => setTier(u.email, e.target.value)}
                      className={`px-1.5 py-1 rounded-sm text-[0.6rem] font-black uppercase border border-white/10 bg-[#0A0A0A] cursor-pointer ${tierCls(u.tier)}`}
                      data-testid={`tier-select-${u.user_id}`}
                    >
                      {TIERS.map((t) => (
                        <option key={t} value={t} className="bg-[#0A0A0A] text-white">{t.toUpperCase()}</option>
                      ))}
                    </select>
                  </td>
                  <td className="py-2 pr-3 text-zinc-400">{u.role === "admin" ? <span className="text-[#BF5AF2] font-bold">ADMIN</span> : "user"}</td>
                  <td className="py-2 pr-3 text-zinc-500 font-mono">{fmtDate(u.created_at)}</td>
                  <td className="py-2 text-zinc-500 font-mono">{fmtDate(u.last_login)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
