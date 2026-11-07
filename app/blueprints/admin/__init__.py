"""Expose the admin blueprint and register its view modules."""

from app.blueprints.admin.blueprint import admin_bp
from app.blueprints.admin import overview, routes
