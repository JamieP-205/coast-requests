"""Receives song requests from the Coast website.

The request form on coastinternetradio.com is handled by Netlify Forms. Netlify
emails each submission to the station and also sends it here as an outgoing
webhook, signed so nobody else can add requests.
"""

import hashlib
import hmac
from datetime import UTC, datetime

import jwt
from flask import Blueprint, abort, current_app, request
from sqlalchemy import select

from .models import SongRequest, db, utc_now

bp = Blueprint("webhook", __name__)

REQUEST_FORM = "song-request"


def signature_is_valid(body, token, secret):
    """Netlify signs a token holding a SHA-256 hash of the exact body it sent.
    The token must be signed with our secret and the hash must match."""
    if not token or not secret:
        return False
    try:
        claims = jwt.decode(token, secret, algorithms=["HS256"])
    except jwt.InvalidTokenError:
        return False
    expected = hashlib.sha256(body).hexdigest()
    return hmac.compare_digest(str(claims.get("sha256", "")), expected)


def clean(value, limit):
    return " ".join(str(value or "").split())[:limit]


def received_time(submission):
    """When the listener sent the request, in UTC like every other time here."""
    try:
        sent = datetime.fromisoformat(submission["created_at"])
    except (KeyError, TypeError, ValueError):
        return utc_now()
    if sent.tzinfo is not None:
        sent = sent.astimezone(UTC).replace(tzinfo=None)
    return sent


@bp.post("/webhook/netlify")
def netlify_form():
    body = request.get_data()
    token = request.headers.get("X-Webhook-Signature", "")
    if not signature_is_valid(body, token, current_app.config["NETLIFY_WEBHOOK_SECRET"]):
        abort(401)

    submission = request.get_json(silent=True) or {}
    # The feedback form goes to the same site, but isn't a request.
    if submission.get("form_name") != REQUEST_FORM:
        return "", 204

    data = submission.get("data") or {}
    netlify_id = clean(submission.get("id"), 64)
    song = clean(data.get("song"), 200)
    artist = clean(data.get("artist"), 200)
    if not netlify_id or not song:
        abort(400)

    already_stored = db.session.scalar(select(SongRequest).filter_by(netlify_id=netlify_id))
    if not already_stored:
        db.session.add(SongRequest(
            netlify_id=netlify_id,
            song=song,
            artist=artist,
            name=clean(data.get("name"), 100),
            message=clean(data.get("message"), 1000),
            received_at=received_time(submission),
        ))
        db.session.commit()
    return "", 204
