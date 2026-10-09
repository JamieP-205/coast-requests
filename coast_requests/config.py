"""Settings, read from environment variables so no secrets live in the code.
Locally they come from a .env file; on PythonAnywhere, from the WSGI file."""

import os
from datetime import timedelta


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///requests.db")

    # Jim's sign-in. The password is only ever stored as a hash, made with
    # `flask --app coast_requests hash-password`.
    ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "")
    ADMIN_PASSWORD_HASH = os.environ.get("ADMIN_PASSWORD_HASH", "")

    # The secret Netlify signs each form notification with.
    NETLIFY_WEBHOOK_SECRET = os.environ.get("NETLIFY_WEBHOOK_SECRET", "")

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("FLASK_DEBUG") != "1"
    PERMANENT_SESSION_LIFETIME = timedelta(days=30)
