import React, { useEffect, useRef, useState } from "react";
import axios from "axios";
import { Bot, Send } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const getSessionId = () => {
  let id = localStorage.getItem("copilot_session");
  if (!id) {
    id = `cp-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
    localStorage.setItem("copilot_session", id);
  }
  return id;
};

const SUGGESTIONS = ["What's the current setup?", "Explain the active signal", "How's my session going?"];

/** Scalp Copilot — streaming GPT chat with live desk context. */
export const CopilotChat = () => {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [provider, setProvider] = useState(() => localStorage.getItem("copilot_provider") || "gpt");
  const sessionId = useRef(getSessionId());
  const scrollRef = useRef(null);

  const pickProvider = (p) => {
    setProvider(p);
    localStorage.setItem("copilot_provider", p);
  };

  useEffect(() => {
    axios.get(`${API}/copilot/history/${sessionId.current}`)
      .then((r) => setMessages(r.data || []))
      .catch(() => {});
  }, []);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  const send = async (text) => {
    const msg = (text ?? input).trim();
    if (!msg || busy) return;
    setInput("");
    setBusy(true);
    setMessages((m) => [...m, { role: "user", content: msg }, { role: "assistant", content: "" }]);
    try {
      const res = await fetch(`${API}/copilot/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId.current, message: msg, provider }),
      });
      if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`);
      const reader = res.body.getReader();
      const dec = new TextDecoder();
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = dec.decode(value);
        setMessages((m) => {
          const out = [...m];
          out[out.length - 1] = { ...out[out.length - 1], content: out[out.length - 1].content + chunk };
          return out;
        });
      }
    } catch (e) {
      setMessages((m) => {
        const out = [...m];
        out[out.length - 1] = { role: "assistant", content: "Copilot is unavailable right now — try again." };
        return out;
      });
    }
    setBusy(false);
  };

  return (
    <div className="col-span-1 md:col-span-4 lg:col-span-12 bg-[#0D0D0F] border border-[#007AFF]/25 rounded-sm p-3" data-testid="copilot-chat">
      <div className="flex flex-wrap items-center gap-2 mb-2">
        <Bot className="w-4 h-4 text-[#007AFF]" />
        <span className="text-xs font-black tracking-wider text-white">SCALP COPILOT</span>
        <div className="flex rounded-sm border border-white/10 overflow-hidden" data-testid="copilot-provider-toggle">
          <button
            onClick={() => pickProvider("gpt")}
            className={`px-2 py-0.5 text-[0.55rem] font-black transition-colors ${provider === "gpt" ? "bg-[#007AFF] text-white" : "text-zinc-500 hover:text-white"}`}
            data-testid="copilot-provider-gpt"
          >
            GPT
          </button>
          <button
            onClick={() => pickProvider("grok")}
            className={`px-2 py-0.5 text-[0.55rem] font-black transition-colors ${provider === "grok" ? "bg-[#BF5AF2] text-white" : "text-zinc-500 hover:text-white"}`}
            data-testid="copilot-provider-grok"
          >
            GROK
          </button>
        </div>
        <span className="text-[0.55rem] font-mono text-zinc-500">knows your live price, signal &amp; position</span>
      </div>

      <div ref={scrollRef} className="max-h-72 overflow-y-auto space-y-2 mb-2 pr-1" data-testid="copilot-messages">
        {messages.length === 0 && (
          <p className="text-[0.65rem] text-zinc-600 py-2">
            Ask about the current setup, the active signal, your open position, or risk rules. Educational only — not financial advice.
          </p>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
            <div
              className={`max-w-[85%] px-2.5 py-1.5 rounded-sm text-xs leading-relaxed whitespace-pre-wrap ${
                m.role === "user" ? "bg-[#007AFF] text-white" : "bg-white/5 border border-white/10 text-zinc-300"
              }`}
            >
              {m.content || (busy && i === messages.length - 1 ? "…" : "")}
            </div>
          </div>
        ))}
      </div>

      {messages.length === 0 && (
        <div className="flex flex-wrap gap-1.5 mb-2">
          {SUGGESTIONS.map((s) => (
            <button
              key={s}
              onClick={() => send(s)}
              className="px-2 py-1 text-[0.6rem] font-bold text-[#007AFF] border border-[#007AFF]/30 rounded-full hover:bg-[#007AFF]/10 transition-colors"
              data-testid="copilot-suggestion"
            >
              {s}
            </button>
          ))}
        </div>
      )}

      <div className="flex gap-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
          placeholder="Ask the copilot…"
          className="flex-1 bg-white/5 border border-white/10 rounded-sm px-3 py-2 text-xs text-white placeholder-zinc-600 focus:outline-none focus:border-[#007AFF]/50"
          data-testid="copilot-input"
        />
        <button
          onClick={() => send()}
          disabled={busy || !input.trim()}
          className="px-4 py-2 bg-[#007AFF] hover:bg-[#0A84FF] text-white rounded-sm transition-colors disabled:opacity-40"
          data-testid="copilot-send-btn"
        >
          <Send className="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  );
};

export default CopilotChat;
