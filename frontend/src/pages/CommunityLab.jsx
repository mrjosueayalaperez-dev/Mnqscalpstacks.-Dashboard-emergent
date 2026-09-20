import React, { useEffect } from "react";
import { Link } from "react-router-dom";
import { Zap, ArrowLeft } from "lucide-react";

/** Community Lab — free education module served as a self-contained page (public/community-lab.html). */
export default function CommunityLab() {
  useEffect(() => {
    document.title = "Community Lab — MNQ Scalp Stacks";
  }, []);

  return (
    <div className="h-screen flex flex-col bg-[#07090e]" data-testid="community-lab-page">
      <div className="flex items-center justify-between gap-3 px-4 h-12 border-b border-white/10 bg-[#0A0A0A] flex-shrink-0">
        <div className="flex items-center gap-3 min-w-0">
          <Link to="/" className="flex items-center gap-2 text-white" data-testid="community-lab-home-link">
            <Zap className="w-4 h-4 text-[#34C759]" />
            <span className="text-xs font-black tracking-wider whitespace-nowrap">MNQ SCALP STACKS</span>
          </Link>
          <span className="hidden sm:inline text-[0.6rem] font-mono uppercase tracking-widest text-zinc-500">
            Community Lab · free practice module
          </span>
        </div>
        <div className="flex items-center gap-2">
          <Link
            to="/"
            className="flex items-center gap-1 px-2.5 py-1.5 text-[0.65rem] font-bold text-zinc-400 hover:text-white transition-colors"
            data-testid="community-lab-back-btn"
          >
            <ArrowLeft className="w-3 h-3" /> Back to site
          </Link>
          <Link
            to="/membership"
            className="px-3 py-1.5 bg-[#34C759] text-black text-[0.65rem] font-black rounded-sm hover:bg-[#2DB84E] transition-colors"
            data-testid="community-lab-join-btn"
          >
            JOIN MEMBERSHIP
          </Link>
        </div>
      </div>
      <iframe
        title="MNQ Scalp Stacks Community Lab"
        src="/community-lab.html"
        className="flex-1 w-full border-0"
        data-testid="community-lab-iframe"
      />
    </div>
  );
}
