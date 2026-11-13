// MNQ Scalp Stacks - TradingView webhook receiver (Vercel serverless)
// Phase 2 (PR version): validate the Vercel-side secret, then forward the
// alert server-side to the Emergent backend endpoint, which remains the
// single code path for the kill switch, per-action semantics (BUY/SELL
// cards, HOLD log, CLOSE expiry, PRICE tape update) and database writes.
//
// Secrets are env-only, never in code:
//   SIGNAL_WEBHOOK_SECRET   - the NEW secret TradingView sends to Vercel
//   EMERGENT_WEBHOOK_SECRET - the CURRENT secret the Emergent backend expects
// This route adds no labels of its own; cards are created by the backend's
// own pipeline with its native labeling. No trading execution happens here.
const crypto = require('crypto');

const UPSTREAM_URL = 'https://mnq-scalp-stack.emergent.host/api/signals/tradingview';
const UPSTREAM_TIMEOUT_MS = 8000;

function safeEqual(a, b) {
  const ba = Buffer.from(String(a));
  const bb = Buffer.from(String(b));
  if (ba.length !== bb.length) return false;
  return crypto.timingSafeEqual(ba, bb);
}

module.exports = async (req, res) => {
  const secret = process.env.SIGNAL_WEBHOOK_SECRET || '';
  const upstreamSecret = process.env.EMERGENT_WEBHOOK_SECRET || '';

  if (req.method === 'GET') {
    return res.status(200).json({
      ok: true,
      receiver: 'vercel',
      mode: 'forward',
      secret_configured: secret.length > 0,
      upstream_configured: upstreamSecret.length > 0,
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
    upstream = await fetch(UPSTREAM_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(forwardBody),
      signal: controller.signal,
    });
  } catch (e) {
    console.error('webhook: upstream unreachable', String((e && e.message) || e));
    return res.status(502).json({ ok: false, error: 'upstream_unreachable' });
  } finally {
    clearTimeout(timer);
  }

  const text = await upstream.text();
  let payload;
  try { payload = JSON.parse(text); } catch (e) { payload = { ok: false, error: 'upstream_non_json', raw: text.slice(0, 200) }; }
  console.log('webhook: forwarded alert, upstream status', upstream.status);
  return res.status(upstream.status).json(payload);
};
