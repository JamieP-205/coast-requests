"""Commands run with `flask --app coast_requests <command>`."""

from datetime import timedelta

import click
from werkzeug.security import generate_password_hash

from .models import SongRequest, db, utc_now

SAMPLES = [
    ("Carlingford Bay", "Joe McShane", "Mary", "For my mum, 80 today!", 35),
    ("Streets Of Bakersfield", "Dwight Yoakam", "Pat from Warrenpoint", "", 22),
    ("The Old Rugged Cross", "Philomena Begley", "", "Played at our wedding", 9),
    ("I'll Settle For You", "Nathan Carter", "Sean", "", 3),
]


def register(app):
    @app.cli.command("hash-password")
    @click.password_option(prompt="Jim's new password")
    def hash_password(password):
        """Print the hash to put in ADMIN_PASSWORD_HASH."""
        if len(password) < 12:
            raise click.BadParameter("Please use at least 12 characters.")
        click.echo(generate_password_hash(password))

    @app.cli.command("add-sample-requests")
    def add_sample_requests():
        """Fill a local database with example requests, for trying the board."""
        if not app.debug:
            raise click.ClickException("Only for your own computer: set FLASK_DEBUG=1 first.")
        for number, (song, artist, name, message, minutes_ago) in enumerate(SAMPLES):
            db.session.add(SongRequest(
                netlify_id=f"sample-{utc_now().timestamp()}-{number}",
                song=song, artist=artist, name=name, message=message,
                received_at=utc_now() - timedelta(minutes=minutes_ago),
            ))
        db.session.commit()
        click.echo(f"Added {len(SAMPLES)} sample requests.")
