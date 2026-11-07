"""Expose the auth blueprint and register its view modules."""

from app.blueprints.auth.blueprint import auth_bp
from app.blueprints.auth import routes
