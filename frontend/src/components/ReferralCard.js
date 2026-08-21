import React, { useEffect, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Gift, Copy, Check, Users } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/** Dashboard referral strip — personal link, 1 friend = 1 month free. */
export const ReferralCard = () => {
  const [info, setInfo] = useState(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    axios.get(`${API}/my/referral`, { withCredentials: true }).then((r) => setInfo(r.data)).catch(() => {});
  }, []);

  if (!info) return null;
  const link = `${window.location.origin}?ref=${info.referral_code}`;

  const copy = () => {
    navigator.clipboard.writeText(link);
    setCopied(true);
    toast.success("Referral link copied — share it!");
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="col-span-1 md:col-span-4 lg:col-span-12 bg-[#0D0D0F] border border-[#FFCC00]/25 rounded-sm p-3 flex flex-wrap items-center gap-3" data-testid="referral-card">
      <span className="flex items-center gap-2 text-xs font-black tracking-wider text-white">
        <Gift className="w-4 h-4 text-[#FFCC00]" /> SHARE &amp; EARN
        <span className="text-[0.55rem] font-mono text-zinc-500 font-normal">1 friend = 1 month free</span>
      </span>
      <div className="flex-1 min-w-[200px] flex items-center gap-2">
        <span className="flex-1 truncate bg-white/5 border border-white/10 rounded-sm px-2.5 py-1.5 text-[0.65rem] font-mono text-zinc-300" data-testid="referral-link">
          {link}
        </span>
        <button
          onClick={copy}
          className="flex items-center gap-1 px-3 py-1.5 bg-[#FFCC00] text-black text-[0.65rem] font-black rounded-sm hover:bg-[#FFCC00]/80 transition-colors shrink-0"
          data-testid="referral-copy-btn"
        >
          {copied ? <Check className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
          {copied ? "COPIED" : "COPY"}
        </button>
      </div>
      <span className="flex items-center gap-1.5 text-[0.6rem] font-mono text-zinc-400" data-testid="referral-stats">
        <Users className="w-3 h-3 text-[#34C759]" />
        {info.referral_count} referred · {info.referral_credits} free month{info.referral_credits === 1 ? "" : "s"} earned
      </span>
    </div>
  );
};

export default ReferralCard;
