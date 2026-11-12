// MNQ Scalp Stacks - TradingView webhook receiver (Vercel serverless, Phase 1)
// Validates SIGNAL_WEBHOOK_SECRET server-side (env var, never in code).
// A validated alert is recorded in the function log and acknowledged.
// No trading execution. No external writes. Education infrastructure only.
const crypto = require('crypto');

function safeEqual(a, b) {
  const ba = Buffer.from(String(a));
  const bb = Buffer.from(String(b));
  if (ba.length !== bb.length) return false;
  return crypto.timingSafeEqual(ba, bb);
}

module.exports = async (req, res) => {
  const expected = process.env.SIGNAL_WEBHOOK_SECRET || '';

  if (req.method === 'GET') {
    return res.status(200).json({
      ok: true,
      receiver: 'vercel',
      secret_configured: expected.length > 0,
      ts: new Date().toISOString(),
    });
  }

  if (req.method !== 'POST') {
    return res.status(405).json({ ok: false, error: 'method_not_allowed' });
  }

  if (!expected) {
    console.error('webhook: SIGNAL_WEBHOOK_SECRET not configured');
    return res.status(503).json({ ok: false, error: 'secret_not_configured' });
  }

  let body = req.body;
  if (typeof body === 'string') {
    try { body = JSON.parse(body); } catch (e) { body = {}; }
  }
  body = body || {};

  const provided = body.secret || req.headers['x-webhook-secret'] || '';
  if (!safeEqual(provided, expected)) {
    console.warn('webhook: rejected POST (bad or missing secret)');
    return res.status(401).json({ ok: false, error: 'bad_or_missing_secret' });
  }

  const alert = {
    action: body.action || null,
    symbol: body.symbol || null,
    interval: body.interval || null,
    price: (body.price === undefined ? null : body.price),
    time: body.time || null,
    source: body.source || 'tradingview',
    received_at: new Date().toISOString(),
  };
  console.log('webhook: validated alert', JSON.stringify(alert));
  return res.status(200).json({ ok: true, received: alert });
};
