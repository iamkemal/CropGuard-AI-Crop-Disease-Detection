"""Build the Flask application and register its views and management commands."""

import secrets
import sqlite3
from pathlib import Path
from re import fullmatch

import click
from flask import Flask, render_template
from flask_wtf.csrf import CSRFProtect
from werkzeug.security import generate_password_hash

from app.blueprints.admin import admin_bp
from app.blueprints.auth import auth_bp
from app.blueprints.farmer import farmer_bp
from app.database import get_db, init_app as init_database_app
from app.database.seed import initialize_database


csrf = CSRFProtect()


def create_app(test_config: dict | None = None) -> Flask:
    """Configure storage, extensions, blueprints, and CLI commands for one app."""
    project_root = Path(__file__).resolve().parent.parent
    instance_path = project_root / "instance"
    app = Flask(
        __name__,
        instance_path=str(instance_path),
        instance_relative_config=True,
    )
    app.config.from_object("config.Config")
    if test_config:
        app.config.update(test_config)

    if not app.config.get("SECRET_KEY"):
        if app.config.get("APP_ENV") == "production":
            raise RuntimeError("SECRET_KEY must be configured in production.")
        app.config["SECRET_KEY"] = secrets.token_hex(32)

    database_path = Path(app.config["DATABASE"])
    database_path.parent.mkdir(parents=True, exist_ok=True)
    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)

    initialize_database(database_path)
    init_database_app(app)
    csrf.init_app(app)

    app.register_blueprint(auth_bp)
    app.register_blueprint(farmer_bp)
    app.register_blueprint(admin_bp)

    @app.get("/")
    def home():
        return render_template("home.html")

    @app.get("/about")
    def about():
        return render_template("about.html")

    @app.errorhandler(403)
    def forbidden(_error):
        return render_template("errors/403.html"), 403

    @app.cli.command("init-db")
    def init_db_command():
        initialize_database(app.config["DATABASE"])
        click.echo("Database schema and knowledge base are ready.")

    @app.cli.command("create-admin")
    def create_admin_command():
        username = click.prompt("Admin username").strip()
        email = click.prompt("Admin email").strip().lower()
        password = click.prompt(
            "Admin password",
            hide_input=True,
            confirmation_prompt=True,
        )
        if len(username) < 2 or len(username) > 80:
            raise click.ClickException("Username must contain 2 to 80 characters.")
        if not fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            raise click.ClickException("Enter a valid email address.")
        if len(password) < 12:
            raise click.ClickException("Admin passwords must contain at least 12 characters.")

        connection = get_db()
        existing = connection.execute(
            "SELECT id FROM users WHERE email = ? COLLATE NOCASE",
            (email,),
        ).fetchone()
        if existing:
            raise click.ClickException("An account already uses that email address.")
        try:
            connection.execute(
                """
                INSERT INTO users (username, email, password_hash, role)
                VALUES (?, ?, ?, 'admin')
                """,
                (username, email, generate_password_hash(password)),
            )
            connection.commit()
        except sqlite3.IntegrityError as error:
            connection.rollback()
            raise click.ClickException("The administrator could not be created.") from error
        click.echo(f"Administrator account created for {email}.")

    return app
