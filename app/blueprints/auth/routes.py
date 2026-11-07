"""Account registration, authentication, and role-based access controls."""

import re
import sqlite3
from functools import wraps
from typing import Callable, TypeVar

from flask import (
    abort,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

from app.blueprints.auth.blueprint import auth_bp
from app.database import get_db


ViewFunction = TypeVar("ViewFunction", bound=Callable)
EMAIL_PATTERN = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")


@auth_bp.before_app_request
def load_logged_in_user() -> None:
    """Load the active session user or clear an invalid account session."""
    user_id = session.get("user_id")
    if not isinstance(user_id, int):
        g.user = None
        return

    user = get_db().execute(
        """
        SELECT id, username, email, role, is_active
        FROM users
        WHERE id = ?
        """,
        (user_id,),
    ).fetchone()
    if user is None or not user["is_active"]:
        session.clear()
        g.user = None
        return
    g.user = user


def login_required(view: ViewFunction) -> ViewFunction:
    """Wrap a view so anonymous visitors must log in before accessing it."""
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if g.get("user") is None:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)

    return wrapped_view  # type: ignore[return-value]


def roles_required(*roles: str):
    """Wrap a view with authentication and an allowed-role check."""
    def decorator(view: ViewFunction) -> ViewFunction:
        @wraps(view)
        def wrapped_view(*args, **kwargs):
            user = g.get("user")
            if user is None:
                flash("Please log in to continue.", "warning")
                return redirect(url_for("auth.login"))
            if user["role"] not in roles:
                abort(403)
            return view(*args, **kwargs)

        return wrapped_view  # type: ignore[return-value]

    return decorator


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    """Validate registration data and create a farmer account with a hashed password."""
    if request.method == "GET":
        return render_template("auth/register.html")

    username = request.form.get("username", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    confirmation = request.form.get("confirm_password", "")
    errors = []

    if not 2 <= len(username) <= 80:
        errors.append("Username must contain 2 to 80 characters.")
    if not EMAIL_PATTERN.fullmatch(email):
        errors.append("Enter a valid email address.")
    if len(password) < 8:
        errors.append("Password must contain at least 8 characters.")
    if password != confirmation:
        errors.append("The passwords do not match.")

    connection = get_db()
    existing_user = connection.execute(
        "SELECT id FROM users WHERE email = ? COLLATE NOCASE",
        (email,),
    ).fetchone()
    if existing_user:
        errors.append("An account already uses that email address.")

    if errors:
        for error in errors:
            flash(error, "danger")
        return render_template("auth/register.html"), 400

    try:
        connection.execute(
            """
            INSERT INTO users (username, email, password_hash, role)
            VALUES (?, ?, ?, 'farmer')
            """,
            (username, email, generate_password_hash(password)),
        )
        connection.commit()
    except sqlite3.IntegrityError:
        connection.rollback()
        flash("An account already uses that email address.", "danger")
        return render_template("auth/register.html"), 400

    flash("Your farmer account was created. You can now log in.", "success")
    return redirect(url_for("auth.login"))


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Authenticate an active user and establish a fresh role-based session."""
    if request.method == "GET":
        return render_template("auth/login.html")

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    user = get_db().execute(
        """
        SELECT id, password_hash, role, is_active
        FROM users
        WHERE email = ? COLLATE NOCASE
        """,
        (email,),
    ).fetchone()

    if (
        user is None
        or not user["is_active"]
        or not check_password_hash(user["password_hash"], password)
    ):
        flash("Invalid email or password.", "danger")
        return render_template("auth/login.html"), 401

    session.clear()
    session["user_id"] = int(user["id"])
    session.permanent = True
    destination = (
        "admin.dashboard" if user["role"] == "admin" else "farmer.dashboard"
    )
    return redirect(url_for(destination))


@auth_bp.post("/logout")
@login_required
def logout():
    """Clear the current session and return the visitor to the login page."""
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("home"))
