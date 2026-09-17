/**
 * Deterministic TradingView chart URL (direct `widgetembed` iframe).
 *
 * Why not the official embed script (`embed-widget-advanced-chart.js`)?
 * 1. TV blocks CME futures symbols (CME_MINI:MNQ1!) in anonymous embeds —
 *    CAPITALCOM:US100 is a real-time Nasdaq-100 CFD that tracks MNQ 1:1.
 * 2. The script loader nondeterministically ignores `theme: "dark"` in its
 *    fragment config (renders light) and misplaces the iframe below the
 *    container. Query-param `widgetembed` URLs are stable and loader-free.
 */
export function buildTvEmbedUrl({ interval = "1", hideSideToolbar = true, withDateRanges = false } = {}) {
  const params = new URLSearchParams({
    symbol: "CAPITALCOM:US100",
    interval,
    theme: "dark",
    style: "1",
    locale: "en",
    timezone: "America/New_York",
    hidesidetoolbar: hideSideToolbar ? "1" : "0",
    withdateranges: withDateRanges ? "1" : "0",
    allow_symbol_change: "0",
    saveimage: "0",
    hideideas: "1",
  });
  // Frame intraday intervals to the session so setup lines are in view
  if (interval === "1" || interval === "5") params.set("range", "1D");
  // Repeated `studies` params attach overlays (comma lists are ignored).
  params.append("studies", "MAExp@tv-basicstudies");
  params.append("studies", "VWAP@tv-basicstudies");
  // Stack spine: EMA length 21
  params.set("studies_overrides", JSON.stringify({ "moving average exponential.length": 21 }));
  return `https://www.tradingview-widget.com/widgetembed/?${params.toString()}`;
}
