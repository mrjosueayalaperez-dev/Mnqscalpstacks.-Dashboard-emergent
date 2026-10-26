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
// CME_MINI:MNQ1! is the true contract but TV blocks it in anonymous embeds. Default to the
// proxy and ALWAYS show PROXY_LABEL when the proxy is in use. Override via REACT_APP_TV_SYMBOL
// (e.g. CME_MINI:MNQ1! once a licensed/authenticated embed is available).
export const TV_SYMBOL = process.env.REACT_APP_TV_SYMBOL || "CAPITALCOM:US100";
export const IS_PROXY = TV_SYMBOL !== "CME_MINI:MNQ1!";
export const PROXY_LABEL = IS_PROXY ? "Proxy: US100 CFD (not MNQ futures)" : "CME_MINI:MNQ1!";

export function buildTvEmbedUrl({ interval = "1", hideSideToolbar = true, withDateRanges = false } = {}) {
  const params = new URLSearchParams({
    symbol: TV_SYMBOL,
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
  // Frame 5m to the session; leave 1m at default zoom (recent candles, like the TV app)
  if (interval === "5") params.set("range", "1D");
  // JSON studies array supports per-instance inputs (repeated params can't set two EMA lengths)
  params.set("studies", JSON.stringify([
    { id: "MAExp@tv-basicstudies", inputs: { length: 21 } },
    { id: "VWAP@tv-basicstudies" },
    { id: "Volume@tv-basicstudies" },
  ]));
  params.set("studies_overrides", JSON.stringify({
    "moving average exponential.plot.color": "#FFFFFF",
  }));
  return `https://www.tradingview-widget.com/widgetembed/?${params.toString()}`;
}
