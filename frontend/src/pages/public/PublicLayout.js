import React, { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { Zap, Menu, X } from "lucide-react";

const NAV = [
  { label: "How It Works", to: "/how-it-works" },
  { label: "Academy", to: "/academy" },
  { label: "Membership", to: "/membership" },
  { label: "About", to: "/about" },
  { label: "FAQ", to: "/faq" },
];

const FOOTER = [
  { label: "Reviews", to: "/reviews" },
  { label: "Getting Started", to: "/start" },
  { label: "Risk Disclosure", to: "/risk" },
  { label: "Terms", to: "/terms" },
  { label: "Privacy", to: "/privacy" },
];

export const DISCLAIMER =
  "Educational material only. Futures trading involves substantial risk of loss. MNQ Scalp Stacks is not a broker, not an investment adviser, and does not provide personalized financial advice. Past study results do not predict future results.";

export const usePageMeta = (title, description) => {
  useEffect(() => {
    document.title = title;
    let m = document.querySelector('meta[name="description"]');
    if (!m) {
      m = document.createElement("meta");
      m.name = "description";
      document.head.appendChild(m);
    }
    m.content = description;
    let c = document.querySelector('link[rel="canonical"]');
    if (!c) {
      c = document.createElement("link");
      c.rel = "canonical";
      document.head.appendChild(c);
    }
    c.href = window.location.origin + window.location.pathname;
    window.scrollTo(0, 0);
  }, [title, description]);
};

export const Section = ({ title, children, testid }) => (
  <section className="mb-10" data-testid={testid}>
    {title && <h2 className="text-base md:text-lg font-black tracking-tight text-white mb-4">{title}</h2>}
    {children}
  </section>
);

export const Bullets = ({ items, accent = "#34C759" }) => (
  <ul className="space-y-2">
    {items.map((it) => (
      <li key={typeof it === "string" ? it : it.head} className="flex items-start gap-2.5 text-sm text-zinc-400 leading-relaxed">
        <span className="mt-2 w-1.5 h-1.5 rounded-full shrink-0" style={{ background: accent }} />
        <span>
          {typeof it === "string" ? it : (<><strong className="text-white">{it.head}</strong> {it.body}</>)}
        </span>
      </li>
    ))}
  </ul>
);

export default function PublicLayout({ h1, kicker, children }) {
  const [open, setOpen] = useState(false);
  const { pathname } = useLocation();

  return (
    <div className="min-h-screen bg-[#0A0A0A]" data-testid={`public-page-${pathname.replace(/\//g, "") || "home"}`}>
      <nav className="fixed top-0 w-full z-50 bg-[#0A0A0A]/90 backdrop-blur-xl border-b border-white/5">
        <div className="max-w-5xl mx-auto px-4 md:px-6 h-14 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2" data-testid="public-nav-logo">
            <Zap className="w-5 h-5 text-[#FFCC00]" />
            <span className="font-black text-white text-sm tracking-tight">MNQ SCALP STACKS</span>
          </Link>
          <div className="hidden md:flex items-center gap-5">
            {NAV.map((n) => (
              <Link key={n.to} to={n.to} className={`text-xs transition-colors ${pathname === n.to ? "text-white font-bold" : "text-zinc-500 hover:text-white"}`}>
                {n.label}
              </Link>
            ))}
            <Link to="/membership" className="px-4 py-1.5 bg-[#34C759] text-black text-xs font-black rounded-sm hover:bg-[#2DB84E] transition-colors" data-testid="public-nav-cta">
              Get Access
            </Link>
          </div>
          <button onClick={() => setOpen(!open)} className="md:hidden p-2 text-zinc-400" data-testid="public-nav-menu-btn" aria-label="Menu">
            {open ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
          </button>
        </div>
        {open && (
          <div className="md:hidden border-t border-white/5 bg-[#0A0A0A] px-4 py-3 space-y-1" data-testid="public-nav-mobile">
            {NAV.map((n) => (
              <Link key={n.to} to={n.to} onClick={() => setOpen(false)} className="block py-2.5 text-sm text-zinc-300 hover:text-white">
                {n.label}
              </Link>
            ))}
            <Link to="/membership" onClick={() => setOpen(false)} className="block w-full text-center py-3 mt-2 bg-[#34C759] text-black text-sm font-black rounded-sm">
              Get Access
            </Link>
          </div>
        )}
      </nav>

      <main className="pt-14">
        <header className="px-5 md:px-6 py-10 md:py-14 border-b border-white/5 bg-[#0D0D0D]">
          <div className="max-w-3xl mx-auto">
            {kicker && <p className="text-[0.65rem] font-bold uppercase tracking-[0.25em] text-[#34C759] mb-3">{kicker}</p>}
            <h1 className="text-3xl sm:text-4xl md:text-5xl font-black tracking-tighter text-white leading-tight" data-testid="public-h1">{h1}</h1>
          </div>
        </header>
        <div className="max-w-3xl mx-auto px-5 md:px-6 py-10 md:py-12">{children}</div>
      </main>

      <footer className="border-t border-white/5 bg-[#0A0A0A] px-5 md:px-6 py-8">
        <div className="max-w-3xl mx-auto">
          <div className="flex flex-wrap gap-x-5 gap-y-2 mb-4">
            {FOOTER.map((f) => (
              <Link key={f.to} to={f.to} className="text-xs text-zinc-500 hover:text-zinc-300 transition-colors">{f.label}</Link>
            ))}
            <a href="/dashboard" className="text-xs text-zinc-500 hover:text-zinc-300 transition-colors">Member Dashboard</a>
          </div>
          <p className="text-[0.6rem] leading-relaxed text-zinc-600" data-testid="public-footer-disclaimer">{DISCLAIMER}</p>
        </div>
      </footer>
    </div>
  );
}
