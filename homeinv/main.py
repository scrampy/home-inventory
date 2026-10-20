from flask import Blueprint, redirect, url_for
from flask_login import current_user
from sqlalchemy import text

from .extensions import db, limiter

bp = Blueprint("main", __name__)


@bp.route("/")
def index():
    if current_user.is_authenticated:
        # Inventory becomes the home page in phase 3; items are home for now.
        return redirect(url_for("catalog.items"))
    return redirect(url_for("auth.login"))


@bp.route("/healthz")
@limiter.exempt
def healthz():
    db.session.execute(text("SELECT 1"))
    return {"status": "ok"}
