from .conftest import PASSWORD, csrf_from


def test_the_board_needs_signing_in(client):
    response = client.get("/")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_the_right_password_signs_jim_in(client):
    page = client.get("/login")
    response = client.post("/login", data={"username": "jim", "password": PASSWORD, "csrf": csrf_from(page)})
    assert response.status_code == 302
    assert client.get("/").status_code == 200


def test_a_wrong_password_is_refused_with_a_message(client):
    page = client.get("/login")
    response = client.post("/login", data={"username": "jim", "password": "wrong", "csrf": csrf_from(page)})
    assert "That username or password isn&#39;t right." in response.get_data(as_text=True)
    assert client.get("/").status_code == 302


def test_a_wrong_username_is_refused(client):
    page = client.get("/login")
    client.post("/login", data={"username": "someone", "password": PASSWORD, "csrf": csrf_from(page)})
    assert client.get("/").status_code == 302


def test_forms_without_the_csrf_token_are_refused(client):
    client.get("/login")
    response = client.post("/login", data={"username": "jim", "password": PASSWORD})
    assert response.status_code == 400


def test_signing_out_ends_the_session(signed_in):
    page = signed_in.get("/")
    signed_in.post("/logout", data={"csrf": csrf_from(page)})
    assert signed_in.get("/").status_code == 302


def test_the_session_cookie_is_protected(app):
    assert app.config["SESSION_COOKIE_HTTPONLY"]
    assert app.config["SESSION_COOKIE_SAMESITE"] == "Lax"
