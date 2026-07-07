"""End-to-end regression: ATI Phase 2 order pipeline + GPay Stripe checkout.

Companion tests to test_ati_bridge.py. Runs synchronously against the live
supervisor-managed backend using REACT_APP_BACKEND_URL.

Cleanup: every test that arms ATI disarms it in a finally block and
resets the operator session.
"""
import os
import time

import httpx
import pytest

BASE = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/")
API = f"{BASE}/api"


# ---------------- helpers ----------------

def _reset_session():
    httpx.post(f"{API}/operator/control/unkill", timeout=10)
    httpx.post(f"{API}/operator/control/resume", timeout=10)
    httpx.post(f"{API}/operator/control/reset_session", timeout=10)


def _arm(enabled: bool):
    r = httpx.post(f"{API}/ati/config", json={"enabled": enabled}, timeout=10)
    assert r.status_code == 200
    return r.json()


# ---------------- ATI status + config ----------------

class TestAtiStatusConfig:
    def test_status_shape(self):
        r = httpx.get(f"{API}/ati/status", timeout=10)
        assert r.status_code == 200
        body = r.json()
        for k in ("enabled", "account", "instrument", "bridge_online", "pending", "dispatched"):
            assert k in body, f"missing key: {k}"
        assert isinstance(body["pending"], int)
        assert isinstance(body["dispatched"], int)

    def test_config_arm_and_disarm(self):
        try:
            armed = _arm(True)
            assert armed["enabled"] is True

            # heartbeat -> bridge_online true
            hb = httpx.post(f"{API}/ati/heartbeat", timeout=10)
            assert hb.status_code == 200
            assert hb.json()["bridge_online"] is True

            # /operator/state connection status must reflect CONNECTED
            op = httpx.get(f"{API}/operator/state", timeout=10).json()
            assert op["connection"]["status"] == "CONNECTED"
            assert op["connection"]["ati_enabled"] is True
        finally:
            disarmed = _arm(False)
            assert disarmed["enabled"] is False
            op = httpx.get(f"{API}/operator/state", timeout=10).json()
            assert op["connection"]["status"] == "DISCONNECTED"

    def test_bridge_script_downloadable(self):
        r = httpx.get(f"{API}/ati/bridge-script", timeout=10)
        assert r.status_code == 200
        cd = r.headers.get("content-disposition", "")
        assert "attachment" in cd
        text = r.text
        assert "PLACE;" in text
        assert "incoming" in text.lower()


# ---------------- ATI order pipeline ----------------

class TestAtiOrderPipeline:
    def test_place_command_snipe_2r(self):
        _reset_session()
        _arm(True)
        try:
            time.sleep(1.7)  # server 1500ms order cooldown
            payload = {
                "action": "BUY", "qty": 1, "order_type": "MARKET",
                "preset": "SNIPE_2R", "sl_ticks": 40, "tp_ticks": 120,
            }
            # retry once for 503 (cold Yahoo feed)
            r = httpx.post(f"{API}/operator/order", json=payload, timeout=20)
            if r.status_code == 503:
                time.sleep(2.0)
                r = httpx.post(f"{API}/operator/order", json=payload, timeout=20)
            if r.status_code == 503:
                pytest.skip("Live feed still cold after retry; cannot fill simulator order")
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["ati"]["routed"] is True
            cid = body["ati"]["command_id"]
            assert isinstance(cid, str) and len(cid) > 0

            # Verify /ati/commands returns the queued PLACE with SNIPE_2R strategy
            cmds = httpx.get(f"{API}/ati/commands", timeout=10).json()["commands"]
            mine = [c for c in cmds if c["id"] == cid]
            assert mine, "PLACE command not present in /ati/commands"
            cmd = mine[0]
            assert cmd["command_type"] == "PLACE"
            assert cmd["action"] == "BUY"
            assert cmd["atm_strategy_name"] == "SNIPE_2R"

            # ack pops it from pending
            ack = httpx.post(f"{API}/ati/ack", json={"command_ids": [cid]}, timeout=10)
            assert ack.status_code == 200
            assert ack.json()["acked"] == 1
            remaining = httpx.get(f"{API}/ati/commands", timeout=10).json()["commands"]
            assert all(c["id"] != cid for c in remaining)
        finally:
            _arm(False)
            _reset_session()

    def test_flatten_enqueues_flatteneverything(self):
        _reset_session()
        _arm(True)
        try:
            r = httpx.post(f"{API}/operator/control/flatten", timeout=10)
            assert r.status_code == 200
            cmds = httpx.get(f"{API}/ati/commands", timeout=10).json()["commands"]
            flats = [c for c in cmds if c["command_type"] == "FLATTENEVERYTHING"]
            assert flats, "FLATTEN did not enqueue FLATTENEVERYTHING"
            # cleanup
            httpx.post(f"{API}/ati/ack", json={"command_ids": [c["id"] for c in flats]}, timeout=10)
        finally:
            _arm(False)
            _reset_session()


# ---------------- Stripe checkout (GPay via Stripe) ----------------

class TestStripeCheckout:
    def test_checkout_create_pro(self):
        r = httpx.post(f"{API}/checkout/create",
                       json={"tier": "pro", "origin_url": BASE}, timeout=20)
        assert r.status_code == 200, r.text
        body = r.json()
        assert "url" in body and body["url"].startswith("https://")
        assert "checkout.stripe.com" in body["url"] or "stripe" in body["url"].lower()
        assert "session_id" in body
        assert isinstance(body["session_id"], str)
        # persist for status check
        TestStripeCheckout.session_id = body["session_id"]

    def test_checkout_create_elite(self):
        r = httpx.post(f"{API}/checkout/create",
                       json={"tier": "elite", "origin_url": BASE}, timeout=20)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["url"].startswith("https://")
        assert "session_id" in body

    def test_checkout_status(self):
        sid = getattr(TestStripeCheckout, "session_id", None)
        if not sid:
            # create fresh
            c = httpx.post(f"{API}/checkout/create",
                           json={"tier": "pro", "origin_url": BASE}, timeout=20).json()
            sid = c["session_id"]
        r = httpx.get(f"{API}/checkout/status/{sid}", timeout=15)
        assert r.status_code == 200, r.text
        body = r.json()
        # unpaid brand new session - accept either status or payment_status
        assert ("status" in body) or ("payment_status" in body)


# ---------------- Regression: /operator/state after refactor ----------------

class TestOperatorStateRegression:
    def test_operator_state_shape(self):
        r = httpx.get(f"{API}/operator/state", timeout=10)
        assert r.status_code == 200
        body = r.json()
        # keys observed on production shape
        for k in ("connection", "position", "balance", "kill_switch"):
            assert k in body, f"missing {k} in operator_state; got keys={list(body.keys())}"
        assert "status" in body["connection"]
