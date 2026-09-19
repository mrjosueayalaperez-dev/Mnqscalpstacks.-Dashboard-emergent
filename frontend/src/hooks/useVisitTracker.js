import { useEffect } from "react";
import { useLocation } from "react-router-dom";
import axios from "axios";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

function visitorId() {
  let id = localStorage.getItem("ss_vid");
  if (!id) {
    id = (crypto.randomUUID ? crypto.randomUUID() : `v_${Date.now()}_${Math.random().toString(36).slice(2)}`);
    localStorage.setItem("ss_vid", id);
  }
  return id;
}

/** Fires one visit ping per path per browser session. */
export default function useVisitTracker() {
  const location = useLocation();

  useEffect(() => {
    const key = `ss_visited_${location.pathname}`;
    if (sessionStorage.getItem(key)) return;
    sessionStorage.setItem(key, "1");
    axios.post(`${API}/analytics/visit`, { visitor_id: visitorId(), path: location.pathname })
      .catch(() => sessionStorage.removeItem(key));
  }, [location.pathname]);

  // Presence heartbeat — powers the admin "Online Now" counter
  useEffect(() => {
    const ping = () =>
      axios.post(`${API}/analytics/heartbeat`, { visitor_id: visitorId(), path: window.location.pathname }).catch(() => {});
    ping();
    const t = setInterval(ping, 60000);
    return () => clearInterval(t);
  }, []);
}
