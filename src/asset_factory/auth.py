"""Local accounts, revocable cookie sessions, and API ownership checks."""
import argparse
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import threading
import time
from collections import OrderedDict
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import HTTPException, Request, Response
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool
from starlette.responses import JSONResponse

from .storage import Store, identity, now

COOKIE = "studio_session"
SESSION_SECONDS = 7 * 24 * 60 * 60
HASH_SLOTS = threading.BoundedSemaphore(2)


class Credentials(BaseModel):
    username: str = Field(min_length=3, max_length=40, pattern=r"^[a-zA-Z0-9_-]+$")
    password: str = Field(min_length=12, max_length=128)


def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    with HASH_SLOTS:
        digest = hashlib.scrypt(
            password.encode(), salt=bytes.fromhex(salt), n=2**17, r=8, p=1,
            maxmem=256 * 1024 * 1024,
        ).hex()
    return f"scrypt${salt}${digest}"


def verify_password(password, encoded):
    _, salt, _ = encoded.split("$")
    return hmac.compare_digest(password_hash(password, salt), encoded)


def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def attach_auth(app, store):
    secure = os.getenv("STUDIO_COOKIE_SECURE", "0") == "1"
    # Single-process demo guard; deployment needs a shared edge/account rate limit.
    attempts = OrderedDict()
    attempt_lock = threading.Lock()
    dummy_hash = password_hash(secrets.token_urlsafe(32))

    def rate_limit(request):
        key = request.client.host if request.client else "unknown"
        stamp = time.monotonic()
        with attempt_lock:
            count, start = attempts.get(key, (0, stamp))
            if stamp - start >= 60:
                count, start = 0, stamp
            attempts[key] = (count + 1, start)
            attempts.move_to_end(key)
            if len(attempts) > 10000:
                attempts.popitem(last=False)
            if count >= 10:
                raise HTTPException(429, "尝试过于频繁，请一分钟后再试。")

    def current_user(token):
        if not token or len(token) > 100:
            return None
        with store.connect() as db:
            row = db.execute(
                "SELECT u.id,u.username FROM sessions s JOIN users u ON u.id=s.user_id "
                "WHERE s.token_hash=? AND s.expires_at>?",
                (token_hash(token), int(time.time())),
            ).fetchone()
        return dict(row) if row else None

    def issue_session(response, user_id, previous_token):
        token = secrets.token_urlsafe(32)
        with store.connect() as db:
            db.execute("DELETE FROM sessions WHERE expires_at<=?", (int(time.time()),))
            if previous_token:
                db.execute("DELETE FROM sessions WHERE token_hash=?", (token_hash(previous_token),))
            db.execute(
                "INSERT INTO sessions VALUES (?,?,?)",
                (token_hash(token), user_id, int(time.time()) + SESSION_SECONDS),
            )
        response.set_cookie(
            COOKIE, token, max_age=SESSION_SECONDS, httponly=True,
            secure=secure, samesite="strict", path="/",
        )
        response.headers["Cache-Control"] = "no-store"

    @app.middleware("http")
    async def account_access(request, call_next):
        path = request.url.path
        if path == "/api" or path.startswith("/api/"):
            if request.method not in ("GET", "HEAD", "OPTIONS"):
                origin = request.headers.get("origin")
                expected = urlsplit(str(request.base_url))
                supplied = urlsplit(origin) if origin else None
                if request.headers.get("sec-fetch-site") == "cross-site" or (
                    supplied and (supplied.scheme, supplied.netloc) != (expected.scheme, expected.netloc)
                ):
                    return JSONResponse({"detail": "请求来源不受信任。"}, status_code=403)
            if path.rstrip("/") not in ("/api/auth/login", "/api/auth/register"):
                user = await run_in_threadpool(current_user, request.cookies.get(COOKIE))
                if not user:
                    return JSONResponse({"detail": "请先登录。"}, status_code=401)
                request.state.user = user
                parts = path.strip("/").split("/")
                if (
                    len(parts) >= 3 and parts[:2] == ["api", "projects"]
                    and not await run_in_threadpool(store.owns, parts[2], user["id"])
                ):
                    return JSONResponse({"detail": "项目不存在。"}, status_code=404)
            response = await call_next(request)
            response.headers["Cache-Control"] = "no-store"
            return response
        return await call_next(request)

    @app.post("/api/auth/register", status_code=201)
    def register(credentials: Credentials, request: Request, response: Response):
        rate_limit(request)
        username = credentials.username.lower()
        uid = identity()
        encoded = password_hash(credentials.password)
        try:
            with store.connect() as db:
                db.execute(
                    "INSERT INTO users VALUES (?,?,?,?)", (uid, username, encoded, now())
                )
        except sqlite3.IntegrityError as error:
            raise HTTPException(409, "该用户名已被使用。") from error
        issue_session(response, uid, request.cookies.get(COOKIE))
        return {"id": uid, "username": username}

    @app.post("/api/auth/login")
    def login(credentials: Credentials, request: Request, response: Response):
        rate_limit(request)
        with store.connect() as db:
            user = db.execute(
                "SELECT * FROM users WHERE username=?", (credentials.username.lower(),)
            ).fetchone()
        valid = verify_password(credentials.password, user["password_hash"] if user else dummy_hash)
        if not user or not valid:
            raise HTTPException(401, "用户名或密码错误。")
        issue_session(response, user["id"], request.cookies.get(COOKIE))
        return {"id": user["id"], "username": user["username"]}

    @app.get("/api/auth/me")
    def me(request: Request):
        return request.state.user

    @app.post("/api/auth/logout", status_code=204)
    def logout(request: Request, response: Response):
        with store.connect() as db:
            db.execute(
                "DELETE FROM sessions WHERE token_hash=?", (token_hash(request.cookies[COOKIE]),)
            )
        response.delete_cookie(COOKIE, path="/", secure=secure, httponly=True, samesite="strict")


def assign_legacy(store, username, pid=None):
    """Explicit local administration only; registration never claims old assets."""
    with store.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        user = db.execute("SELECT id FROM users WHERE username=?", (username.lower(),)).fetchone()
        if not user:
            raise ValueError("账号不存在，请先在网页注册。")
        query = "SELECT id,data FROM projects WHERE owner_id IS NULL"
        rows = db.execute(query + (" AND id=?" if pid else ""), (pid,) if pid else ()).fetchall()
        for row in rows:
            project = json.loads(row["data"])
            project["owner_id"] = user["id"]
            db.execute("UPDATE projects SET owner_id=? WHERE id=?", (user["id"], row["id"]))
            store.put(db, project)
    return len(rows)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="将未分配的历史项目交给指定已注册账号")
    parser.add_argument("--username", required=True)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--project-id")
    group.add_argument("--all-unowned", action="store_true")
    parser.add_argument("--data-dir", type=Path, default=Path(__file__).resolve().parents[2] / "data")
    args = parser.parse_args()
    print(f"已分配 {assign_legacy(Store(args.data_dir), args.username, args.project_id)} 个历史项目。")
