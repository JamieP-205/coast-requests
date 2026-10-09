from datetime import UTC, datetime

from sqlalchemy import select

from coast_requests.board import uk_when
from coast_requests.models import SongRequest, db

from .conftest import csrf_from, send_request


def request_id(app, song):
    with app.app_context():
        return db.session.scalar(select(SongRequest.id).filter_by(song=song))


def test_waiting_requests_are_listed_oldest_first(signed_in):
    send_request(signed_in, song="First song", submission_id="1")
    send_request(signed_in, song="Second song", submission_id="2")
    page = signed_in.get("/").get_data(as_text=True)
    assert page.index("First song") < page.index("Second song")
    assert '<span class="count">2</span>' in page


def test_marking_a_request_played_moves_it_down(app, signed_in):
    send_request(signed_in, song="Carlingford Bay")
    page = signed_in.get("/")
    signed_in.post(f"/requests/{request_id(app, 'Carlingford Bay')}/played", data={"csrf": csrf_from(page)})
    page = signed_in.get("/").get_data(as_text=True)
    assert "No requests waiting" in page
    assert "Played recently" in page


def test_a_played_request_can_go_back_on_the_list(app, signed_in):
    send_request(signed_in, song="Carlingford Bay")
    song_id = request_id(app, "Carlingford Bay")
    csrf = csrf_from(signed_in.get("/"))
    signed_in.post(f"/requests/{song_id}/played", data={"csrf": csrf})
    signed_in.post(f"/requests/{song_id}/not-played", data={"csrf": csrf})
    assert '<span class="count">1</span>' in signed_in.get("/").get_data(as_text=True)


def test_a_joke_request_can_be_removed(app, signed_in):
    send_request(signed_in, song="Never Gonna Give You Up")
    csrf = csrf_from(signed_in.get("/"))
    signed_in.post(f"/requests/{request_id(app, 'Never Gonna Give You Up')}/remove", data={"csrf": csrf})
    assert request_id(app, "Never Gonna Give You Up") is None


def test_requests_are_shown_as_text_not_html(signed_in):
    send_request(signed_in, song="<script>alert(1)</script>")
    page = signed_in.get("/").get_data(as_text=True)
    assert "<script>alert(1)</script>" not in page
    assert "&lt;script&gt;" in page


def test_changing_a_request_needs_signing_in(app, client):
    send_request(client, song="Carlingford Bay")
    response = client.post(f"/requests/{request_id(app, 'Carlingford Bay')}/played")
    assert response.status_code in (302, 400)
    with app.app_context():
        assert db.session.scalar(select(SongRequest)).played_at is None


def test_the_page_can_tell_when_new_requests_arrive(signed_in):
    before = signed_in.get("/updates").get_json()["version"]
    send_request(signed_in, song="Carlingford Bay")
    after = signed_in.get("/updates").get_json()["version"]
    assert before != after


def test_times_are_shown_in_uk_time():
    now = datetime(2026, 10, 9, 20, 0, tzinfo=UTC)
    # 18:42 UTC is 7:42pm in the UK during British Summer Time.
    assert uk_when(datetime(2026, 10, 9, 18, 42), now) == "at 7:42pm"
    assert uk_when(datetime(2026, 10, 8, 18, 42), now) == "yesterday at 7:42pm"
    assert uk_when(datetime(2026, 10, 5, 9, 5), now) == "on Mon 5 Oct at 10:05am"
