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
      } catch { /* ignore */ }
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
          } catch { /* ignore */ }
        };
        ws.onclose = () => {
          setConnected(false);
          if (cancelled) return;
          const delay = Math.min(15000, 1000 * Math.pow(1.6, retryRef.current));
          retryRef.current += 1;
          setTimeout(connect, delay);
        };
        ws.onerror = () => { try { ws.close(); } catch { /* ignore */ } };
      } catch (e) {
        if (!cancelled) setTimeout(connect, 3000);
      }
    };

    connect();

    return () => {
      cancelled = true;
      clearInterval(fallbackTimerRef.current);
      if (wsRef.current) { try { wsRef.current.close(); } catch { /* ignore */ } }
    };
  }, []);

  return { tick, connected };
}
