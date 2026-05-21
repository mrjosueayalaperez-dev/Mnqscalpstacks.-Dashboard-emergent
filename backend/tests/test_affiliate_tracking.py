"""Regression: affiliate redirect + admin click stats."""
import os
import httpx
import pytest

BASE = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001")
API = f"{BASE}/api"


def test_redirect_known_partner_302():
    r = httpx.get(f"{API}/r/ninjatrader?src=pytest-regression", follow_redirects=False, timeout=10)
    assert r.status_code == 302
    assert r.headers.get("location", "").startswith("http")


def test_redirect_unknown_partner_404():
    r = httpx.get(f"{API}/r/nonexistent_partner", follow_redirects=False, timeout=10)
    assert r.status_code == 404


def test_click_stats_shape():
    # Generate a click to ensure data exists
    httpx.get(f"{API}/r/tradingview?src=pytest-stats", follow_redirects=False, timeout=10)

    r = httpx.get(f"{API}/admin/clicks", timeout=10)
    assert r.status_code == 200
    body = r.json()
    assert "total_clicks" in body and body["total_clicks"] >= 1
    assert "by_partner" in body and isinstance(body["by_partner"], list)
    assert "by_partner_src" in body and isinstance(body["by_partner_src"], list)
    assert "partner_urls" in body
    # All 4 partners are exposed in config
    assert set(body["partner_urls"].keys()) >= {"ninjatrader", "tradingview", "gpay", "discord"}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
