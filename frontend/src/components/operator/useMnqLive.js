import { useEffect, useRef, useState } from "react";
import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;
const WS_URL = `${BACKEND_URL.replace(/^http/, "ws")}/api/ws/mnq`;

/**
 * useMnqLive — subscribes to the live MNQ tick stream.
 *
 * Strategy: WebSocket primary, REST fallback every 8s in case the socket drops.
 * Auto-reconnects with exponential backoff (capped at 15s).
 *
 * Empty-deps `[]` is intentional: this effect must run exactly once on mount.
 * All captured values are module-level constants (`API`, `WS_URL`), refs, or
 * React-stable setters. Re-running would tear down the live WebSocket every render.
 */
export default function useMnqLive() {
  const [tick, setTick] = useState(null);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef(null);
  const retryRef = useRef(0);
  const fallbackTimerRef = useRef(null);

  useEffect(() => {
    let cancelled = false;

    // REST fallback — runs at slow cadence so we still get data if WS dies
    const restPoll = async () => {
      try {
        const { data } = await axios.get(`${API}/futures/mnq`);
        if (!cancelled) setTick((prev) => prev || data);
      } catch (e) {
        // Network blip — REST poll will retry in 8s. Log only when persistent.
        if (process.env.NODE_ENV !== "production") {
          console.debug("[useMnqLive] REST fallback fetch failed:", e?.message || e);
        }
      }
    };
    restPoll();
    fallbackTimerRef.current = setInterval(restPoll, 8000);

    const connect = () => {
      if (cancelled) return;
      try {
        const ws = new WebSocket(WS_URL);
        wsRef.current = ws;

        ws.onopen = () => {
          setConnected(true);
          retryRef.current = 0;
        };
        ws.onmessage = (ev) => {
          try {
            const data = JSON.parse(ev.data);
            if (data && typeof data.price === "number") setTick(data);
          } catch (e) {
            console.warn("[useMnqLive] malformed WS payload:", e?.message || e);
          }
        };
        ws.onclose = () => {
          setConnected(false);
          if (cancelled) return;
          const delay = Math.min(15000, 1000 * Math.pow(1.6, retryRef.current));
          retryRef.current += 1;
          setTimeout(connect, delay);
        };
        ws.onerror = () => {
          try {
            ws.close();
          } catch (e) {
            console.warn("[useMnqLive] WS close after error failed:", e?.message || e);
          }
        };
      } catch (e) {
        console.warn("[useMnqLive] WS connect threw, retrying in 3s:", e?.message || e);
        if (!cancelled) setTimeout(connect, 3000);
      }
    };

    connect();

    return () => {
      cancelled = true;
      clearInterval(fallbackTimerRef.current);
      if (wsRef.current) {
        try {
          wsRef.current.close();
        } catch (e) {
          // Cleanup race — socket already closed; safe to ignore.
        }
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return { tick, connected };
}
