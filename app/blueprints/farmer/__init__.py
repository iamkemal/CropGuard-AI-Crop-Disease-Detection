from flask import Blueprint


farmer_bp = Blueprint("farmer", __name__, url_prefix="/farmer")

from app.blueprints.farmer import routes
