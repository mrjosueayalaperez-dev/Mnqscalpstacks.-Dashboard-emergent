import React, { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Zap, ArrowLeft, Lock } from "lucide-react";
import { useAuth } from "@/context/AuthContext";

const LOCKED_SECTIONS = {
  edge: "Edge Lab",
  practice: "Trade Path",
  stack: "Stack Lab",
  observe: "Watch & Learn",
  journal: "Practice Journal",
  progress: "Progress",
};
const PAID_TIERS = ["pro", "premium", "elite"];

/** Community Lab — free education module; advanced sections gated behind Pro/Elite. */
export default function CommunityLab() {
  const { user } = useAuth();
  const iframeRef = useRef(null);
  const [lockedHash, setLockedHash] = useState(null);
  const paid = !!user && (PAID_TIERS.includes(user.tier) || ["admin", "owner"].includes(user.role));

  useEffect(() => {
    document.title = "Community Lab — MNQ Scalp Stacks";
  }, []);

  // Same-origin iframe: watch its hash and gate advanced sections for free users
  useEffect(() => {
    if (paid) {
      setLockedHash(null);
      return undefined;
    }
    const t = setInterval(() => {
      try {
        const h = (iframeRef.current?.contentWindow?.location?.hash || "").replace("#", "");
        setLockedHash(LOCKED_SECTIONS[h] ? h : null);
      } catch { /* iframe not ready */ }
    }, 500);
    return () => clearInterval(t);
  }, [paid]);

  const backToFree = () => {
    try { iframeRef.current.contentWindow.location.hash = "#home"; } catch { /* noop */ }
    setLockedHash(null);
  };

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
      <div className="relative flex-1">
        <iframe
          ref={iframeRef}
          title="MNQ Scalp Stacks Community Lab"
          src="/community-lab.html"
          className="absolute inset-0 w-full h-full border-0"
          data-testid="community-lab-iframe"
        />
        {lockedHash && (
          <div
            className="absolute inset-0 z-20 flex items-center justify-center bg-[#07090e]/85 backdrop-blur-md p-6"
            data-testid="community-lab-lock-overlay"
          >
            <div className="max-w-md w-full bg-[#0D1420] border border-[#5eead4]/25 rounded-sm p-8 text-center">
              <div className="w-12 h-12 mx-auto rounded-full bg-[#5eead4]/10 border border-[#5eead4]/30 flex items-center justify-center mb-4">
                <Lock className="w-5 h-5 text-[#5eead4]" />
              </div>
              <h2 className="text-xl font-black text-white mb-2">
                {LOCKED_SECTIONS[lockedHash]} is a member section
              </h2>
              <p className="text-sm text-zinc-400 leading-relaxed mb-6">
                Probability Lab, Coins to Markets and the Learning Center are free forever. The applied tools —
                Edge Lab, Trade Path, Stack Lab, Watch &amp; Learn, Journal and Progress — unlock with any
                Pro, Premium or Elite membership.
              </p>
              <div className="flex flex-col gap-2">
                <Link
                  to="/membership"
                  className="w-full px-4 py-3 bg-[#34C759] text-black text-sm font-black rounded-sm hover:bg-[#2DB84E] transition-colors"
                  data-testid="lab-lock-upgrade-btn"
                >
                  UNLOCK WITH MEMBERSHIP
                </Link>
                {!user && (
                  <Link
                    to="/auth"
                    className="w-full px-4 py-2.5 border border-white/15 text-zinc-300 text-xs font-bold rounded-sm hover:bg-white/5 transition-colors"
                    data-testid="lab-lock-login-btn"
                  >
                    ALREADY A MEMBER? LOG IN
                  </Link>
                )}
                <button
                  onClick={backToFree}
                  className="w-full px-4 py-2 text-[0.65rem] font-bold text-zinc-500 hover:text-zinc-300 transition-colors"
                  data-testid="lab-lock-back-btn"
                >
                  ← Back to the free sections
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
