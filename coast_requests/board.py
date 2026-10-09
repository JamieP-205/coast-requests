"""The request board: what's waiting, oldest first, and what Jim has played."""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from flask import Blueprint, jsonify, redirect, render_template, url_for
from sqlalchemy import func, select

from .auth import login_required
from .models import SongRequest, db, utc_now

bp = Blueprint("board", __name__)

UK = ZoneInfo("Europe/London")
RECENTLY_PLAYED = 10


@bp.app_template_filter("uk_when")
def uk_when(moment, now=None):
    """Times are stored in UTC and shown in UK time: "at 7:42pm" for today,
    "yesterday at 7:42pm", or "on Mon 6 Oct at 7:42pm" for anything older."""
    local = moment.replace(tzinfo=UTC).astimezone(UK)
    today = (now or datetime.now(UTC)).astimezone(UK).date()
    time = local.strftime("%I:%M%p").lstrip("0").lower()
    days_ago = (today - local.date()).days
    if days_ago == 0:
        return f"at {time}"
    if days_ago == 1:
        return f"yesterday at {time}"
    return f"on {local.strftime('%a')} {local.day} {local.strftime('%b')} at {time}"


def board_version():
    """Changes whenever a request arrives, is played or is removed, so the
    page can tell when it's out of date."""
    newest = db.session.scalar(select(func.max(SongRequest.id))) or 0
    waiting = db.session.scalar(select(func.count(SongRequest.id)).where(SongRequest.played_at.is_(None)))
    played = db.session.scalar(select(func.count(SongRequest.id)).where(SongRequest.played_at.is_not(None)))
    return f"{newest}-{waiting}-{played}"


@bp.get("/")
@login_required
def index():
    waiting = db.session.scalars(
        select(SongRequest)
        .where(SongRequest.played_at.is_(None))
        .order_by(SongRequest.received_at)
    ).all()
    played = db.session.scalars(
        select(SongRequest)
        .where(SongRequest.played_at.is_not(None))
        .order_by(SongRequest.played_at.desc())
        .limit(RECENTLY_PLAYED)
    ).all()
    return render_template("board.html", waiting=waiting, played=played, version=board_version())


@bp.get("/updates")
@login_required
def updates():
    return jsonify(version=board_version())


@bp.post("/requests/<int:request_id>/played")
@login_required
def mark_played(request_id):
    song_request = db.get_or_404(SongRequest, request_id)
    song_request.played_at = utc_now()
    db.session.commit()
    return redirect(url_for("board.index"))


@bp.post("/requests/<int:request_id>/not-played")
@login_required
def mark_not_played(request_id):
    song_request = db.get_or_404(SongRequest, request_id)
    song_request.played_at = None
    db.session.commit()
    return redirect(url_for("board.index"))


@bp.post("/requests/<int:request_id>/remove")
@login_required
def remove(request_id):
    """For joke or spam requests that should never be played."""
    db.session.delete(db.get_or_404(SongRequest, request_id))
    db.session.commit()
    return redirect(url_for("board.index"))
