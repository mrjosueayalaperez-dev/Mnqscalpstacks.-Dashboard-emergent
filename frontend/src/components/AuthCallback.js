import React, { useEffect, useRef, useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";

/** Processes #session_id= from Emergent Google OAuth, then enters the dashboard. */
export default function AuthCallback() {
  const hasProcessed = useRef(false);
  const [error, setError] = useState("");
  const { googleSession } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    if (hasProcessed.current) return;
    hasProcessed.current = true;

    const hash = location.hash || "";
    const match = hash.match(/session_id=([^&]+)/);
    if (!match) {
      navigate("/auth", { replace: true });
      return;
    }
    (async () => {
      try {
        const user = await googleSession(match[1]);
        window.history.replaceState(null, "", window.location.pathname);
        navigate("/dashboard", { replace: true, state: { user } });
      } catch (e) {
        setError("Google sign-in failed. Please try again.");
        setTimeout(() => navigate("/auth", { replace: true }), 2500);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="min-h-screen bg-[#0A0A0A] flex items-center justify-center" data-testid="auth-callback">
      <div className="text-center">
        <div className="w-8 h-8 border-2 border-[#007AFF] border-t-transparent rounded-full animate-spin mx-auto mb-3" />
        <p className="text-sm text-zinc-400">{error || "Signing you in…"}</p>
      </div>
    </div>
  );
}
