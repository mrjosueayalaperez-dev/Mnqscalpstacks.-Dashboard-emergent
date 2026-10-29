"""One-shot: add two PAPER/SIM MNQ fills from 2026-10-29 to the `trades` collection.

PAPER/SIM only — these are NOT live trades. Josue runs this himself; agents never run it
against production. It touches only the `trades` collection and inserts at most two rows.

How to run (Josue):
    export MONGO_URL='<your Mongo connection string>'   # never commit or share it
    export DB_NAME='<your database name>'
    cd backend
    python scripts/add_paper_trades_2026-10-29.py            # dry run (default): preview only, writes nothing
    python scripts/add_paper_trades_2026-10-29.py --apply    # insert the two rows

Safety:
- Dry run by default; --apply is required to write.
- Refuses to insert a fill whose broker Trade ID (49634819 / 49669945) already appears in any
  trade's notes, so re-running is a no-op.
- No other collections or rows are read for writing; no auth, webhook, secret or Apex-journal changes.
- symbol MNQ and entry_price >= 25000, so the startup purge_stale_market_data() keeps these rows.

P&L is the broker's NET figure (after fees), stored in USD like auto-logged trades.
Gross check: SELL 6 MNQ x $2/pt -> #1 12.25 pts = $147.00 gross, #2 197.25 pts = $2,367.00 gross.

Futures trading involves substantial risk of loss and is not suitable for all investors. This is
education and structured practice, not financial advice. Past performance is not indicative of future results.
"""
import argparse
import os
import sys
import uuid
from typing import Any, Dict, List

TRADE_DATE = "2026-10-29"
DAY_NET = 2493.60

FILLS: List[Dict[str, Any]] = [
    {"broker_trade_id": "49634819", "entry_price": 29473.00, "exit_price": 29460.75, "pnl": 136.80,
     "notes": "PAPER/SIM — not live | broker Trade ID 49634819 | SELL 6 MNQ | closed ~09:50 ET 2026-10-29 | P&L NET $136.80"},
    {"broker_trade_id": "49669945", "entry_price": 29438.75, "exit_price": 29241.50, "pnl": 2356.80,
     "notes": "PAPER/SIM — not live | broker Trade ID 49669945 | Order ID 54971494 | SELL 6 MNQ | "
              "closed ~16:20 ET 2026-10-29 (User Request) | P&L NET $2,356.80"},
]


def build_rows() -> List[Dict[str, Any]]:
    rows = []
    for f in FILLS:
        rows.append({
            "id": str(uuid.uuid4()),
            "symbol": "MNQ",
            "entry_price": f["entry_price"],
            "exit_price": f["exit_price"],
            "quantity": 6,
            "side": "short",  # existing schema uses long/short; SELL-to-open = short
            "status": "closed",
            "entry_date": TRADE_DATE,
            "exit_date": TRADE_DATE,
            "pnl": float(f["pnl"]),
            "notes": f["notes"],
        })
    return rows


def already_present(coll, broker_trade_id: str) -> bool:
    return coll.find_one({"notes": {"$regex": f"Trade ID {broker_trade_id}\\b"}}) is not None


def run(db, apply: bool, out=print) -> Dict[str, Any]:
    coll = db["trades"]
    rows = build_rows()
    out(f"{'APPLY' if apply else 'DRY RUN'}: {len(rows)} PAPER/SIM fills for {TRADE_DATE} -> collection 'trades'")
    inserted, skipped = [], []
    for f, row in zip(FILLS, rows):
        dup = already_present(coll, f["broker_trade_id"])
        out(f"  [{'SKIP duplicate' if dup else ('INSERT' if apply else 'would insert')}] "
            f"{row['side']} {row['quantity']} {row['symbol']} entry {row['entry_price']:.2f} exit {row['exit_price']:.2f} "
            f"pnl {row['pnl']:+.2f} | {row['notes']}")
        if dup:
            skipped.append(f["broker_trade_id"])
            continue
        if apply:
            coll.insert_one(dict(row))
            inserted.append(f["broker_trade_id"])
    total = round(sum(r["pnl"] for r in rows), 2)
    assert total == DAY_NET, total
    out(f"Day net (these two fills): {total:+.2f}")
    if not apply:
        out("Nothing written. Re-run with --apply to insert.")
    return {"inserted": inserted, "skipped": skipped, "day_net": total}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--apply", action="store_true", help="insert the rows (default: dry run)")
    args = ap.parse_args(argv)
    url, name = os.environ.get("MONGO_URL"), os.environ.get("DB_NAME")
    if not url or not name:
        print("Set MONGO_URL and DB_NAME first (see the docstring).", file=sys.stderr)
        return 2
    from pymongo import MongoClient
    client = MongoClient(url, serverSelectionTimeoutMS=8000)
    try:
        res = run(client[name], args.apply)
    finally:
        client.close()
    print(f"Done: inserted {res['inserted'] or 'none'}, skipped {res['skipped'] or 'none'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
