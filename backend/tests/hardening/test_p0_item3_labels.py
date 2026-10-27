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


def test_discord_title_paper(srv):
    src = (ROOT / "backend" / "server.py").read_text()
    assert '"title": f"PAPER · ' in src


def test_demo_rows_labelled_demo(client, srv):
    import asyncio
    asyncio.get_event_loop().run_until_complete(srv._test_db.signals.insert_one({"id": "d", "source": "demo", "created_at": "y"}))
    rows = {r["id"]: r for r in client.get("/api/signals").json()}
    assert rows["d"]["data_label"] == "DEMO"
