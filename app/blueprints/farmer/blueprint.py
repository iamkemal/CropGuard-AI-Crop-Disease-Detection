"""Define the farmer blueprint independently of its view registrations."""

from flask import Blueprint


farmer_bp = Blueprint("farmer", __package__, url_prefix="/farmer")
