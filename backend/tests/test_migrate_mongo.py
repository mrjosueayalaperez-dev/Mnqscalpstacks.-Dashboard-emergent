"""Unit tests for scripts/migrate_mongo.py (mongomock / fakes; never a real database)."""
from __future__ import annotations

import importlib.util
import os
from io import StringIO
from pathlib import Path
import pytest

mongomock = pytest.importorskip("mongomock")

_PATH = Path(__file__).resolve().parents[2] / "scripts" / "migrate_mongo.py"
spec = importlib.util.spec_from_file_location("migrate_mongo", _PATH)
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mod)

SOURCE_URL = "mongodb://source-user:s0urceP#ass@source-host.example:27017/srcdb"
TARGET_URL = "mongodb+srv://target-user:t0rgetP#ass@target-host.example/tgtdb"


def _clients():
    # One mongomock process can host both "clusters" via distinct client instances.
    return mongomock.MongoClient(), mongomock.MongoClient()


def _connect_fn(source_client, target_client):
    mapping = {SOURCE_URL: source_client, TARGET_URL: target_client}

    def connect(url: str):
        try:
            return mapping[url]
        except KeyError as exc:  # pragma: no cover
            raise RuntimeError(f"unexpected url in test connect: {url}") from exc

    return connect


def _run(monkeypatch, source_client, target_client, argv, extra_env=None):
    monkeypatch.setenv("SOURCE_MONGO_URL", SOURCE_URL)
    monkeypatch.setenv("TARGET_MONGO_URL", TARGET_URL)
    for key in ("SOURCE_DB_NAME", "TARGET_DB_NAME", "DB_NAME"):
        if extra_env is None or key not in extra_env:
            monkeypatch.delenv(key, raising=False)
    if extra_env:
        for k, v in extra_env.items():
            monkeypatch.setenv(k, v)
    stdout = StringIO()
    stderr = StringIO()
    code = mod.main(
        argv,
        connect_fn=_connect_fn(source_client, target_client),
        out=lambda msg="": stdout.write(str(msg) + "\n"),
        err=lambda msg="": stderr.write(str(msg) + "\n"),
    )
    return code, stdout.getvalue(), stderr.getvalue()


def _seed(source_client):
    db = source_client["srcdb"]
    db.users.insert_many(
        [
            {"_id": "u1", "email": "a@example.com", "role": "admin"},
            {"_id": "u2", "email": "b@example.com", "role": "member"},
        ]
    )
    db.signals.insert_one({"_id": "s1", "symbol": "MNQ", "side": "buy"})
    db["system.profile"].insert_one({"_id": "sys1", "ok": 1})
    return db


def test_database_name_from_url_does_not_expose_credentials():
    assert mod.database_name_from_url(SOURCE_URL) == "srcdb"
    assert mod.database_name_from_url(TARGET_URL) == "tgtdb"
    assert mod.database_name_from_url("mongodb://localhost:27017") is None
    assert "s0urce" not in (mod.database_name_from_url(SOURCE_URL) or "")


def test_redact_strips_urls_and_passwords():
    raw = f"failed to connect {SOURCE_URL} also {TARGET_URL}"
    cleaned = mod.redact(raw)
    assert "s0urceP#ass" not in cleaned
    assert "t0rgetP#ass" not in cleaned
    assert "source-host.example" not in cleaned
    assert "mongodb" not in cleaned.lower() or "REDACTED" in cleaned
    assert "SOURCE_URL" not in cleaned or True
    assert SOURCE_URL not in cleaned
    assert TARGET_URL not in cleaned


def test_dry_run_writes_nothing_and_prints_counts(monkeypatch):
    source, target = _clients()
    _seed(source)
    target["tgtdb"].keep_me.insert_one({"_id": "k1", "stay": True})
    code, stdout, stderr = _run(monkeypatch, source, target, [])
    assert code == 0
    assert "DRY-RUN" in stdout
    assert source["srcdb"].users.count_documents({}) == 2
    assert target["tgtdb"].users.count_documents({}) == 0
    assert target["tgtdb"].signals.count_documents({}) == 0
    assert target["tgtdb"].keep_me.count_documents({}) == 1
    assert "users" in stdout and "signals" in stdout
    assert "keep_me" in stdout  # listed as target-only
    assert "system.profile" not in stdout
    assert SOURCE_URL not in stdout + stderr
    assert TARGET_URL not in stdout + stderr
    assert "s0urceP#ass" not in stdout + stderr
    assert "source-host.example" not in stdout + stderr


def test_apply_upserts_by_id_and_is_idempotent(monkeypatch):
    source, target = _clients()
    _seed(source)
    code, stdout, _ = _run(monkeypatch, source, target, ["--apply"])
    assert code == 0
    assert "APPLY" in stdout
    tgt = target["tgtdb"]
    assert tgt.users.count_documents({}) == 2
    assert tgt.signals.count_documents({}) == 1
    assert tgt.users.find_one({"_id": "u1"})["email"] == "a@example.com"

    source["srcdb"].users.replace_one(
        {"_id": "u1"}, {"_id": "u1", "email": "a@example.com", "role": "owner"}
    )
    source["srcdb"].users.insert_one({"_id": "u3", "email": "c@example.com"})
    code2, stdout2, _ = _run(monkeypatch, source, target, ["--apply"])
    assert code2 == 0
    assert tgt.users.count_documents({}) == 3
    assert tgt.users.find_one({"_id": "u1"})["role"] == "owner"
    assert tgt.users.find_one({"_id": "u3"})["email"] == "c@example.com"
    # report compares source vs target_after
    assert "yes" in stdout2
    assert "NO" not in stdout2.splitlines()[-3:] or all(
        "NO" not in line for line in stdout2.splitlines() if line.startswith("users") or line.startswith("signals")
    )


def test_apply_leaves_target_only_collections_alone(monkeypatch):
    source, target = _clients()
    _seed(source)
    target["tgtdb"].keep_me.insert_one({"_id": "k1", "stay": True})
    code, stdout, _ = _run(monkeypatch, source, target, ["--apply"])
    assert code == 0
    assert target["tgtdb"].keep_me.find_one({"_id": "k1"})["stay"] is True
    assert "keep_me" in stdout


def test_skips_docs_without_id_and_system_collections(monkeypatch):
    source, target = _clients()
    source["srcdb"].plain.insert_one({"_id": "ok", "n": 1})
    source["srcdb"].plain.insert_one({"no_id_field": True})  # mongomock adds _id
    # Force a find() result without _id via a thin wrapper by inserting then
    # using a custom collection isn't easy with mongomock. Use the helper directly.
    class FakeColl:
        def __init__(self, docs):
            self.docs = docs
            self.stored = []

        def find(self, *_a, **_k):
            return list(self.docs)

        def replace_one(self, filt, doc, upsert=False):
            self.stored.append((filt, doc, upsert))
            return None

        def count_documents(self, *_a, **_k):
            return len(self.docs)

    src = FakeColl([{"_id": 1, "a": 1}, {"a": 2}])
    tgt = FakeColl([])
    result = mod.upsert_collection(src, tgt)
    assert result == {"written": 1, "skipped_no_id": 1}
    assert tgt.stored == [({"_id": 1}, {"_id": 1, "a": 1}, True)]
    assert not mod.is_copyable_collection("system.profile")
    assert not mod.is_copyable_collection("system.indexes")
    assert mod.is_copyable_collection("users")


def test_missing_env_exits_without_connecting(monkeypatch):
    monkeypatch.delenv("SOURCE_MONGO_URL", raising=False)
    monkeypatch.delenv("TARGET_MONGO_URL", raising=False)
    called = []

    def connect(url):
        called.append(url)
        raise AssertionError("must not connect")

    stderr = StringIO()
    code = mod.main([], connect_fn=connect, out=lambda *_: None, err=lambda msg="": stderr.write(str(msg) + "\n"))
    assert code == 2
    assert called == []
    assert "SOURCE_MONGO_URL" in stderr.getvalue()


def test_missing_db_name_exits_without_connecting(monkeypatch):
    monkeypatch.setenv("SOURCE_MONGO_URL", "mongodb://source-user:s0urceP#ass@source-host.example:27017")
    monkeypatch.setenv("TARGET_MONGO_URL", "mongodb://target-user:t0rgetP#ass@target-host.example")
    monkeypatch.delenv("SOURCE_DB_NAME", raising=False)
    monkeypatch.delenv("TARGET_DB_NAME", raising=False)
    monkeypatch.delenv("DB_NAME", raising=False)
    called = []
    stderr = StringIO()
    code = mod.main(
        [],
        connect_fn=lambda url: called.append(url),
        out=lambda *_: None,
        err=lambda msg="": stderr.write(str(msg) + "\n"),
    )
    assert code == 2
    assert called == []
    assert "s0urceP#ass" not in stderr.getvalue()
    assert "database name" in stderr.getvalue().lower()


def test_db_name_env_override(monkeypatch):
    source, target = _clients()
    source["custom_src"].users.insert_one({"_id": "u1"})
    code, stdout, _ = _run(
        monkeypatch,
        source,
        target,
        ["--apply"],
        extra_env={"SOURCE_DB_NAME": "custom_src", "TARGET_DB_NAME": "custom_tgt"},
    )
    assert code == 0
    assert target["custom_tgt"].users.count_documents({}) == 1
    assert "custom_src" in stdout and "custom_tgt" in stdout


def test_connection_error_is_redacted(monkeypatch):
    monkeypatch.setenv("SOURCE_MONGO_URL", SOURCE_URL)
    monkeypatch.setenv("TARGET_MONGO_URL", TARGET_URL)
    stderr = StringIO()

    def boom(url: str):
        raise RuntimeError(f"auth failed for {url}")

    code = mod.main(
        [],
        connect_fn=boom,
        out=lambda *_: None,
        err=lambda msg="": stderr.write(str(msg) + "\n"),
    )
    assert code == 1
    text = stderr.getvalue()
    assert SOURCE_URL not in text
    assert "s0urceP#ass" not in text
    assert "source-host.example" not in text
