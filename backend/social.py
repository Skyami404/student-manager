"""Accounts (@bu.edu email + scrypt password + bearer session), friend requests, shared free windows.

Privacy: the only thing a friend can ever read is the intersection of both people's FREE windows.
No course names, buildings, or section details leave this module. Sharing is opt-in per user.
Email ownership is NOT verified.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
import time
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

import db
import leaveby
from optimizer import fmt, hm

router = APIRouter()
EMAIL_RE = re.compile(r"^[a-z0-9._%+\-]+@bu\.edu$")
SESSION_DAYS = 30
VERIFY_NOTE = "Email ownership is not verified: anyone can register any @bu.edu address, so only accept requests from people you know."
DAY_START, DAY_END, MIN_WINDOW = 8 * 60, 20 * 60, 30
WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri"]
_fails: dict[str, list[float]] = {}


def hash_pw(pw: str) -> str:
    salt = os.urandom(16)
    h = hashlib.scrypt(pw.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return f"scrypt${salt.hex()}${h.hex()}"


def verify_pw(pw: str, stored: str) -> bool:
    try:
        _, salt, h = stored.split("$")
        got = hashlib.scrypt(pw.encode(), salt=bytes.fromhex(salt), n=2**14, r=8, p=1, dklen=32)
        return hmac.compare_digest(got, bytes.fromhex(h))
    except ValueError:
        return False


def _throttle(email: str) -> None:
    recent = [t for t in _fails.get(email, []) if time.time() - t < 300]
    _fails[email] = recent
    if len(recent) >= 5:
        raise HTTPException(429, "Too many failed attempts. Try again in a few minutes.")


def _new_session(s: Session, user: db.User) -> str:
    token = secrets.token_urlsafe(32)
    s.add(db.AuthSession(token_hash=hashlib.sha256(token.encode()).hexdigest(), user_id=user.id,
                         expires_at=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=SESSION_DAYS)))
    s.commit()
    return token


def current_user(authorization: str | None = Header(default=None), s: Session = Depends(db.get_session)) -> db.User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Sign in required.")
    h = hashlib.sha256(authorization[7:].strip().encode()).hexdigest()
    sess = s.get(db.AuthSession, h)
    if not sess or sess.expires_at < datetime.now(timezone.utc).replace(tzinfo=None):
        raise HTTPException(401, "Session expired. Sign in again.")
    return s.get(db.User, sess.user_id)


def _public(u: db.User) -> dict:
    return {"id": u.id, "email": u.email, "display_name": u.display_name, "share_free_time": u.share_free_time,
            "has_schedule": bool(u.active_schedule_id and leaveby.load_schedule(u.active_schedule_id)), "email_verified": False}


class Creds(BaseModel):
    email: str = Field(max_length=120)
    password: str = Field(min_length=8, max_length=128)
    display_name: str | None = Field(default=None, max_length=40)


@router.post("/auth/register")
def register(body: Creds, s: Session = Depends(db.get_session)):
    email = body.email.strip().lower()
    if not EMAIL_RE.match(email):
        raise HTTPException(422, "Email must be a valid address ending in @bu.edu.")
    if s.scalar(select(db.User).where(db.User.email == email)):
        raise HTTPException(409, "That email is already registered. Try signing in.")
    u = db.User(email=email, password_hash=hash_pw(body.password), display_name=(body.display_name or "").strip() or None)
    s.add(u)
    s.commit()
    return {"token": _new_session(s, u), "user": _public(u), "note": VERIFY_NOTE}


@router.post("/auth/login")
def login(body: Creds, s: Session = Depends(db.get_session)):
    email = body.email.strip().lower()
    _throttle(email)
    u = s.scalar(select(db.User).where(db.User.email == email))
    if not u or not verify_pw(body.password, u.password_hash):
        _fails.setdefault(email, []).append(time.time())
        raise HTTPException(401, "Wrong email or password.")
    return {"token": _new_session(s, u), "user": _public(u), "note": VERIFY_NOTE}


@router.post("/auth/logout")
def logout(authorization: str | None = Header(default=None), s: Session = Depends(db.get_session)):
    if authorization and authorization.lower().startswith("bearer "):
        sess = s.get(db.AuthSession, hashlib.sha256(authorization[7:].strip().encode()).hexdigest())
        if sess:
            s.delete(sess)
            s.commit()
    return {"ok": True}


@router.get("/me")
def me(u: db.User = Depends(current_user)):
    return {"user": _public(u), "note": VERIFY_NOTE}


class Settings(BaseModel):
    share_free_time: bool | None = None
    display_name: str | None = Field(default=None, max_length=40)


@router.post("/me/settings")
def settings(body: Settings, u: db.User = Depends(current_user), s: Session = Depends(db.get_session)):
    if body.share_free_time is not None:
        u.share_free_time = body.share_free_time
    if body.display_name is not None:
        u.display_name = body.display_name.strip() or None
    s.commit()
    return {"user": _public(u)}


class SchedRef(BaseModel):
    schedule_id: str


@router.post("/me/schedule")
def set_schedule(body: SchedRef, u: db.User = Depends(current_user), s: Session = Depends(db.get_session)):
    if not leaveby.load_schedule(body.schedule_id):
        raise HTTPException(404, "Unknown schedule_id (generate schedules first).")
    u.active_schedule_id = body.schedule_id
    s.commit()
    return {"user": _public(u)}


class EmailBody(BaseModel):
    email: str = Field(max_length=120)


@router.post("/friends/request")
def friend_request(body: EmailBody, u: db.User = Depends(current_user), s: Session = Depends(db.get_session)):
    other = s.scalar(select(db.User).where(db.User.email == body.email.strip().lower()))
    if other and other.id != u.id:
        exists = s.scalar(select(db.Friendship).where(or_(
            (db.Friendship.user_id == u.id) & (db.Friendship.friend_id == other.id),
            (db.Friendship.user_id == other.id) & (db.Friendship.friend_id == u.id))))
        if not exists:
            s.add(db.Friendship(user_id=u.id, friend_id=other.id, status="pending"))
            s.commit()
    # same answer whether or not the address has an account
    return {"ok": True, "message": "If that @bu.edu address has an account, a request was sent."}


class AcceptBody(BaseModel):
    request_id: int


@router.post("/friends/accept")
def friend_accept(body: AcceptBody, u: db.User = Depends(current_user), s: Session = Depends(db.get_session)):
    f = s.get(db.Friendship, body.request_id)
    if not f or f.friend_id != u.id or f.status != "pending":
        raise HTTPException(404, "No such pending request.")
    f.status = "accepted"
    s.commit()
    return {"ok": True}


def _label(x: db.User) -> dict:
    return {"id": x.id, "display_name": x.display_name, "email": x.email, "shares_free_time": x.share_free_time}


@router.get("/friends")
def friends(u: db.User = Depends(current_user), s: Session = Depends(db.get_session)):
    rows = s.scalars(select(db.Friendship).where(or_(db.Friendship.user_id == u.id, db.Friendship.friend_id == u.id))).all()
    out = {"friends": [], "incoming": [], "outgoing": [], "note": VERIFY_NOTE}
    for f in rows:
        other = s.get(db.User, f.friend_id if f.user_id == u.id else f.user_id)
        if f.status == "accepted":
            out["friends"].append(_label(other))
        elif f.friend_id == u.id:
            out["incoming"].append({"request_id": f.id, **_label(other)})
        else:
            out["outgoing"].append({"request_id": f.id, "email": other.email})
    return out


def _free(entry: dict) -> dict[str, list[tuple[int, int]]]:
    free = {}
    for d in WEEKDAYS:
        busy = sorted((hm(x["start"]), hm(x["end"])) for x in entry["schedule"]["sections"] if timed_d(x) and d in x["days"])
        cur, out = DAY_START, []
        for a, b in busy:
            if a > cur:
                out.append((cur, min(a, DAY_END)))
            cur = max(cur, b)
        if cur < DAY_END:
            out.append((cur, DAY_END))
        free[d] = [(a, b) for a, b in out if b > a]
    return free


def timed_d(x: dict) -> bool:
    return bool(x["days"] and x["start"] and x["end"])


@router.get("/friends/free-gaps")
def free_gaps(friend_id: int, u: db.User = Depends(current_user), s: Session = Depends(db.get_session)):
    """Windows when BOTH of you are free (Mon-Fri, 08:00-20:00, 30+ min). Times only: no course names."""
    friend = s.get(db.User, friend_id)
    ok = friend and s.scalar(select(db.Friendship).where(db.Friendship.status == "accepted", or_(
        (db.Friendship.user_id == u.id) & (db.Friendship.friend_id == friend_id),
        (db.Friendship.user_id == friend_id) & (db.Friendship.friend_id == u.id))))
    if not ok:
        raise HTTPException(404, "Not a friend.")
    if not friend.share_free_time:
        raise HTTPException(403, "This friend has not turned on free-time sharing.")
    mine = leaveby.load_schedule(u.active_schedule_id) if u.active_schedule_id else None
    theirs = leaveby.load_schedule(friend.active_schedule_id) if friend.active_schedule_id else None
    if not mine:
        raise HTTPException(409, "Pick a schedule and sync it first (Week tab).")
    if not theirs:
        raise HTTPException(409, "This friend has not synced a schedule yet.")
    fa, fb = _free(mine), _free(theirs)
    windows = {}
    for d in WEEKDAYS:
        both = []
        for a1, b1 in fa[d]:
            for a2, b2 in fb[d]:
                lo, hi = max(a1, a2), min(b1, b2)
                if hi - lo >= MIN_WINDOW:
                    both.append({"start": fmt(lo), "end": fmt(hi), "minutes": hi - lo})
        windows[d] = both
    return {"friend": {"id": friend.id, "display_name": friend.display_name}, "windows": windows,
            "privacy": "Only times when you are both free are shown. Neither side's classes are revealed."}
