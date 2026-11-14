"""Item 3 — no LIVE badges on delayed/sim data; SIM on executions; PAPER on signals."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "frontend" / "src"


def _all_js():
    return {p: p.read_text() for p in SRC.rglob("*.js") if "/ui/" not in str(p)}


def test_no_bare_live_badges():
    bad = []
    for p, s in _all_js().items():
        for m in re.finditer(r'"LIVE"|>LIVE<|"LIVE MNQ"|LIVE FEED|PUNCH EXECUTED|"RECEIVER LIVE"|>Live Signal<|: live signals', s):
            # ApexPnlJournal lists TEST/PAPER/LIVE as honest mode options for manual
            # journal rows; that is a label picker, not a badge claiming sim data is live.
            if p.name == "ApexPnlJournal.js" and m.group(0) == '"LIVE"' and 'MODES = ["TEST", "PAPER", "LIVE"]' in s:
                continue
            bad.append(f"{p.name}:{m.group(0)}")
    assert not bad, bad


def test_execution_toasts_tagged_sim():
    for name in ("ExecutionHub.js", "dashboard/ExecutionPanel.js", "operator/OperatorCockpit.js"):
        s = (SRC / "components" / name).read_text()
        for m in re.finditer(r"toast\.(success|error)\(\s*`([^`]*)`", s):
            assert m.group(2).startswith("SIM"), (name, m.group(2))


def test_feed_label_helper():
    s = (SRC / "lib" / "fmt.js").read_text()
    assert 'tick?.source === "tradingview:live" && tick?.data_mode === "realtime" ? "REAL-TIME" : "DELAYED 10m"' in s


def test_signals_api_tags_paper(client, srv):
    import asyncio
    asyncio.get_event_loop().run_until_complete(srv._test_db.signals.insert_one({"id": "a", "source": "webhook", "created_at": "x"}))
    rows = client.get("/api/signals").json()
    assert rows and all(r["data_label"] == "PAPER" for r in rows)


_DISCLAIMER = ("Futures trading involves substantial risk of loss and is not suitable for all investors. "
               "This is education and structured practice, not financial advice. "
               "Past performance is not indicative of future results.")


def _signal_cases():
    # Founder-approved titles (Josue, Nov 13 2026 6:51 PM ET).
    tv = "REAL-TIME · alert"
    return [
        ({"source": "webhook"}, tv),
        ({"source": "tradingview:live"}, tv),
        ({"source": "TradingView alert"}, tv),
        ({"source": "webhook", "data_label": "PAPER"}, tv),  # stored display label is ignored
        ({"source": "yahoo:NQ=F"}, "DELAYED · practice alert"),
        ({"source": "live_engine"}, "DELAYED · practice alert"),
        ({"source": "test", "is_test": True}, "TEST · practice alert"),
        ({"source": "webhook", "is_test": True}, "TEST · practice alert"),
        ({"source": "paper-test"}, "PAPER · practice alert"),
        ({"source": ""}, "data source unverified · practice alert"),
        ({"source": "MNQ Scalp Punch v1"}, "data source unverified · practice alert"),
    ]


def test_discord_title_paper(srv):
    """Item 3: honest Discord titles per source; never LIVE; no-trade line and disclaimer always."""
    for extra, prefix in _signal_cases():
        for side, direction in (("long", "LONG"), ("short", "SHORT")):
            sig = {"side": side, "entry_price": 28000.0, "stop_loss": 27992.0, "tp1": 28010.0, **extra}
            embed = srv._build_discord_payload(sig)["embeds"][0]
            assert embed["title"] == f"{prefix} · {direction} · MNQ", (extra, embed["title"])
            assert "LIVE" not in embed["title"]
            if not prefix.startswith("REAL-TIME"):
                assert "REAL-TIME" not in embed["title"]
            assert embed["description"].endswith(_DISCLAIMER)
            assert "No trade was placed" in embed["description"]


def test_send_discord_signal_uses_same_title(monkeypatch):
    # Not using the `srv` fixture: it stubs send_discord_signal out.
    import asyncio
    import notifications as n
    import server as srv
    captured = []

    async def fake_deliver(payload, **kw):
        captured.append(payload)
        return {"status": "delivered"}

    monkeypatch.setattr(n, "deliver_discord", fake_deliver)
    for extra, prefix in _signal_cases():
        captured.clear()
        sig = {"side": "long", "created_at": "2026-11-13T23:00:00+00:00", **extra}
        asyncio.get_event_loop().run_until_complete(srv.send_discord_signal(sig))
        title = n.format_alert_message(captured[0])["embeds"][0]["title"]
        body = n.format_alert_message(captured[0])
        assert title == f"{prefix} · LONG · MNQ", (extra, title)
        assert "No trade was placed" in body["text"] and _DISCLAIMER in body["text"]


def test_demo_rows_labelled_demo(client, srv):
    import asyncio
    asyncio.get_event_loop().run_until_complete(srv._test_db.signals.insert_one({"id": "d", "source": "demo", "created_at": "y"}))
    rows = {r["id"]: r for r in client.get("/api/signals").json()}
    assert rows["d"]["data_label"] == "DEMO"
