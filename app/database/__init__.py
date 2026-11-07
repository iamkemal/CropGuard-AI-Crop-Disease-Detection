"""Manage SQLite connections for the lifetime of each Flask request."""

import sqlite3

from flask import current_app, g


def get_db() -> sqlite3.Connection:
    """Reuse the request connection with row access and foreign-key checks enabled."""
    if "database" not in g:
        connection = sqlite3.connect(current_app.config["DATABASE"])
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        g.database = connection
    return g.database


def close_db(_error: BaseException | None = None) -> None:
    """Close and remove the database connection at the end of the app context."""
    connection = g.pop("database", None)
    if connection is not None:
        connection.close()


def init_app(app) -> None:
    """Register database cleanup with the Flask application."""
    app.teardown_appcontext(close_db)
