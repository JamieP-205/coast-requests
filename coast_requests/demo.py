"""A public demo of the request board with fictional requests.

Each visitor gets a private in-memory database, so nobody sees anyone else's
changes. The demo has no username or password, no webhook secret and no
connection to the station's website, so it can't reach real requests,
listener details or anything that affects the station.

Run it with:  flask --app coast_requests.demo:create_demo_app run
"""

import os
import random
import secrets
import threading
import time
from collections import deque
from datetime import timedelta

from flask import Blueprint, abort, current_app, flash, g, redirect, request, session, url_for
from flask_sqlalchemy.session import Session as FlaskSession
from sqlalchemy import create_engine, func, select
from sqlalchemy.pool import StaticPool

from . import create_app
from .models import Base, SongRequest, db, utc_now
from .webhook import clean

IDLE_SECONDS = 60 * 60
MAX_AGE_SECONDS = 2 * 60 * 60
MAX_SANDBOXES = 200
MAX_REQUESTS = 60
STARTS_PER_MINUTE = 60
# Per visitor address (as reported by the hosting proxy).
CLIENT_STARTS_PER_MINUTE = 6
CLIENT_LIVE_BOARDS = 10
# When full, only a board unused for this long can give way. Open boards refresh every 20 seconds.
EVICT_AFTER_IDLE = 120

SAMPLE_REQUESTS = [
    ("Jolene", "Dolly Parton", "Maura in Rostrevor", "For my sister, who's on the road today"),
    ("The Gambler", "Kenny Rogers", "Paddy", ""),
    ("Galway Girl", "Steve Earle", "Siobhan and the girls at work", "We're having a party tonight!"),
    ("Coat of Many Colors", "Dolly Parton", "", ""),
    ("Forty Shades of Green", "Johnny Cash", "Eamon in Warrenpoint", "Happy 80th birthday, Dad"),
    ("He Stopped Loving Her Today", "George Jones", "Bernie", "Our song"),
    ("Isle of Innisfree", "Bing Crosby", "Kathleen", "Thinking of home"),
    ("Islands in the Stream", "Kenny Rogers & Dolly Parton", "Gerry and Ann", "40 years married this week"),
]
NAMES = ["Una", "Sean", "Brid", "Declan", "Marie", "Frank", "Noeleen", "Tommy"]


class Sandboxes:
    """Visitor databases, with expiry and limits so memory stays bounded."""

    def __init__(self):
        self._items = {}
        self._starts = deque()
        self._lock = threading.Lock()

    def create(self, client=None):
        """Returns a new board's ID, or None if the demo can't take another right now."""
        now = time.monotonic()
        removed = []
        try:
            with self._lock:
                removed = self._expire(now)
                while self._starts and self._starts[0][0] < now - 60:
                    self._starts.popleft()
                if len(self._starts) >= STARTS_PER_MINUTE:
                    return None
                if client is not None and (
                        sum(1 for _, c in self._starts if c == client) >= CLIENT_STARTS_PER_MINUTE
                        or sum(1 for v in self._items.values() if v["client"] == client) >= CLIENT_LIVE_BOARDS):
                    return None
                if len(self._items) >= MAX_SANDBOXES:
                    # Full: a board nobody has used for a while gives way. Boards in use stay.
                    idle = [k for k, v in self._items.items() if v["seen"] < now - EVICT_AFTER_IDLE]
                    if not idle:
                        return None
                    removed.append(self._items.pop(min(idle, key=lambda k: self._items[k]["seen"])))
                self._starts.append((now, client))
                engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
                Base.metadata.create_all(engine)
                sandbox_id = secrets.token_urlsafe(18)
                self._items[sandbox_id] = {"engine": engine, "seen": now, "created": now, "client": client,
                                           "lock": threading.Lock()}
                return sandbox_id
        finally:
            # Closed outside the registry lock, so one busy board can't hold everyone up.
            for item in removed:
                self._dispose(item)

    def find(self, sandbox_id):
        now = time.monotonic()
        with self._lock:
            expired = self._expire(now)
            item = self._items.get(sandbox_id)
            if item:
                item["seen"] = now
        for old in expired:
            self._dispose(old)
        return item

    def remove(self, sandbox_id):
        with self._lock:
            item = self._items.pop(sandbox_id, None)
        if item:
            self._dispose(item)

    @staticmethod
    def _dispose(item):
        # Wait for any request still using the board to finish before closing its database.
        locked = item["lock"].acquire(timeout=5)
        try:
            item["engine"].dispose()
        finally:
            if locked:
                item["lock"].release()

    def count(self):
        return len(self._items)

    def _expire(self, now):
        # Removed under the registry lock, closed afterwards, so one busy board can't hold everyone up.
        keys = [k for k, v in self._items.items() if v["seen"] < now - IDLE_SECONDS or v["created"] < now - MAX_AGE_SECONDS]
        return [self._items.pop(k) for k in keys]


class SandboxSession(FlaskSession):
    """Sends every query to the current visitor's own database."""

    def get_bind(self, mapper=None, clause=None, bind=None, **kwargs):
        engine = g.get("sandbox_engine")
        if engine is not None:
            return engine
        # In the demo every query must belong to a visitor's board; never fall back to a shared database.
        if current_app.config.get("DEMO"):
            abort(403)
        return super().get_bind(mapper=mapper, clause=clause, bind=bind, **kwargs)


def seed(minutes_ago=(95, 61, 38, 22, 9, 3, 140, 180)):
    now = utc_now()
    for i, (song, artist, name, message) in enumerate(SAMPLE_REQUESTS):
        item = SongRequest(netlify_id=f"demo-{i}", song=song, artist=artist, name=name, message=message,
                           received_at=now - timedelta(minutes=minutes_ago[i]))
        if i >= 6:
            item.played_at = now - timedelta(minutes=minutes_ago[i] - 20)
        db.session.add(item)
    db.session.commit()


def create_demo_app():
    app = create_app({
        "DEMO": True,
        "SECRET_KEY": secrets.token_hex(32),
        "SQLALCHEMY_DATABASE_URI": "sqlite://",
        # No real sign-in and no webhook secret: password sign-in and the webhook can never succeed.
        "ADMIN_USERNAME": "",
        "ADMIN_PASSWORD_HASH": "",
        "NETLIFY_WEBHOOK_SECRET": "",
        "PERMANENT_SESSION_LIFETIME": timedelta(seconds=IDLE_SECONDS),
        "MAX_CONTENT_LENGTH": 16 * 1024,
        # X-Forwarded-For entries added by trusted proxies, counted from the right. 0 = per-visitor limits off.
        "TRUSTED_PROXY_HOPS": int(os.environ.get("TRUSTED_PROXY_HOPS", "0")),
    })
    db.session = db._make_scoped_session({"class_": SandboxSession})
    sandboxes = Sandboxes()
    app.extensions["coast_demo_sandboxes"] = sandboxes
    bp = Blueprint("demo", __name__)

    @app.before_request
    def use_sandbox():
        if request.path.startswith("/webhook"):
            abort(404)
        sandbox_id = session.get("sandbox")
        if not sandbox_id:
            if session.get("signed_in"):
                session.clear()
            return None
        item = sandboxes.find(sandbox_id)
        if item is None:
            session.clear()
            flash("Your demo ended after an hour without activity, so its requests were deleted. Start a new one below.")
            return redirect(url_for("auth.login"))
        item["lock"].acquire()
        g.sandbox_lock = item["lock"]
        g.sandbox_engine = item["engine"]
        return None

    @app.teardown_request
    def release_sandbox(_error):
        lock = g.pop("sandbox_lock", None)
        if lock is not None:
            lock.release()

    def client_address():
        # Only the entry the hosting proxy adds (TRUSTED_PROXY_HOPS from the right) is used, so nobody can
        # claim someone else's address. With no trusted hop set, per-visitor limits are off.
        hops = app.config.get("TRUSTED_PROXY_HOPS", 0)
        forwarded = [a.strip() for a in request.headers.get("X-Forwarded-For", "").split(",") if a.strip()]
        if hops < 1 or len(forwarded) < hops:
            return None
        return forwarded[-hops]

    @bp.post("/demo/start")
    def start():
        old = session.get("sandbox")
        if old:
            # Starting again replaces this visitor's board rather than adding another.
            g.pop("sandbox_lock").release()
            g.pop("sandbox_engine", None)
        session.clear()
        if old:
            sandboxes.remove(old)
        sandbox_id = sandboxes.create(client_address())
        if sandbox_id is None:
            flash("The demo is busy right now. Please try again in a minute.")
            return redirect(url_for("auth.login"))
        session.permanent = True
        session["signed_in"] = True
        session["sandbox"] = sandbox_id
        g.sandbox_engine = sandboxes.find(sandbox_id)["engine"]
        seed()
        return redirect(url_for("board.index"))

    @bp.post("/demo/add")
    def add():
        if not session.get("signed_in") or "sandbox_engine" not in g:
            return redirect(url_for("auth.login"))
        if db.session.scalar(select(func.count(SongRequest.id))) >= MAX_REQUESTS:
            flash(f"This demo holds up to {MAX_REQUESTS} requests. Use Start again for a fresh board.")
            return redirect(url_for("board.index"))
        song, artist, _, _ = random.choice(SAMPLE_REQUESTS)
        # The same cleaning the real webhook applies to a listener's form.
        db.session.add(SongRequest(netlify_id="demo-" + secrets.token_hex(8), song=clean(song, 200),
                                   artist=clean(artist, 200), name=clean(random.choice(NAMES), 100),
                                   message="", received_at=utc_now()))
        db.session.commit()
        return redirect(url_for("board.index"))

    @bp.post("/demo/end")
    def end():
        sandbox_id = session.get("sandbox")
        session.clear()
        if sandbox_id:
            sandboxes.remove(sandbox_id)
        return redirect(url_for("auth.login"))

    app.register_blueprint(bp)
    return app
