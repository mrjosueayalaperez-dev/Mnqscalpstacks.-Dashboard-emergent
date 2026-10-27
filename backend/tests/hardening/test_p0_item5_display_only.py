"""Item 5 — signals display-only + verbatim disclaimer; no automatic order paths."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "frontend" / "src"
DISCLAIMER = ("Futures trading involves substantial risk of loss and is not suitable for all investors. "
              "This is education and structured practice, not financial advice. "
              "Past performance is not indicative of future results.")


def test_disclaimer_verbatim_and_rendered():
    assert DISCLAIMER in (SRC / "lib" / "fmt.js").read_text()
    for f in ("components/SignalDashboard.js", "components/dashboard/MobileShell.js", "components/LandingPage.js", "pages/public/PublicLayout.js"):
        assert "RISK_DISCLAIMER" in (SRC / f).read_text(), f


def test_no_auto_execute_in_frontend():
    for p in SRC.rglob("*.js"):
        s = p.read_text()
        assert "onAutoExecute" not in s, p
        assert "AUTO ${" not in s, p
        assert "ati/config" not in s, p


def test_order_endpoints_only_called_from_manual_handlers():
    hits = []
    for p in SRC.rglob("*.js"):
        for i, line in enumerate(p.read_text().splitlines(), 1):
            if "/operator/order" in line:
                hits.append(f"{p.relative_to(SRC)}:{i}")
    # exactly the two manual button handlers (cockpit + execution panel), both SIM log-only server side
    assert sorted(h.split(":")[0] for h in hits) == ["components/dashboard/ExecutionPanel.js", "components/operator/OperatorCockpit.js"], hits


def test_backend_has_no_broker_routing_or_auto_order():
    srv = (ROOT / "backend" / "server.py").read_text()
    assert "ati.enqueue" not in srv
    assert not re.search(r"operator_order\(", srv.replace("async def operator_order(", ""))  # never invoked internally
    ati = (ROOT / "backend" / "ati.py").read_text()
    assert "insert_one" not in ati and "return False" in ati
    assert 'raise SystemExit("MNQ ATI bridge DISABLED' in (ROOT / "backend" / "bridge_template.py").read_text()
