#!/usr/bin/env python3
"""Copy MongoDB collections from a source database to a target database.

Connection strings are read from the environment only:

  SOURCE_MONGO_URL
  TARGET_MONGO_URL

Optional, when a URI has no database path:

  SOURCE_DB_NAME / TARGET_DB_NAME
  DB_NAME   (fallback for both)

This script never prints URLs, hosts, usernames or passwords.
Dry-run is the default (counts only). Pass --apply to write, using
idempotent replace_one upserts keyed on _id.

Josue runs this on his own machine. Do not run it against production
from chat or a shared agent box, and never paste the URLs into chat.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from typing import Any, Callable, Dict, List, Optional, Sequence

SYSTEM_PREFIXES = ("system.",)
SKIP_COLLECTION_EXACT = frozenset(
    {"system.indexes", "system.profile", "system.users", "system.views"}
)

_URI_RE = re.compile(r"mongodb(\+srv)?://\S+", re.IGNORECASE)
_USERINFO_RE = re.compile(r"://[^/\s:@]+:[^/\s@]+@", re.IGNORECASE)
_HTTP_RE = re.compile(r"https?://\S+", re.IGNORECASE)


def redact(text: Any) -> str:
    """Strip connection strings and URL-shaped values from anything we print."""
    s = "" if text is None else str(text)
    s = _URI_RE.sub("[REDACTED_MONGO_URL]", s)
    s = _HTTP_RE.sub("[REDACTED_URL]", s)
    s = _USERINFO_RE.sub("://[REDACTED]@", s)
    return s


def database_name_from_url(url: str) -> Optional[str]:
    """Return the database name in the URI path, or None. Never returns the URL."""
    if not url:
        return None
    rest = url.split("://", 1)[1] if "://" in url else url
    if "@" in rest:
        rest = rest.rsplit("@", 1)[1]
    if "/" not in rest:
        return None
    path = rest.split("/", 1)[1].split("?", 1)[0].strip()
    name = path.split("/")[0].strip()
    if not name or name in {".", ".."}:
        return None
    return name


def resolve_db_name(url: str, specific: str = "", fallback: str = "") -> str:
    if (specific or "").strip():
        return specific.strip()
    from_url = database_name_from_url(url)
    if from_url:
        return from_url
    if (fallback or "").strip():
        return fallback.strip()
    raise ValueError("database name missing")


def is_copyable_collection(name: str) -> bool:
    if not name or name in SKIP_COLLECTION_EXACT:
        return False
    return not name.startswith(SYSTEM_PREFIXES)


def list_copyable_collections(db: Any) -> List[str]:
    names = list(db.list_collection_names())
    return sorted(n for n in names if is_copyable_collection(n))


def count_documents(coll: Any) -> int:
    return int(coll.count_documents({}))


def upsert_collection(source_coll: Any, target_coll: Any) -> Dict[str, int]:
    """Replace each source document on the target by _id. Idempotent."""
    written = 0
    skipped = 0
    for doc in source_coll.find({}):
        if "_id" not in doc:
            skipped += 1
            continue
        target_coll.replace_one({"_id": doc["_id"]}, doc, upsert=True)
        written += 1
    return {"written": written, "skipped_no_id": skipped}


def compare_and_maybe_copy(
    source_db: Any,
    target_db: Any,
    apply: bool,
) -> List[Dict[str, Any]]:
    source_names = list_copyable_collections(source_db)
    target_names = list_copyable_collections(target_db)
    rows: List[Dict[str, Any]] = []
    for name in source_names:
        src_n = count_documents(source_db[name])
        tgt_before = count_documents(target_db[name])
        written = 0
        skipped = 0
        if apply:
            result = upsert_collection(source_db[name], target_db[name])
            written = result["written"]
            skipped = result["skipped_no_id"]
        tgt_after = count_documents(target_db[name])
        rows.append(
            {
                "collection": name,
                "source": src_n,
                "target_before": tgt_before,
                "target_after": tgt_after,
                "written": written,
                "skipped_no_id": skipped,
                "match": src_n == tgt_after,
            }
        )
    target_only = sorted(set(target_names) - set(source_names))
    return rows, target_only


def format_report(rows: List[Dict[str, Any]]) -> str:
    headers = (
        "collection",
        "source",
        "target_before",
        "target_after",
        "written",
        "skipped_no_id",
        "match",
    )
    table = [headers]
    for r in rows:
        table.append(
            (
                str(r["collection"]),
                str(r["source"]),
                str(r["target_before"]),
                str(r["target_after"]),
                str(r["written"]),
                str(r["skipped_no_id"]),
                "yes" if r["match"] else "NO",
            )
        )
    widths = [max(len(row[i]) for row in table) for i in range(len(headers))]
    lines = []
    for i, row in enumerate(table):
        line = "  ".join(row[c].ljust(widths[c]) for c in range(len(headers)))
        lines.append(line)
        if i == 0:
            lines.append("  ".join("-" * widths[c] for c in range(len(headers))))
    return "\n".join(lines)



def connect(url: str) -> Any:
    from pymongo import MongoClient

    try:
        return MongoClient(url, serverSelectionTimeoutMS=20000)
    except Exception as exc:  # pragma: no cover - exercised via injected failures
        raise RuntimeError(f"Mongo connection failed ({type(exc).__name__})") from None


def _ping(client: Any) -> None:
    admin = getattr(client, "admin", None)
    command = getattr(admin, "command", None) if admin is not None else None
    if callable(command):
        command("ping")


def main(
    argv: Optional[Sequence[str]] = None,
    connect_fn: Optional[Callable[[str], Any]] = None,
    out: Optional[Callable[..., None]] = None,
    err: Optional[Callable[..., None]] = None,
) -> int:
    def _out(msg: Any = "") -> None:
        (out or print)(redact(msg))

    def _err(msg: Any = "") -> None:
        if err is not None:
            err(redact(msg))
        else:
            print(redact(msg), file=sys.stderr)

    parser = argparse.ArgumentParser(
        description=(
            "Copy Mongo collections from SOURCE_MONGO_URL to TARGET_MONGO_URL. "
            "Dry-run (counts only) is the default. Never prints URLs."
        )
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write to the target using idempotent upserts by _id. Default is counts only.",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    source_url = os.environ.get("SOURCE_MONGO_URL", "").strip()
    target_url = os.environ.get("TARGET_MONGO_URL", "").strip()
    if not source_url or not target_url:
        _err(
            "Set SOURCE_MONGO_URL and TARGET_MONGO_URL in the environment "
            "(do not pass them as flags or paste them into chat)."
        )
        return 2

    try:
        source_db_name = resolve_db_name(
            source_url,
            os.environ.get("SOURCE_DB_NAME", ""),
            os.environ.get("DB_NAME", ""),
        )
        target_db_name = resolve_db_name(
            target_url,
            os.environ.get("TARGET_DB_NAME", ""),
            os.environ.get("DB_NAME", ""),
        )
    except ValueError:
        _err(
            "A database name is required. Put it in the URL path, or set "
            "SOURCE_DB_NAME / TARGET_DB_NAME (or DB_NAME)."
        )
        return 2

    connector = connect_fn or connect
    try:
        source_client = connector(source_url)
        target_client = connector(target_url)
    except Exception as exc:
        _err(f"Could not connect ({type(exc).__name__})")
        return 1

    try:
        try:
            _ping(source_client)
            _ping(target_client)
        except Exception as exc:
            _err(f"Could not reach Mongo ({type(exc).__name__})")
            return 1

        mode = "APPLY" if args.apply else "DRY-RUN (no writes)"
        _out(f"Mode: {mode}")
        _out(f"Source database name: {source_db_name}")
        _out(f"Target database name: {target_db_name}")
        rows, target_only = compare_and_maybe_copy(
            source_client[source_db_name],
            target_client[target_db_name],
            apply=args.apply,
        )
        if not rows:
            _out("No copyable collections found on the source.")
        else:
            _out(format_report(rows))
        if target_only:
            _out("Target-only collections (left untouched): " + ", ".join(target_only))
        mismatches = [r["collection"] for r in rows if not r["match"]]
        if args.apply and mismatches:
            _out("Count mismatch after apply for: " + ", ".join(mismatches))
            return 1
        if not args.apply:
            _out("Dry-run complete. Re-run with --apply to write (idempotent upserts by _id).")
        else:
            _out("Apply complete. Compare the source and target_after columns above.")
        return 0
    finally:
        for client in (source_client, target_client):
            closer = getattr(client, "close", None)
            if callable(closer):
                try:
                    closer()
                except Exception:
                    pass


if __name__ == "__main__":
    sys.exit(main())
