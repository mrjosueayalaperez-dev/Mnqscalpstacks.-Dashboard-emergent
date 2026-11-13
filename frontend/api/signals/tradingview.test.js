/**
 * Unit tests for the Vercel TradingView receiver.
 * Run with: node --test frontend/api/signals/tradingview.test.js
 * No live POSTs, no production URLs are contacted (fetch is mocked).
 */
const { describe, it, beforeEach, afterEach } = require('node:test');
const assert = require('node:assert/strict');
const receiver = require('./tradingview.js');

const DEFAULT = 'https://mnq-scalp-stack.emergent.host/api/signals/tradingview';
const OVERRIDE = 'https://example-backend.test/api/signals/tradingview';
const TV_SECRET = 'test-only-signal-secret';
const UPSTREAM_SECRET = 'test-only-upstream-secret';

const originalEnv = { ...process.env };
const originalFetch = global.fetch;
let logs;

function captureLogs() {
  logs = { error: [], warn: [], log: [] };
  console.error = (...args) => logs.error.push(args.map(String).join(' '));
  console.warn = (...args) => logs.warn.push(args.map(String).join(' '));
  console.log = (...args) => logs.log.push(args.map(String).join(' '));
}

function restore() {
  for (const key of Object.keys(process.env)) {
    if (!(key in originalEnv)) delete process.env[key];
  }
  Object.assign(process.env, originalEnv);
  global.fetch = originalFetch;
  console.error = originalEnv && require('console').error;
  // Restore console from the console module's prototype methods
  const con = require('console');
  console.error = con.error;
  console.warn = con.warn;
  console.log = con.log;
}

function mockRes() {
  return {
    statusCode: null,
    body: null,
    status(code) {
      this.statusCode = code;
      return this;
    },
    json(obj) {
      this.body = obj;
      return this;
    },
  };
}

function assertNoSecretsOrUrls(text) {
  const s = String(text);
  assert.equal(s.includes(OVERRIDE), false, 'override URL leaked');
  assert.equal(s.includes('emergent.host'), false, 'default host leaked');
  assert.equal(s.includes(TV_SECRET), false, 'signal secret leaked');
  assert.equal(s.includes(UPSTREAM_SECRET), false, 'upstream secret leaked');
}

describe('getUpstreamUrl', () => {
  afterEach(restore);

  it('defaults to the Emergent URL when unset', () => {
    assert.equal(receiver.getUpstreamUrl({}), DEFAULT);
    assert.equal(receiver.DEFAULT_UPSTREAM_URL, DEFAULT);
  });

  it('defaults to the Emergent URL when blank or whitespace', () => {
    assert.equal(receiver.getUpstreamUrl({ UPSTREAM_WEBHOOK_URL: '' }), DEFAULT);
    assert.equal(receiver.getUpstreamUrl({ UPSTREAM_WEBHOOK_URL: '   ' }), DEFAULT);
  });

  it('uses a trimmed override when set', () => {
    assert.equal(receiver.getUpstreamUrl({ UPSTREAM_WEBHOOK_URL: `  ${OVERRIDE}  ` }), OVERRIDE);
    assert.equal(receiver.upstreamUrlOverridden({ UPSTREAM_WEBHOOK_URL: OVERRIDE }), true);
    assert.equal(receiver.upstreamUrlOverridden({}), false);
  });
});

describe('GET health', () => {
  beforeEach(() => {
    captureLogs();
    delete process.env.UPSTREAM_WEBHOOK_URL;
    process.env.SIGNAL_WEBHOOK_SECRET = TV_SECRET;
    process.env.EMERGENT_WEBHOOK_SECRET = UPSTREAM_SECRET;
  });
  afterEach(restore);

  it('does not echo the upstream URL or secrets, and reports override=false by default', async () => {
    const res = mockRes();
    await receiver({ method: 'GET' }, res);
    assert.equal(res.statusCode, 200);
    assert.equal(res.body.ok, true);
    assert.equal(res.body.receiver, 'vercel');
    assert.equal(res.body.upstream_url_overridden, false);
    assert.equal(res.body.secret_configured, true);
    assert.equal(res.body.upstream_configured, true);
    const dumped = JSON.stringify(res.body) + logs.error.join('\n') + logs.log.join('\n');
    assertNoSecretsOrUrls(dumped);
    assert.equal('url' in res.body, false);
    assert.equal('upstream_url' in res.body, false);
  });

  it('reports override=true without revealing the URL when UPSTREAM_WEBHOOK_URL is set', async () => {
    process.env.UPSTREAM_WEBHOOK_URL = OVERRIDE;
    const res = mockRes();
    await receiver({ method: 'GET' }, res);
    assert.equal(res.statusCode, 200);
    assert.equal(res.body.upstream_url_overridden, true);
    assertNoSecretsOrUrls(JSON.stringify(res.body));
  });
});

describe('POST forward', () => {
  beforeEach(() => {
    captureLogs();
    delete process.env.UPSTREAM_WEBHOOK_URL;
    process.env.SIGNAL_WEBHOOK_SECRET = TV_SECRET;
    process.env.EMERGENT_WEBHOOK_SECRET = UPSTREAM_SECRET;
  });
  afterEach(restore);

  function installFetch(impl) {
    const calls = [];
    global.fetch = async (url, opts) => {
      calls.push({ url, opts });
      return impl(url, opts);
    };
    return calls;
  }

  it('forwards to the Emergent default when UPSTREAM_WEBHOOK_URL is unset', async () => {
    const calls = installFetch(async () => ({
      status: 200,
      text: async () => JSON.stringify({ ok: true, action: 'logged' }),
    }));
    const res = mockRes();
    await receiver(
      { method: 'POST', headers: {}, body: { secret: TV_SECRET, action: 'HOLD', symbol: 'MNQ' } },
      res,
    );
    assert.equal(res.statusCode, 200);
    assert.equal(calls.length, 1);
    assert.equal(calls[0].url, DEFAULT);
    const sent = JSON.parse(calls[0].opts.body);
    assert.equal(sent.secret, UPSTREAM_SECRET);
    assert.equal(sent.action, 'HOLD');
  });

  it('forwards to UPSTREAM_WEBHOOK_URL when set', async () => {
    process.env.UPSTREAM_WEBHOOK_URL = OVERRIDE;
    const calls = installFetch(async () => ({
      status: 200,
      text: async () => JSON.stringify({ ok: true }),
    }));
    const res = mockRes();
    await receiver(
      { method: 'POST', headers: { 'x-webhook-secret': TV_SECRET }, body: { action: 'BUY', symbol: 'MNQ' } },
      res,
    );
    assert.equal(res.statusCode, 200);
    assert.equal(calls.length, 1);
    assert.equal(calls[0].url, OVERRIDE);
  });

  it('redacts URLs from unreachable-error logs and does not put them in the response', async () => {
    process.env.UPSTREAM_WEBHOOK_URL = OVERRIDE;
    installFetch(async () => {
      throw new Error(`fetch failed: ${OVERRIDE}`);
    });
    const res = mockRes();
    await receiver(
      { method: 'POST', headers: {}, body: { secret: TV_SECRET, action: 'HOLD' } },
      res,
    );
    assert.equal(res.statusCode, 502);
    assert.equal(res.body.error, 'upstream_unreachable');
    const dumped = JSON.stringify(res.body) + logs.error.join('\n');
    assertNoSecretsOrUrls(dumped);
    assert.equal(logs.error.some((line) => line.includes('[REDACTED_URL]')), true);
  });
});
