"""Jim's sign-in, and protection for every form in the app.

There's one user, so the username and password hash come from the settings
rather than a users table.
"""

import hmac
import secrets
from functools import wraps

from flask import (
    Blueprint, abort, current_app, flash, redirect, render_template, request, session, url_for,
)
from werkzeug.security import check_password_hash

bp = Blueprint("auth", __name__)


def login_required(view):
    @wraps(view)
    def wrapped(**kwargs):
        if not session.get("signed_in"):
            return redirect(url_for("auth.login"))
        return view(**kwargs)
    return wrapped


def csrf_token():
    """A random token kept in the session and put in every form, so another
    website can't make Jim's browser submit a form here."""
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(32)
    return session["csrf"]


def protect_forms(app):
    app.jinja_env.globals["csrf_token"] = csrf_token

    @app.before_request
    def check_csrf():
        # The webhook is signed by Netlify instead.
        if request.method != "POST" or request.blueprint == "webhook":
            return
        sent = request.form.get("csrf", "")
        if not sent or not hmac.compare_digest(sent, session.get("csrf", "")):
            abort(400, "This page was open too long. Please go back and try again.")


def credentials_match(username, password):
    config = current_app.config
    right_name = hmac.compare_digest(username.encode(), config["ADMIN_USERNAME"].encode())
    # Check the password even if the name is wrong, so both take the same time.
    stored = config["ADMIN_PASSWORD_HASH"]
    right_password = bool(stored) and check_password_hash(stored, password)
    return right_name and right_password


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if credentials_match(username, password):
            session.clear()
            session.permanent = True
            session["signed_in"] = True
            return redirect(url_for("board.index"))
        flash("That username or password isn't right.")
    return render_template("login.html")


@bp.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))
