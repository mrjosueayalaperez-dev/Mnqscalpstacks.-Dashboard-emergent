"""Item 1 — CFTC 4.41: no generated results, KPIs exclude demo/test rows."""
import asyncio
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
W = {"X-API-Key": "k" * 32}


def _seed(srv, rows):
    asyncio.get_event_loop().run_until_complete(srv._test_db.signals.insert_many(rows)) if rows else None


def _sig(i, outcome, pts, **kw):
    return {"id": f"s{i}", "symbol": "MNQ", "side": "long", "entry_price": 1, "stop_loss": 0, "tp1": 2, "tp2": 3,
            "outcome": outcome, "pnl_points": pts, "status": "hit_tp1", "created_at": f"2026-10-0{i % 9 + 1}T10:00:00+00:00", **kw}


def test_kpis_with_only_demo_test_rows_are_na(client, srv):
    _seed(srv, [_sig(1, "win", 10, source="demo"), _sig(2, "win", 10, source="test", is_test=True),
                _sig(3, "win", 20, source="engine", is_test=True), _sig(4, "win", 5, source="webhook", is_demo=True)])
    st = client.get("/api/signals/stats").json()
    assert st["closed_signals"] == 0 and st["win_rate"] is None and st["total_pnl_points"] is None
    perf = client.get("/api/public/performance").json()["overview"]
    assert perf["win_rate"] is None and perf["closed_signals"] == 0 and perf["total_signals"] == 0
    rr = client.get("/api/signals/recent-results").json()
    assert rr["results"] == [] and rr["win_rate"] is None
    lb = client.get("/api/public/leaderboard").json()
    assert lb["best_win_streak"] == 0


def test_kpis_count_only_real_rows(client, srv):
    _seed(srv, [_sig(1, "win", 10, source="demo"), _sig(2, "loss", -8, source="webhook"), _sig(3, "win", 10, source="engine")])
    st = client.get("/api/signals/stats").json()
    assert st["closed_signals"] == 2 and st["win_rate"] == 50.0


def test_trade_stats_na_when_no_closed_trades(client):
    st = client.get("/api/trades/stats").json()
    assert st["win_rate"] is None and st["total_pnl"] is None


def test_seed_and_random_endpoints_removed(client):
    assert client.post("/api/public/seed-demo", headers=W).status_code == 410
    assert client.post("/api/signals/test").status_code == 410


def test_stock_endpoints_never_fabricate(client, srv, monkeypatch):
    async def none(*a, **k):
        return None
    for f in ("fetch_stock_quote", "fetch_intraday_data", "fetch_technical_indicators"):
        monkeypatch.setattr(srv, f, none)
    for path in ("/api/stocks/quote/AMD", "/api/stocks/intraday/AMD", "/api/stocks/indicators/AMD"):
        r = client.get(path)
        assert r.status_code == 503 and r.json()["detail"]["status"] == "data_unavailable"
    r = client.get("/api/stocks/scanner").json()
    assert r["scanners"] == [] and r["status"] == "data_unavailable"


def test_no_random_in_backend_kpi_signal_paths():
    src = (ROOT / "backend" / "server.py").read_text()
    assert "_rng" not in src and "SystemRandom" not in src and not re.search(r"^import random|^from random", src, re.M)
    assert "* 0.995" not in src
    assert "Startup pipeline check" not in src


def test_no_random_outcomes_or_seed_calls_in_frontend():
    comp = ROOT / "frontend" / "src" / "components"
    eh = (comp / "ExecutionHub.js").read_text()
    assert "Math.random" not in eh and "signals/test`" not in eh
    for f in comp.rglob("*.js"):
        assert "seed-demo" not in f.read_text(), f
