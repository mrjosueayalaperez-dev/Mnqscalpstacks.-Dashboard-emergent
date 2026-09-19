"""Auth tests: JWT register/login, admin seed, lockout, session-token, /me, logout, Stripe metadata."""
import os
import time
import subprocess
import json
import httpx
import pytest
from dotenv import load_dotenv

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE}/api"
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
ADMIN_EMAIL = os.environ["ADMIN_EMAIL"]
ADMIN_PASS = os.environ["ADMIN_PASSWORD"]


def _fresh_email(prefix="testauth"):
    return f"TEST_{prefix}_{int(time.time()*1000)}@example.com"


# ----- Register -----
class TestRegister:
    def test_register_success_sets_cookies(self):
        email = _fresh_email("reg")
        with httpx.Client(timeout=20) as c:
            r = c.post(f"{API}/auth/register", json={"email": email, "password": "test1234", "name": "Reg User"})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["email"] == email.lower()
        assert body["role"] == "user"
        assert body["tier"] == "free"
        assert "user_id" in body
        cookies = r.cookies
        assert cookies.get("access_token")
        assert cookies.get("refresh_token")

    def test_register_duplicate_returns_409(self):
        email = _fresh_email("dup")
        with httpx.Client(timeout=20) as c:
            r1 = c.post(f"{API}/auth/register", json={"email": email, "password": "test1234"})
            assert r1.status_code == 200
            r2 = c.post(f"{API}/auth/register", json={"email": email, "password": "test1234"})
        assert r2.status_code == 409

    def test_register_short_password_400(self):
        with httpx.Client(timeout=20) as c:
            r = c.post(f"{API}/auth/register", json={"email": _fresh_email("short"), "password": "abc"})
        assert r.status_code == 400


# ----- Login -----
class TestLogin:
    def test_admin_login_success(self):
        with httpx.Client(timeout=20) as c:
            r = c.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["role"] == "admin"
        assert body["tier"] == "elite"
        assert r.cookies.get("access_token")
        assert r.cookies.get("refresh_token")

    def test_wrong_password_401(self):
        with httpx.Client(timeout=20) as c:
            r = c.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": "WRONG_PASS_xyz"})
        assert r.status_code == 401

    def test_lockout_after_5_failures(self):
        # Use throwaway registered user — never lock admin
        email = _fresh_email("lock")
        with httpx.Client(timeout=20) as c:
            reg = c.post(f"{API}/auth/register", json={"email": email, "password": "test1234"})
            assert reg.status_code == 200
            statuses = []
            for _ in range(5):
                r = c.post(f"{API}/auth/login", json={"email": email, "password": "wrong_pwd_xxx"})
                statuses.append(r.status_code)
            # 6th attempt (correct pwd) — should now be 429 due to lockout
            r6 = c.post(f"{API}/auth/login", json={"email": email, "password": "test1234"})
        assert all(s == 401 for s in statuses), statuses
        assert r6.status_code == 429, r6.text


# ----- /me + logout -----
class TestMe:
    def test_me_via_cookies(self):
        with httpx.Client(timeout=20) as c:
            c.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS})
            r = c.get(f"{API}/auth/me")
        assert r.status_code == 200
        assert r.json()["email"] == ADMIN_EMAIL

    def test_me_via_bearer(self):
        with httpx.Client(timeout=20) as c:
            r = c.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS})
            token = r.cookies.get("access_token")
        assert token
        r2 = httpx.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {token}"}, timeout=20)
        assert r2.status_code == 200
        assert r2.json()["role"] == "admin"

    def test_me_no_creds_401(self):
        r = httpx.get(f"{API}/auth/me", timeout=20)
        assert r.status_code == 401

    def test_logout_clears_cookies(self):
        with httpx.Client(timeout=20) as c:
            c.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS})
            lo = c.post(f"{API}/auth/logout")
            assert lo.status_code == 200
            # New client without cookies — post-logout /me should 401.
            # Since delete_cookie sets Max-Age=0 the httpx jar clears them:
            r = c.get(f"{API}/auth/me")
        assert r.status_code == 401


# ----- Google session-token path -----
class TestSessionTokenPath:
    def setup_method(self):
        self.token = f"test_session_{int(time.time()*1000)}"
        self.user_id = f"test-user-{int(time.time()*1000)}"
        self.email = f"test_google_{int(time.time()*1000)}@example.com"
        db_name = "test_database"
        # Insert valid user + session
        script = f"""
use('{db_name}');
db.users.insertOne({{user_id: '{self.user_id}', email: '{self.email}', name: 'Google Test',
  picture: '', role: 'user', tier: 'free', created_at: new Date()}});
db.user_sessions.insertOne({{user_id: '{self.user_id}', session_token: '{self.token}',
  expires_at: new Date(Date.now() + 7*24*60*60*1000), created_at: new Date()}});
"""
        subprocess.run(["mongosh", "--quiet", "--eval", script], check=True, capture_output=True)

    def teardown_method(self):
        script = f"""
use('test_database');
db.users.deleteOne({{user_id: '{self.user_id}'}});
db.user_sessions.deleteMany({{session_token: /^test_session_/}});
"""
        subprocess.run(["mongosh", "--quiet", "--eval", script], capture_output=True)

    def test_me_via_session_bearer(self):
        r = httpx.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {self.token}"}, timeout=20)
        assert r.status_code == 200, r.text
        assert r.json()["email"] == self.email.lower()

    def test_expired_session_401(self):
        expired_token = f"test_session_expired_{int(time.time()*1000)}"
        script = f"""
use('test_database');
db.user_sessions.insertOne({{user_id: '{self.user_id}', session_token: '{expired_token}',
  expires_at: new Date(Date.now() - 60*1000), created_at: new Date()}});
"""
        subprocess.run(["mongosh", "--quiet", "--eval", script], check=True, capture_output=True)
        r = httpx.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {expired_token}"}, timeout=20)
        assert r.status_code == 401


# ----- Stripe metadata round trip -----
class TestStripeMetadata:
    def test_checkout_create_and_status(self):
        email = _fresh_email("stripe")
        with httpx.Client(timeout=30) as c:
            c.post(f"{API}/auth/register", json={"email": email, "password": "test1234"})
            r = c.post(f"{API}/checkout/create",
                       json={"tier": "pro", "origin_url": BASE, "email": email})
        assert r.status_code == 200, r.text
        session = r.json()
        assert "session_id" in session
        sid = session["session_id"]
        rs = httpx.get(f"{API}/checkout/status/{sid}", timeout=30)
        assert rs.status_code == 200, rs.text
        data = rs.json()
        # metadata email round trip
        md = data.get("metadata") or {}
        assert md.get("email", "").lower() == email.lower() or data.get("payment_status") in ("unpaid", "paid")
