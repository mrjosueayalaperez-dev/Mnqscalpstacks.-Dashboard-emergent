"""Unified authentication: email/password JWT + Emergent Google OAuth sessions.

A request is authenticated by EITHER:
  1. JWT access token  — `access_token` cookie or `Authorization: Bearer`
  2. Google session    — `session_token` cookie or `Authorization: Bearer`
Both resolve to the same `users` collection document.
"""
import os
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional

import bcrypt
import httpx
import jwt
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr

JWT_ALGORITHM = "HS256"
EMERGENT_SESSION_URL = "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data"
LOCKOUT_ATTEMPTS = 5
LOCKOUT_MINUTES = 15


def _jwt_secret() -> str:
    return os.environ["JWT_SECRET"]


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def create_access_token(user_id: str, email: str) -> str:
    payload = {"sub": user_id, "email": email, "type": "access",
               "exp": datetime.now(timezone.utc) + timedelta(minutes=60)}
    return jwt.encode(payload, _jwt_secret(), algorithm=JWT_ALGORITHM)


def create_refresh_token(user_id: str) -> str:
    payload = {"sub": user_id, "type": "refresh",
               "exp": datetime.now(timezone.utc) + timedelta(days=7)}
    return jwt.encode(payload, _jwt_secret(), algorithm=JWT_ALGORITHM)


def _set_jwt_cookies(response: Response, access: str, refresh: str) -> None:
    response.set_cookie("access_token", access, httponly=True, secure=True,
                        samesite="none", max_age=3600, path="/")
    response.set_cookie("refresh_token", refresh, httponly=True, secure=True,
                        samesite="none", max_age=604800, path="/")


def _public_user(doc: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "user_id": doc["user_id"],
        "email": doc["email"],
        "name": doc.get("name", ""),
        "picture": doc.get("picture", ""),
        "role": doc.get("role", "user"),
        "tier": doc.get("tier", "free"),
    }


def _role_for(email: str) -> str:
    return "admin" if email.lower() == os.environ.get("ADMIN_EMAIL", "").lower() else "user"


class RegisterBody(BaseModel):
    email: EmailStr
    password: str
    name: str = ""


class LoginBody(BaseModel):
    email: EmailStr
    password: str


class SessionBody(BaseModel):
    session_id: str


async def get_current_user(request: Request, db: Any) -> Dict[str, Any]:
    """Resolve a user from JWT access token OR Google session token."""
    bearer = ""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        bearer = auth_header[7:]

    # 1) JWT path
    token = request.cookies.get("access_token") or bearer
    if token:
        try:
            payload = jwt.decode(token, _jwt_secret(), algorithms=[JWT_ALGORITHM])
            if payload.get("type") == "access":
                user = await db.users.find_one({"user_id": payload["sub"]}, {"_id": 0})
                if user:
                    return user
        except jwt.InvalidTokenError:
            pass  # fall through to session token path

    # 2) Google session path
    session_token = request.cookies.get("session_token") or bearer
    if session_token:
        session = await db.user_sessions.find_one({"session_token": session_token}, {"_id": 0})
        if session:
            expires_at = session["expires_at"]
            if isinstance(expires_at, str):
                expires_at = datetime.fromisoformat(expires_at)
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if expires_at >= datetime.now(timezone.utc):
                user = await db.users.find_one({"user_id": session["user_id"]}, {"_id": 0})
                if user:
                    return user

    raise HTTPException(status_code=401, detail="Not authenticated")


async def seed_admin(db: Any) -> None:
    """Idempotent owner/admin account from env (updates hash if env password changed)."""
    email = os.environ.get("ADMIN_EMAIL", "").lower()
    password = os.environ.get("ADMIN_PASSWORD", "")
    if not email or not password:
        return
    existing = await db.users.find_one({"email": email}, {"_id": 0})
    if existing is None:
        await db.users.insert_one({
            "user_id": f"user_{uuid.uuid4().hex[:12]}",
            "email": email,
            "name": "Operator",
            "password_hash": hash_password(password),
            "role": "admin",
            "tier": "elite",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
    elif not existing.get("password_hash") or not verify_password(password, existing["password_hash"]):
        await db.users.update_one(
            {"email": email},
            {"$set": {"password_hash": hash_password(password), "role": "admin"}},
        )


async def _check_lockout(db: Any, identifier: str) -> None:
    doc = await db.login_attempts.find_one({"identifier": identifier}, {"_id": 0})
    if doc and doc.get("count", 0) >= LOCKOUT_ATTEMPTS:
        last = datetime.fromisoformat(doc["last_attempt"])
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) - last < timedelta(minutes=LOCKOUT_MINUTES):
            raise HTTPException(status_code=429, detail="Too many failed attempts. Try again in 15 minutes.")
        await db.login_attempts.delete_one({"identifier": identifier})


async def _record_failure(db: Any, identifier: str) -> None:
    await db.login_attempts.update_one(
        {"identifier": identifier},
        {"$inc": {"count": 1}, "$set": {"last_attempt": datetime.now(timezone.utc).isoformat()}},
        upsert=True,
    )


def build_auth_router(db: Any) -> APIRouter:
    router = APIRouter(prefix="/auth", tags=["auth"])

    @router.post("/register")
    async def register(body: RegisterBody, response: Response) -> Dict[str, Any]:
        email = body.email.lower()
        if len(body.password) < 6:
            raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
        if await db.users.find_one({"email": email}, {"_id": 0, "user_id": 1}):
            raise HTTPException(status_code=409, detail="An account with this email already exists")
        doc = {
            "user_id": f"user_{uuid.uuid4().hex[:12]}",
            "email": email,
            "name": body.name.strip() or email.split("@")[0],
            "password_hash": hash_password(body.password),
            "role": _role_for(email),
            "tier": "free",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.users.insert_one(dict(doc))
        _set_jwt_cookies(response, create_access_token(doc["user_id"], email), create_refresh_token(doc["user_id"]))
        return _public_user(doc)

    @router.post("/login")
    async def login(body: LoginBody, request: Request, response: Response) -> Dict[str, Any]:
        email = body.email.lower()
        identifier = f"{request.client.host if request.client else 'unknown'}:{email}"
        await _check_lockout(db, identifier)
        user = await db.users.find_one({"email": email}, {"_id": 0})
        if not user or not user.get("password_hash") or not verify_password(body.password, user["password_hash"]):
            await _record_failure(db, identifier)
            raise HTTPException(status_code=401, detail="Invalid email or password")
        await db.login_attempts.delete_one({"identifier": identifier})
        _set_jwt_cookies(response, create_access_token(user["user_id"], email), create_refresh_token(user["user_id"]))
        return _public_user(user)

    @router.post("/session")
    async def google_session(body: SessionBody, response: Response) -> Dict[str, Any]:
        """Exchange an Emergent OAuth session_id for a 7-day session token."""
        async with httpx.AsyncClient(timeout=15) as client:
            res = await client.get(EMERGENT_SESSION_URL, headers={"X-Session-ID": body.session_id})
        if res.status_code != 200:
            raise HTTPException(status_code=401, detail="Invalid session")
        data = res.json()
        email = data["email"].lower()

        user = await db.users.find_one({"email": email}, {"_id": 0})
        if user is None:
            user = {
                "user_id": f"user_{uuid.uuid4().hex[:12]}",
                "email": email,
                "name": data.get("name", ""),
                "picture": data.get("picture", ""),
                "role": _role_for(email),
                "tier": "free",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            await db.users.insert_one(dict(user))
        else:
            await db.users.update_one(
                {"email": email},
                {"$set": {"name": data.get("name") or user.get("name", ""),
                          "picture": data.get("picture") or user.get("picture", "")}},
            )

        session_token = data["session_token"]
        await db.user_sessions.insert_one({
            "user_id": user["user_id"],
            "session_token": session_token,
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        response.set_cookie("session_token", session_token, httponly=True, secure=True,
                            samesite="none", max_age=604800, path="/")
        return _public_user(user)

    @router.get("/me")
    async def me(request: Request) -> Dict[str, Any]:
        user = await get_current_user(request, db)
        return _public_user(user)

    @router.post("/refresh")
    async def refresh(request: Request, response: Response) -> Dict[str, Any]:
        token = request.cookies.get("refresh_token", "")
        try:
            payload = jwt.decode(token, _jwt_secret(), algorithms=[JWT_ALGORITHM])
            if payload.get("type") != "refresh":
                raise jwt.InvalidTokenError()
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=401, detail="Invalid refresh token")
        user = await db.users.find_one({"user_id": payload["sub"]}, {"_id": 0})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        response.set_cookie("access_token", create_access_token(user["user_id"], user["email"]),
                            httponly=True, secure=True, samesite="none", max_age=3600, path="/")
        return _public_user(user)

    @router.post("/logout")
    async def logout(request: Request, response: Response) -> Dict[str, Any]:
        session_token = request.cookies.get("session_token")
        if session_token:
            await db.user_sessions.delete_one({"session_token": session_token})
        for cookie in ("access_token", "refresh_token", "session_token"):
            response.delete_cookie(cookie, path="/", secure=True, samesite="none")
        return {"ok": True}

    return router
