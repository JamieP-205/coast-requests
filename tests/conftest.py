import hashlib
import json
import re

import jwt
import pytest
from werkzeug.security import generate_password_hash

from coast_requests import create_app

PASSWORD = "a long test password"
WEBHOOK_SECRET = "test-webhook-secret-at-least-32-bytes"


@pytest.fixture
def app():
    return create_app({
        "TESTING": True,
        "SECRET_KEY": "test",
        "SQLALCHEMY_DATABASE_URI": "sqlite://",
        "ADMIN_USERNAME": "jim",
        "ADMIN_PASSWORD_HASH": generate_password_hash(PASSWORD),
        "NETLIFY_WEBHOOK_SECRET": WEBHOOK_SECRET,
        "SESSION_COOKIE_SECURE": False,
    })


@pytest.fixture
def client(app):
    return app.test_client()


def csrf_from(response):
    return re.search(r'name="csrf" value="([^"]+)"', response.get_data(as_text=True)).group(1)


@pytest.fixture
def signed_in(client):
    page = client.get("/login")
    client.post("/login", data={"username": "jim", "password": PASSWORD, "csrf": csrf_from(page)})
    return client


def send_request(client, song="Carlingford Bay", artist="Joe McShane", submission_id="abc123",
                 form_name="song-request", secret=WEBHOOK_SECRET, **extra):
    """Sends a form submission the way Netlify's outgoing webhook does."""
    body = json.dumps({
        "id": submission_id,
        "form_name": form_name,
        "created_at": "2026-10-09T18:42:00.000Z",
        "data": {"song": song, "artist": artist, **extra},
    }).encode()
    token = jwt.encode({"iss": "netlify", "sha256": hashlib.sha256(body).hexdigest()}, secret, algorithm="HS256")
    return client.post("/webhook/netlify", data=body, content_type="application/json",
                       headers={"X-Webhook-Signature": token})
