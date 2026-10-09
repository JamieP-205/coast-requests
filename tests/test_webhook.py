import hashlib
from datetime import datetime

import jwt
from sqlalchemy import select

from coast_requests.models import SongRequest, db
from coast_requests.webhook import signature_is_valid

from .conftest import WEBHOOK_SECRET, send_request


def stored(app):
    with app.app_context():
        return db.session.scalars(select(SongRequest)).all()


def test_a_signed_request_is_stored(app, client):
    response = send_request(client, name="Mary", message="For my mum's birthday")
    assert response.status_code == 204
    [song_request] = stored(app)
    assert song_request.song == "Carlingford Bay"
    assert song_request.artist == "Joe McShane"
    assert song_request.name == "Mary"
    assert song_request.message == "For my mum's birthday"
    assert song_request.received_at == datetime(2026, 10, 9, 18, 42)
    assert not song_request.is_played


def test_the_same_submission_is_only_stored_once(app, client):
    send_request(client)
    send_request(client)
    assert len(stored(app)) == 1


def test_a_request_signed_with_another_secret_is_refused(app, client):
    response = send_request(client, secret="a-different-secret-at-least-32-bytes")
    assert response.status_code == 401
    assert stored(app) == []


def test_an_unsigned_request_is_refused(app, client):
    response = client.post("/webhook/netlify", json={"id": "1", "form_name": "song-request"})
    assert response.status_code == 401


def test_a_changed_body_fails_the_signature_check():
    body = b'{"song": "Carlingford Bay"}'
    token = jwt.encode({"sha256": hashlib.sha256(body).hexdigest()}, WEBHOOK_SECRET, algorithm="HS256")
    assert signature_is_valid(body, token, WEBHOOK_SECRET)
    assert not signature_is_valid(b'{"song": "Something else"}', token, WEBHOOK_SECRET)


def test_feedback_from_the_other_form_is_ignored(app, client):
    response = send_request(client, form_name="feedback")
    assert response.status_code == 204
    assert stored(app) == []


def test_a_request_with_no_song_is_refused(app, client):
    response = send_request(client, song="   ")
    assert response.status_code == 400
    assert stored(app) == []


def test_extra_spaces_and_very_long_text_are_tidied(app, client):
    send_request(client, song="  Carlingford   Bay  ", message="x" * 5000)
    [song_request] = stored(app)
    assert song_request.song == "Carlingford Bay"
    assert len(song_request.message) == 1000
