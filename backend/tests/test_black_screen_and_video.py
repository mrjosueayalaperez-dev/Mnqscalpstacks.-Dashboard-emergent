"""Tests for black-screen fixes, proof video support, and Stripe checkout regression."""
import os
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
API = f"{BASE_URL}/api"


# ----- Proof gallery: video item -----
class TestProofVideo:
    def test_list_contains_video_item(self):
        r = requests.get(f"{API}/proof/list", timeout=30)
        assert r.status_code == 200
        shots = r.json()["shots"]
        assert len(shots) >= 4, f"expected >=4 shots, got {len(shots)}"
        videos = [s for s in shots if s["content_type"].startswith("video/")]
        assert len(videos) >= 1, f"no video item found. content_types={[s['content_type'] for s in shots]}"
        v = videos[0]
        assert v["content_type"] in ("video/mp4", "video/webm")
        assert v["size"] > 1_000_000  # ~8.6MB expected

    def test_video_bytes_served(self):
        shots = requests.get(f"{API}/proof/list", timeout=30).json()["shots"]
        videos = [s for s in shots if s["content_type"].startswith("video/")]
        assert videos, "no video shot"
        vid = videos[0]
        r = requests.get(f"{API}/proof/image/{vid['id']}", timeout=120)
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("video/")
        assert len(r.content) == vid["size"]


# ----- Stripe checkout regression -----
class TestCheckoutFlow:
    def test_create_pro_checkout_and_status(self):
        origin = BASE_URL  # frontend origin equals same host in preview
        r = requests.post(
            f"{API}/checkout/create",
            json={"tier": "pro", "origin_url": origin},
            timeout=30,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert "url" in body and body["url"].startswith("http")
        assert "session_id" in body and body["session_id"]

        sid = body["session_id"]
        s = requests.get(f"{API}/checkout/status/{sid}", timeout=30)
        assert s.status_code == 200, s.text
        sb = s.json()
        assert "status" in sb
        assert "payment_status" in sb
        assert sb.get("amount_total") == 4900, f"expected 4900, got {sb.get('amount_total')}"
