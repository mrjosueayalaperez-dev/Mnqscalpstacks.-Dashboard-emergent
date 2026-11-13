// MNQ Scalp Stacks - TradingView webhook receiver (Vercel serverless)
// Phase 2 (PR version): validate the Vercel-side secret, then forward the
// alert server-side to the Emergent backend endpoint, which remains the
// single code path for the kill switch, per-action semantics (BUY/SELL
// cards, HOLD log, CLOSE expiry, PRICE tape update) and database writes.
//
// Secrets and the upstream URL are env-only, never in client code:
//   SIGNAL_WEBHOOK_SECRET   - the NEW secret TradingView sends to Vercel
//   EMERGENT_WEBHOOK_SECRET - the CURRENT secret the backend expects
//   UPSTREAM_WEBHOOK_URL    - optional; default is the Emergent signals URL
// This route adds no labels of its own; cards are created by the backend's
// own pipeline with its native labeling. No trading execution happens here.
const crypto = require('crypto');

// Default stays on Emergent so current production behavior does not change
// until a server-only UPSTREAM_WEBHOOK_URL is set (for example after the
// FastAPI backend moves off Emergent). Never put this value in REACT_APP_*.
const DEFAULT_UPSTREAM_URL = 'https://mnq-scalp-stack.emergent.host/api/signals/tradingview';
const UPSTREAM_TIMEOUT_MS = 8000;

function getUpstreamUrl(env) {
  const raw = String(((env || process.env).UPSTREAM_WEBHOOK_URL) || '').trim();
  return raw || DEFAULT_UPSTREAM_URL;
}

function redact(value) {
  return String(value || '').replace(/https?:\/\/[^\s]+/gi, '[REDACTED_URL]');
}

function upstreamUrlOverridden(env) {
  return String(((env || process.env).UPSTREAM_WEBHOOK_URL) || '').trim().length > 0;
}

function safeEqual(a, b) {
  const ba = Buffer.from(String(a));
  const bb = Buffer.from(String(b));
  if (ba.length !== bb.length) return false;
  return crypto.timingSafeEqual(ba, bb);
}

async function handler(req, res) {
  const secret = process.env.SIGNAL_WEBHOOK_SECRET || '';
  const upstreamSecret = process.env.EMERGENT_WEBHOOK_SECRET || '';

  if (req.method === 'GET') {
    return res.status(200).json({
      ok: true,
      receiver: 'vercel',
      mode: 'forward',
      secret_configured: secret.length > 0,
      upstream_configured: upstreamSecret.length > 0,
      // Boolean only — never echo the upstream URL or any secret.
      upstream_url_overridden: upstreamUrlOverridden(),
      ts: new Date().toISOString(),
    });
  }

  if (req.method !== 'POST') {
    return res.status(405).json({ ok: false, error: 'method_not_allowed' });
  }

  if (!secret) {
    console.error('webhook: SIGNAL_WEBHOOK_SECRET not configured');
    return res.status(503).json({ ok: false, error: 'secret_not_configured' });
  }

  let body = req.body;
  if (typeof body === 'string') {
    try { body = JSON.parse(body); } catch (e) { body = {}; }
  }
  body = body || {};

  const provided = body.secret || req.headers['x-webhook-secret'] || '';
  if (!safeEqual(provided, secret)) {
    console.warn('webhook: rejected POST (bad or missing secret)');
    return res.status(401).json({ ok: false, error: 'bad_or_missing_secret' });
  }

  if (!upstreamSecret) {
    console.error('webhook: EMERGENT_WEBHOOK_SECRET not configured');
    return res.status(503).json({ ok: false, error: 'upstream_not_configured' });
  }

  // Swap in the upstream secret; every other field passes through verbatim
  // so the backend applies its own semantics to the original alert.
  const forwardBody = Object.assign({}, body, { secret: upstreamSecret });

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), UPSTREAM_TIMEOUT_MS);
  let upstream;
  try {
    const upstreamUrl = getUpstreamUrl();
    upstream = await fetch(upstreamUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(forwardBody),
      signal: controller.signal,
    });
  } catch (e) {
    console.error('webhook: upstream unreachable', redact((e && e.message) || e));
    return res.status(502).json({ ok: false, error: 'upstream_unreachable' });
  } finally {
    clearTimeout(timer);
  }

  const text = await upstream.text();
  let payload;
  try { payload = JSON.parse(text); } catch (e) { payload = { ok: false, error: 'upstream_non_json', raw: text.slice(0, 200) }; }
  console.log('webhook: forwarded alert, upstream status', upstream.status);
  return res.status(upstream.status).json(payload);
}

module.exports = handler;
module.exports.DEFAULT_UPSTREAM_URL = DEFAULT_UPSTREAM_URL;
module.exports.getUpstreamUrl = getUpstreamUrl;
module.exports.upstreamUrlOverridden = upstreamUrlOverridden;
module.exports.redact = redact;
