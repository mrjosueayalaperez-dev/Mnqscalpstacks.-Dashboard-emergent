"""Iteration 14: Verify data cleanup + MNQ-only seed + checkout/order flow."""
import os
import requests
import pytest
from dotenv import load_dotenv

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://mnq-scalp-stack.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"
_ENV = os.path.join(os.path.dirname(__file__), "..", ".env")
load_dotenv(_ENV)
ADMIN_EMAIL = os.environ["ADMIN_EMAIL"]
ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]


@pytest.fixture(scope="session")
def auth():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=15)
    assert r.status_code == 200, r.text
    return s


# ---- Data cleanup checks ----

def test_watchlist_mnq_only(auth):
    r = auth.get(f"{API}/watchlist", timeout=15)
    assert r.status_code == 200
    items = r.json()
    stocks = [w for w in items if (w.get("symbol") or "").upper() in {"SOFI", "NIO", "F", "AAPL", "TSLA"}]
    assert stocks == [], f"Non-MNQ watchlist items found: {stocks}"


def test_seed_endpoint(auth):
    r = auth.post(f"{API}/seed", timeout=30)
    assert r.status_code in (200, 201), r.text


def test_watchlist_after_seed_mnq_only(auth):
    r = auth.get(f"{API}/watchlist", timeout=15)
    assert r.status_code == 200
    items = r.json()
    for w in items:
        sym = (w.get("symbol") or "").upper()
        assert "MNQ" in sym or sym == "NQ", f"Non-MNQ watchlist symbol after seed: {sym}"


def test_trades_no_sofi_no_stale_prices(auth):
    r = auth.get(f"{API}/trades", timeout=15)
    assert r.status_code == 200
    trades = r.json()
    for t in trades:
        sym = (t.get("symbol") or "").upper()
        assert sym == "MNQ", f"Non-MNQ trade found: {sym} / {t}"
        entry = t.get("entry_price") or 0
        # stale range 18,000-19,000 or 28,000-28,500 (old fake prices)
        assert not (18000 <= entry <= 19000), f"Stale 18k trade: {t}"


def test_signals_no_low_prices(auth):
    r = auth.get(f"{API}/signals?limit=200", timeout=15)
    assert r.status_code == 200
    sigs = r.json()
    for s in sigs:
        entry = s.get("entry_price") or s.get("price") or 0
        if entry:
            assert entry >= 25000, f"Stale low-price signal: {s}"


def test_active_signals_expired(auth):
    r = auth.get(f"{API}/signals?status=active&limit=50", timeout=15)
    # 200 with list or empty is fine
    assert r.status_code == 200
    for s in r.json():
        entry = s.get("entry_price") or 0
        if entry:
            assert entry >= 25000, f"Stale active signal: {s}"


# ---- Checkout backend fallback ----

def test_checkout_create_premium(auth):
    r = auth.post(f"{API}/checkout/create", json={"tier": "premium", "origin_url": BASE_URL}, timeout=20)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "url" in data or "session_url" in data, data


# ---- Operator order regression ----

def test_operator_buy_and_flatten(auth):
    # reset first
    auth.post(f"{API}/operator/control/flatten", timeout=15)
    auth.post(f"{API}/operator/control/reset_session", timeout=15)

    r = auth.post(
        f"{API}/operator/order",
        json={"symbol": "MNQ", "action": "BUY", "qty": 1, "order_type": "MARKET"},
        timeout=20,
    )
    assert r.status_code == 200, r.text

    r2 = auth.post(f"{API}/operator/control/flatten", timeout=15)
    assert r2.status_code == 200

    auth.post(f"{API}/operator/control/reset_session", timeout=15)
