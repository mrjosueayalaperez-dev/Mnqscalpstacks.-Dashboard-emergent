import React, { useEffect, useState } from "react";
import { BadgeCheck, Play, X } from "lucide-react";

const BACKEND = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND}/api`;

const isVideo = (shot) => (shot.content_type || "").startsWith("video/");

/** Lightbox overlay for a single proof shot. */
const Lightbox = ({ shot, onClose }) => (
  <div
    className="fixed inset-0 z-[100] bg-black/90 backdrop-blur-sm flex items-center justify-center p-4"
    onClick={onClose}
    data-testid="proof-lightbox"
  >
    <button
      className="absolute top-4 right-4 p-2 bg-white/10 rounded-sm hover:bg-white/20 transition-colors"
      onClick={onClose}
      data-testid="proof-lightbox-close"
    >
      <X className="w-5 h-5 text-white" />
    </button>
    <figure className="max-w-5xl max-h-[90vh] flex flex-col items-center" onClick={(e) => e.stopPropagation()}>
      {isVideo(shot) ? (
        <video
          src={`${BACKEND}${shot.url}`}
          controls
          autoPlay
          className="max-h-[80vh] w-auto rounded-sm border border-white/10"
          data-testid="proof-lightbox-video"
        />
      ) : (
        <img
          src={`${BACKEND}${shot.url}`}
          alt={shot.caption || "Trading proof"}
          className="max-h-[80vh] w-auto object-contain rounded-sm border border-white/10"
        />
      )}
      {shot.caption && (
        <figcaption className="mt-3 text-sm text-zinc-300 font-mono text-center">{shot.caption}</figcaption>
      )}
    </figure>
  </div>
);

/**
 * ProofGallery — "Verified Results" landing section. Real trade receipts
 * uploaded via the admin panel, served from /api/proof.
 */
export default function ProofGallery() {
  const [shots, setShots] = useState([]);
  const [active, setActive] = useState(null);

  useEffect(() => {
    fetch(`${API}/proof/list`)
      .then((r) => r.json())
      .then((d) => setShots(d.shots || []))
      .catch((e) => console.error("Proof fetch error:", e));
  }, []);

  if (shots.length === 0) return null;

  return (
    <section className="py-14 md:py-20 px-5 md:px-6 bg-[#0D0D0D]" data-testid="proof-section">
      <div className="max-w-6xl mx-auto">
        <div className="flex items-center gap-2 mb-2">
          <BadgeCheck className="w-5 h-5 text-[#34C759]" />
          <span className="text-[0.65rem] font-black tracking-[0.25em] text-[#34C759] uppercase">Receipts, Not Promises</span>
        </div>
        <h2 className="text-base md:text-lg font-black text-white mb-1">VERIFIED RESULTS — REAL TRADE PROOF</h2>
        <p className="text-sm text-zinc-500 mb-8 max-w-xl">
          Actual account screenshots and closed Micro E-mini Nasdaq-100 positions. Tap any shot to inspect the fills.
        </p>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {shots.map((s) => (
            <button
              key={s.id}
              onClick={() => setActive(s)}
              className="group relative bg-[#121212] border border-white/10 rounded-sm overflow-hidden text-left hover:border-[#34C759]/40 transition-colors"
              data-testid={`proof-shot-${s.id}`}
            >
              <div className="h-56 md:h-64 overflow-hidden relative">
                {isVideo(s) ? (
                  <>
                    <video
                      src={`${BACKEND}${s.url}`}
                      muted
                      playsInline
                      preload="metadata"
                      className="w-full h-full object-cover object-top"
                    />
                    <span className="absolute inset-0 flex items-center justify-center">
                      <span className="w-12 h-12 rounded-full bg-black/60 border border-white/30 flex items-center justify-center group-hover:scale-110 transition-transform">
                        <Play className="w-5 h-5 text-white ml-0.5" />
                      </span>
                    </span>
                  </>
                ) : (
                  <img
                    src={`${BACKEND}${s.url}`}
                    alt={s.caption || "Trading proof"}
                    loading="lazy"
                    className="w-full h-full object-cover object-top group-hover:scale-[1.03] transition-transform duration-300"
                  />
                )}
              </div>
              <div className="flex items-center gap-2 px-3 py-2 border-t border-white/5">
                <BadgeCheck className="w-3.5 h-3.5 text-[#34C759] shrink-0" />
                <span className="text-[0.65rem] text-zinc-400 font-mono truncate">{s.caption || "Verified trade proof"}</span>
              </div>
            </button>
          ))}
        </div>
      </div>

      {active && <Lightbox shot={active} onClose={() => setActive(null)} />}
    </section>
  );
}
