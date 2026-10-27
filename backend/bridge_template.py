"""MNQ SCALP STACKS — NinjaTrader ATI Bridge (single-file, stdlib only).

Runs on YOUR Windows PC next to NinjaTrader 8. It polls the cloud backend for
pending order commands and writes OIF files into
  Documents\\NinjaTrader 8\\incoming
which NinjaTrader executes instantly via the ATI File Interface.

SETUP (one time):
  1. In NinjaTrader 8: Tools -> Options -> Automated trading interface ->
     enable "AT Interface" (File Interface). Restart NT8.
  2. Connect your account (Sim101 first! Live only after testing).
  3. Create ATM strategy templates named exactly: SNIPE_1R, SNIPE_2R, RUNNER
     (matching your cockpit bracket presets: 40t/60t, 40t/120t, 40t/200t).
  4. Set two environment variables (or edit the constants below):
       SCALP_BACKEND_URL = https://<your-app>.com
       SCALP_API_KEY     = <your RETOOL_API_KEY value>  (blank if not configured)
  5. Run:  python mnq_ati_bridge.py

The bridge only writes text files — NinjaTrader stays in full control of
broker connectivity and risk.
"""
raise SystemExit("MNQ ATI bridge DISABLED (P0 hardening): no broker order routing.")

import json
import os
import time
import urllib.request
import uuid
from pathlib import Path

BACKEND_URL = os.environ.get("SCALP_BACKEND_URL", "").rstrip("/")
API_KEY = os.environ.get("SCALP_API_KEY", "")
POLL_INTERVAL_S = 1.0
# Override with NT_INCOMING env var if NinjaTrader lives somewhere custom.
NT_INCOMING = os.environ.get(
    "NT_INCOMING",
    str(Path.home() / "Documents" / "NinjaTrader 8" / "incoming"),
)

_seen_ids = set()  # local duplicate guard for the current run


def _request(method, path, body=None):
    url = f"{BACKEND_URL}/api/ati{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if API_KEY:
        req.add_header("X-API-Key", API_KEY)
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read().decode())


def build_oif_line(cmd):
    ctype = cmd["command_type"]
    acct = cmd.get("account", "")
    inst = cmd.get("instrument", "")
    if ctype == "PLACE":
        limit_price = cmd.get("limit_price")
        stop_price = cmd.get("stop_price")
        return (
            f"PLACE;{acct};{inst};{cmd.get('action','')};{cmd.get('quantity',0)};"
            f"{cmd.get('order_type','MARKET')};"
            f"{'' if limit_price is None else limit_price};"
            f"{'' if stop_price is None else stop_price};"
            f"{cmd.get('tif','DAY')};;;"
            f"{cmd.get('atm_strategy_name','')};"
        )
    if ctype == "CLOSEPOSITION":
        return f"CLOSEPOSITION;{acct};{inst};;;;;;;;;;"
    if ctype == "FLATTENEVERYTHING":
        return "FLATTENEVERYTHING;;;;;;;;;;"
    raise ValueError(f"Unknown command type: {ctype}")


def write_oif(lines):
    incoming = Path(NT_INCOMING)
    if not incoming.exists():
        raise RuntimeError(
            f"NinjaTrader incoming folder not found: {incoming}\n"
            "Is NinjaTrader 8 installed? Set NT_INCOMING env var to override."
        )
    # Unique name per file (oif*.txt) — NEVER reuse names (NT file-locking rule).
    path = incoming / f"oif_{uuid.uuid4().hex[:10]}.txt"
    # Write DIRECTLY into incoming (never copy) — atomic single write + close.
    with path.open("w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    return path.name


def main():
    if not BACKEND_URL:
        raise SystemExit("Set SCALP_BACKEND_URL env var to your app URL first.")
    print(f"MNQ ATI BRIDGE online -> {BACKEND_URL}")
    print(f"NinjaTrader incoming  -> {NT_INCOMING}")
    while True:
        try:
            _request("POST", "/heartbeat", {})
            data = _request("GET", "/commands")
            cmds = [c for c in data.get("commands", []) if c["id"] not in _seen_ids]
            if cmds:
                lines = [build_oif_line(c) for c in cmds]
                fname = write_oif(lines)
                _request("POST", "/ack", {"command_ids": [c["id"] for c in cmds]})
                _seen_ids.update(c["id"] for c in cmds)
                for c, line in zip(cmds, lines):
                    print(f"  -> {fname}: {line}")
        except Exception as e:
            print(f"bridge error: {e}")
        time.sleep(POLL_INTERVAL_S)


if __name__ == "__main__":
    main()
