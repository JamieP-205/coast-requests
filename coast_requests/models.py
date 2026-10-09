"""The database: one table of song requests."""

from datetime import UTC, datetime

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


db = SQLAlchemy(model_class=Base)


def utc_now():
    # SQLite has no time zones, so every time is stored as UTC without one.
    return datetime.now(UTC).replace(tzinfo=None)


class SongRequest(db.Model):
    __tablename__ = "song_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Netlify's own ID for the form submission, so the same request is never
    # stored twice if Netlify sends it again.
    netlify_id: Mapped[str] = mapped_column(String(64), unique=True)
    song: Mapped[str] = mapped_column(String(200))
    artist: Mapped[str] = mapped_column(String(200))
    name: Mapped[str] = mapped_column(String(100), default="")
    message: Mapped[str] = mapped_column(String(1000), default="")
    received_at: Mapped[datetime] = mapped_column(default=utc_now)
    played_at: Mapped[datetime | None]

    @property
    def is_played(self):
        return self.played_at is not None
