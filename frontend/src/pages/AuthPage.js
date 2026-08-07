import React, { useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { Activity, LogIn, UserPlus } from "lucide-react";
import { useAuth, formatApiErrorDetail } from "@/context/AuthContext";

export default function AuthPage() {
  const [mode, setMode] = useState("login");
  const [form, setForm] = useState({ email: "", password: "", name: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const { login, register } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const from = location.state?.from || "/dashboard";

  const handleGoogle = () => {
    // REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
    const redirectUrl = window.location.origin + "/dashboard";
    window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      if (mode === "login") {
        await login(form.email, form.password);
      } else {
        await register(form.email, form.password, form.name);
      }
      navigate(from, { replace: true });
    } catch (err) {
      setError(formatApiErrorDetail(err.response?.data?.detail) || err.message);
    }
    setBusy(false);
  };

  return (
    <div className="min-h-screen bg-[#0A0A0A] flex items-center justify-center px-4" data-testid="auth-page">
      <div className="w-full max-w-sm">
        <div className="flex items-center justify-center gap-2 mb-6">
          <Activity className="w-6 h-6 text-[#007AFF]" />
          <h1 className="text-lg font-black tracking-tight text-white">MNQ SCALP STACKS</h1>
        </div>

        <div className="bg-[#121212] border border-white/10 rounded-sm p-6">
          {/* Mode tabs */}
          <div className="flex gap-1 mb-5 bg-white/5 p-1 rounded-sm">
            <button
              onClick={() => { setMode("login"); setError(""); }}
              className={`flex-1 py-1.5 text-xs font-black tracking-wider rounded-sm transition-colors ${mode === "login" ? "bg-[#007AFF] text-white" : "text-zinc-400 hover:text-white"}`}
              data-testid="auth-tab-login"
            >
              SIGN IN
            </button>
            <button
              onClick={() => { setMode("register"); setError(""); }}
              className={`flex-1 py-1.5 text-xs font-black tracking-wider rounded-sm transition-colors ${mode === "register" ? "bg-[#007AFF] text-white" : "text-zinc-400 hover:text-white"}`}
              data-testid="auth-tab-register"
            >
              CREATE ACCOUNT
            </button>
          </div>

          {/* Google */}
          <button
            onClick={handleGoogle}
            className="w-full flex items-center justify-center gap-2 py-2.5 bg-white text-black text-sm font-bold rounded-sm hover:bg-zinc-200 transition-colors mb-4"
            data-testid="auth-google-btn"
          >
            <svg className="w-4 h-4" viewBox="0 0 24 24"><path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.27-4.74 3.27-8.1z"/><path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/><path fill="#FBBC05" d="M5.84 14.1A7.2 7.2 0 0 1 5.46 12c0-.73.13-1.44.38-2.1V7.06H2.18A11 11 0 0 0 1 12c0 1.77.43 3.45 1.18 4.94l3.66-2.84z"/><path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"/></svg>
            Continue with Google
          </button>

          <div className="flex items-center gap-3 mb-4">
            <div className="flex-1 h-px bg-white/10" />
            <span className="text-[0.6rem] text-zinc-600 uppercase tracking-wider">or with email</span>
            <div className="flex-1 h-px bg-white/10" />
          </div>

          {/* Email form */}
          <form onSubmit={handleSubmit} className="space-y-3">
            {mode === "register" && (
              <input
                type="text"
                placeholder="Your name"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                className="w-full text-sm"
                data-testid="auth-name-input"
              />
            )}
            <input
              type="email"
              required
              placeholder="Email"
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
              className="w-full text-sm"
              data-testid="auth-email-input"
            />
            <input
              type="password"
              required
              placeholder="Password (min 6 characters)"
              value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })}
              className="w-full text-sm"
              data-testid="auth-password-input"
            />
            {error && (
              <p className="text-xs text-[#FF3B30] bg-[#FF3B30]/10 border border-[#FF3B30]/30 rounded-sm px-3 py-2" data-testid="auth-error">
                {error}
              </p>
            )}
            <button
              type="submit"
              disabled={busy}
              className="w-full flex items-center justify-center gap-2 py-2.5 bg-[#34C759] text-black text-sm font-black rounded-sm hover:bg-[#2DB84E] transition-colors disabled:opacity-50"
              data-testid="auth-submit-btn"
            >
              {mode === "login" ? <LogIn className="w-4 h-4" /> : <UserPlus className="w-4 h-4" />}
              {busy ? "Please wait…" : mode === "login" ? "Sign In" : "Create Account"}
            </button>
          </form>
        </div>

        <p className="text-center text-[0.65rem] text-zinc-600 mt-4">
          <a href="/" className="hover:text-zinc-400 transition-colors">← Back to landing page</a>
        </p>
      </div>
    </div>
  );
}
