"""The public demo: private fictional boards, no way in to real data."""

import re

import pytest

from coast_requests.demo import MAX_REQUESTS, create_demo_app


@pytest.fixture
def demo():
    app = create_demo_app()
    app.config.update(TESTING=True, SESSION_COOKIE_SECURE=False, TRUSTED_PROXY_HOPS=1)
    return app


def csrf(page):
    return re.search(r'name="csrf" value="([^"]+)"', page.get_data(as_text=True)).group(1)


VISITOR = [0]


def start(app, address=None):
    VISITOR[0] += 1
    client = app.test_client()
    client.environ_base["HTTP_X_FORWARDED_FOR"] = address or f"10.0.0.{VISITOR[0] % 250}"
    page = client.get("/login")
    assert "Open the demo board" in page.get_data(as_text=True)
    response = client.post("/demo/start", data={"csrf": csrf(page)})
    assert response.status_code == 302
    return client


def test_each_visitor_gets_a_private_board(demo):
    alice, bob = start(demo), start(demo)
    board = alice.get("/")
    assert "Jolene" in board.get_data(as_text=True)
    first_id = re.search(r"/requests/(\d+)/played", board.get_data(as_text=True)).group(1)
    alice.post(f"/requests/{first_id}/played", data={"csrf": csrf(board)})
    waiting = lambda c: int(re.search(r'class="count">(\d+)<', c.get("/").get_data(as_text=True)).group(1))
    assert waiting(alice) == 5
    assert waiting(bob) == 6


def test_no_real_sign_in_or_webhook(demo):
    client = demo.test_client()
    page = client.get("/login")
    client.post("/login", data={"username": "", "password": "", "csrf": csrf(page)})
    assert client.get("/").status_code == 302
    assert client.post("/webhook/netlify", data=b"{}").status_code == 404


def test_adding_requests_is_capped(demo):
    client = start(demo)
    for _ in range(MAX_REQUESTS):
        client.post("/demo/add", data={"csrf": csrf(client.get("/"))})
    text = client.get("/").get_data(as_text=True)
    assert f"holds up to {MAX_REQUESTS} requests" in text


def test_forms_still_need_csrf(demo):
    client = start(demo)
    assert client.post("/demo/add").status_code == 400
    assert client.post("/demo/request", data={"song": "Wildflowers"}).status_code == 400


def test_listener_request_arrives_in_own_board_and_can_be_played(demo):
    alice, bob = start(demo), start(demo)
    form = alice.get("/demo/request")
    response = alice.post("/demo/request", data={
        "csrf": csrf(form), "song": "  Wildflowers  ", "artist": "Tom Petty",
        "name": "Demo listener", "message": "For everyone finishing work",
    })
    assert response.status_code == 302
    assert "#request-" in response.location
    request_id = response.location.split("#request-")[1]
    board = alice.get("/")
    text = board.get_data(as_text=True)
    assert "Wildflowers" in text and "For everyone finishing work" in text
    assert text.index("Forty Shades of Green") < text.index('class="song">Wildflowers')
    assert "Wildflowers" not in bob.get("/").get_data(as_text=True)
    played = alice.post(f"/requests/{request_id}/played", data={"csrf": csrf(board)}, follow_redirects=True)
    text = played.get_data(as_text=True)
    assert "Wildflowers" not in text.split('id="played-heading"')[0]
    assert "Wildflowers" in text.split('id="played-heading"')[1]


def test_listener_request_requires_a_title_and_keeps_other_fields(demo):
    client = start(demo)
    response = client.post("/demo/request", data={
        "csrf": csrf(client.get("/demo/request")), "song": " \n ", "artist": "Tom Petty",
    })
    assert response.status_code == 400
    text = response.get_data(as_text=True)
    assert "Enter a song title" in text and 'value="Tom Petty"' in text
    assert 'class="count">6<' in client.get("/").get_data(as_text=True)


def test_listener_request_escapes_input_and_limits_length(demo):
    client = start(demo)
    response = client.post("/demo/request", data={
        "csrf": csrf(client.get("/demo/request")), "song": "x" * 210,
        "name": '<script>alert("x")</script>', "message": "m" * 510,
    }, follow_redirects=True)
    text = response.get_data(as_text=True)
    assert "x" * 200 in text and "x" * 201 not in text
    assert "m" * 500 in text and "m" * 501 not in text
    assert '<script>alert("x")</script>' not in text
    assert "&lt;script&gt;" in text


def test_listener_form_obeys_board_cap(demo, monkeypatch):
    import coast_requests.demo as d
    client = start(demo)
    monkeypatch.setattr(d, "MAX_REQUESTS", 8)
    response = client.post("/demo/request", data={
        "csrf": csrf(client.get("/demo/request")), "song": "No room",
    })
    assert response.status_code == 400
    assert "holds up to 8 requests" in response.get_data(as_text=True)
    assert "No room" not in client.get("/").get_data(as_text=True)


def test_listener_demo_is_unavailable_without_demo_session(demo, client):
    assert demo.test_client().get("/demo/request").status_code == 302
    assert client.get("/demo/request").status_code == 404


def test_an_expired_board_starts_again_cleanly(demo):
    client = start(demo)
    sandboxes = demo.extensions["coast_demo_sandboxes"]
    with client.session_transaction() as s:
        sandboxes.remove(s["sandbox"])
    response = client.get("/")
    assert response.status_code == 302
    assert "demo ended" in client.get("/login").get_data(as_text=True)


def test_a_full_demo_only_replaces_idle_boards(demo, monkeypatch):
    import coast_requests.demo as d
    monkeypatch.setattr(d, "MAX_SANDBOXES", 2)
    first, second = start(demo), start(demo)
    sandboxes = demo.extensions["coast_demo_sandboxes"]
    newcomer = demo.test_client()
    page = newcomer.get("/login")
    # Both boards are in use, so a newcomer is told to wait rather than pushing someone out.
    assert "busy" in newcomer.post("/demo/start", data={"csrf": csrf(page)}, follow_redirects=True).get_data(as_text=True)
    monkeypatch.setattr(d, "EVICT_AFTER_IDLE", -1)
    third = start(demo)
    assert sandboxes.count() == 2
    assert first.get("/").status_code == 302


def test_one_address_cant_take_every_board(demo, monkeypatch):
    import coast_requests.demo as d
    monkeypatch.setattr(d, "CLIENT_LIVE_BOARDS", 2)
    start(demo, "10.7.0.1"), start(demo, "10.7.0.1")
    client = demo.test_client()
    client.environ_base["HTTP_X_FORWARDED_FOR"] = "10.0.0.9, 10.7.0.1"
    page = client.get("/login")
    assert "busy" in client.post("/demo/start", data={"csrf": csrf(page)}, follow_redirects=True).get_data(as_text=True)


def test_a_signed_in_session_without_a_board_is_signed_out(demo):
    client = start(demo)
    with client.session_transaction() as s:
        s.pop("sandbox")
    assert client.get("/").status_code == 302
    with client.session_transaction() as s:
        assert not s.get("signed_in")


def test_a_forged_earlier_address_cant_use_up_someone_elses_limit(demo, monkeypatch):
    import coast_requests.demo as d
    monkeypatch.setattr(d, "CLIENT_LIVE_BOARDS", 2)
    start(demo, "10.5.0.1, 10.5.0.50")
    start(demo, "10.5.0.1, 10.5.0.51")
    start(demo, "10.5.0.1")
