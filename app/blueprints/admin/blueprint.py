"""Define the admin blueprint independently of its view registrations."""

from flask import Blueprint


admin_bp = Blueprint("admin", __package__, url_prefix="/admin")
