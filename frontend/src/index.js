import React from "react";
import ReactDOM from "react-dom/client";
import "@/index.css";
import App from "@/App";

// Suppress benign cross-origin "Script error." reports from third-party
// iframes (TradingView widget telemetry). Must run before React mounts
// so it beats the CRA dev-overlay listener.
window.addEventListener("error", (e) => {
  const msg = e?.message || "";
  if (msg === "Script error." || (!e?.filename && !e?.error)) {
    e.stopImmediatePropagation();
    e.preventDefault();
  }
}, true);
window.addEventListener("unhandledrejection", (e) => {
  const r = e?.reason;
  if (!r || (typeof r === "object" && Object.keys(r).length === 0)) {
    e.stopImmediatePropagation();
    e.preventDefault();
  }
});

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
