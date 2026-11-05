"""The public demo: private fictional boards, no way in to real data."""

import re

import pytest

from coast_requests.demo import MAX_REQUESTS, create_demo_app


@pytest.fixture
def demo():
    app = create_demo_app()
    app.config.update(TESTING=True, SESSION_COOKIE_SECURE=False)
    return app


def csrf(page):
    return re.search(r'name="csrf" value="([^"]+)"', page.get_data(as_text=True)).group(1)


def start(app):
    client = app.test_client()
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


def test_an_expired_board_starts_again_cleanly(demo):
    client = start(demo)
    sandboxes = demo.extensions["coast_demo_sandboxes"]
    with client.session_transaction() as s:
        sandboxes.remove(s["sandbox"])
    response = client.get("/")
    assert response.status_code == 302
    assert "demo ended" in client.get("/login").get_data(as_text=True)


def test_a_full_demo_makes_room_instead_of_refusing(demo, monkeypatch):
    import coast_requests.demo as d
    monkeypatch.setattr(d, "MAX_SANDBOXES", 3)
    first = start(demo)
    for _ in range(3):
        start(demo)
    sandboxes = demo.extensions["coast_demo_sandboxes"]
    assert sandboxes.count() == 3
    # The oldest board was removed to make room, so its visitor starts again cleanly.
    assert first.get("/").status_code == 302
