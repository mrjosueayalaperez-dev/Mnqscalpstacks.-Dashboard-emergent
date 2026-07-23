"""Backend tests for Verified Results proof gallery CRUD.

Covers:
 - GET /api/proof/list (metadata only, no base64 leak)
 - GET /api/proof/image/{id} (bytes + 404)
 - POST /api/proof/upload (valid PNG + reject .txt)
 - DELETE /api/proof/{id}
"""
import base64
import io
import os
import struct
import zlib

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/") or "https://mnq-scalp-stack.preview.emergentagent.com"
API = f"{BASE_URL}/api"


def _make_png(width: int = 4, height: int = 4) -> bytes:
    """Generate a tiny valid PNG in-memory (no PIL dependency)."""
    def chunk(tag: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    raw = b""
    for _ in range(height):
        raw += b"\x00" + b"\x22\x88\x44" * width
    idat = chunk(b"IDAT", zlib.compress(raw))
    iend = chunk(b"IEND", b"")
    return sig + ihdr + idat + iend


@pytest.fixture(scope="module")
def api_session():
    s = requests.Session()
    return s


# ---- LIST endpoint ----

class TestProofList:
    def test_list_returns_shots_array(self, api_session):
        r = api_session.get(f"{API}/proof/list", timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "shots" in data
        assert isinstance(data["shots"], list)

    def test_list_has_seeded_items(self, api_session):
        r = api_session.get(f"{API}/proof/list", timeout=30)
        shots = r.json()["shots"]
        assert len(shots) >= 2, f"Expected >= 2 seeded shots, got {len(shots)}"

    def test_list_item_shape_and_no_base64_leak(self, api_session):
        shots = api_session.get(f"{API}/proof/list", timeout=30).json()["shots"]
        for s in shots:
            for k in ("id", "caption", "content_type", "size", "uploaded_at", "url"):
                assert k in s, f"Missing key {k} in shot: {s}"
            assert "data" not in s, "base64 'data' field must not leak in list"
            assert s["url"] == f"/api/proof/image/{s['id']}"
            assert isinstance(s["size"], int) and s["size"] > 0


# ---- IMAGE endpoint ----

class TestProofImage:
    def test_image_bytes_served(self, api_session):
        shots = api_session.get(f"{API}/proof/list", timeout=30).json()["shots"]
        assert shots, "need at least one shot"
        pid = shots[0]["id"]
        r = api_session.get(f"{API}/proof/image/{pid}", timeout=60)
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("image/")
        assert len(r.content) > 100, "image content trivially small"

    def test_image_unknown_id_returns_404(self, api_session):
        r = api_session.get(f"{API}/proof/image/does-not-exist-xyz", timeout=30)
        assert r.status_code == 404


# ---- UPLOAD + DELETE ----

class TestProofUploadDelete:
    def test_upload_png_appears_in_list_then_delete(self, api_session):
        png_bytes = _make_png()
        files = {"file": ("TEST_proof.png", io.BytesIO(png_bytes), "image/png")}
        data = {"caption": "TEST_upload proof gallery"}
        r = api_session.post(f"{API}/proof/upload", files=files, data=data, timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("ok") is True
        assert "id" in body and body["id"]
        assert body["url"] == f"/api/proof/image/{body['id']}"
        assert body["size"] == len(png_bytes)
        new_id = body["id"]

        # Verify it appears in list
        listed = api_session.get(f"{API}/proof/list", timeout=30).json()["shots"]
        ids = [s["id"] for s in listed]
        assert new_id in ids, f"Uploaded id not in list: {ids}"

        # Verify bytes fetchable
        img = api_session.get(f"{API}/proof/image/{new_id}", timeout=30)
        assert img.status_code == 200
        assert img.headers.get("content-type") == "image/png"
        assert img.content == png_bytes, "roundtrip bytes mismatch"

        # Delete
        d = api_session.delete(f"{API}/proof/{new_id}", timeout=30)
        assert d.status_code == 200, d.text
        assert d.json().get("ok") is True

        # Confirm gone
        listed_after = api_session.get(f"{API}/proof/list", timeout=30).json()["shots"]
        ids_after = [s["id"] for s in listed_after]
        assert new_id not in ids_after
        # Image now 404
        gone = api_session.get(f"{API}/proof/image/{new_id}", timeout=30)
        assert gone.status_code == 404

    def test_upload_rejects_txt(self, api_session):
        files = {"file": ("bogus.txt", io.BytesIO(b"not an image"), "text/plain")}
        data = {"caption": "TEST_bad type"}
        r = api_session.post(f"{API}/proof/upload", files=files, data=data, timeout=30)
        assert r.status_code == 400

    def test_delete_unknown_id_404(self, api_session):
        r = api_session.delete(f"{API}/proof/does-not-exist-xyz", timeout=30)
        assert r.status_code == 404

    def test_seeded_shots_preserved(self, api_session):
        """Regression: ensure the 2 seeded shots still exist after CRUD."""
        shots = api_session.get(f"{API}/proof/list", timeout=30).json()["shots"]
        captions = " | ".join((s.get("caption") or "") for s in shots)
        # Loose match on seeded caption fragments per problem statement
        assert "P&L" in captions or "Nasdaq" in captions or "Micro E-mini" in captions, (
            f"Seeded captions missing. Captions: {captions}"
        )
        assert len(shots) >= 2
