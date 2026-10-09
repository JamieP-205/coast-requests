"""Coast Requests: song requests from the Coast Internet Radio website, in one
list Jim can work through during his live shows."""

import os

from flask import Flask

from .config import Config
from .models import db


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)

    if not app.config["SECRET_KEY"]:
        raise RuntimeError("Set SECRET_KEY before starting the app. See README.md.")

    # The SQLite database lives in the instance folder, outside the code.
    os.makedirs(app.instance_path, exist_ok=True)
    db.init_app(app)

    from . import auth, board, cli, webhook

    app.register_blueprint(webhook.bp)
    app.register_blueprint(auth.bp)
    app.register_blueprint(board.bp)
    auth.protect_forms(app)
    cli.register(app)

    @app.after_request
    def security_headers(response):
        response.headers["Content-Security-Policy"] = (
            "default-src 'none'; script-src 'self'; connect-src 'self'; style-src 'self'; img-src 'self'; "
            "form-action 'self'; base-uri 'none'; frame-ancestors 'none'"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        return response

    with app.app_context():
        db.create_all()

    return app
