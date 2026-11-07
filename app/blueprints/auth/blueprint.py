"""Define the auth blueprint independently of its view registrations."""

from flask import Blueprint


auth_bp = Blueprint("auth", __package__)
