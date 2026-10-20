from flask import Blueprint, redirect, url_for
from flask_login import current_user
from sqlalchemy import text

from .extensions import db, limiter

bp = Blueprint("main", __name__)


@bp.route("/")
def index():
    if current_user.is_authenticated:
        # The inventory screens arrive in a later phase; the family page is home for now.
        return redirect(url_for("family.dashboard"))
    return redirect(url_for("auth.login"))


@bp.route("/healthz")
@limiter.exempt
def healthz():
    db.session.execute(text("SELECT 1"))
    return {"status": "ok"}
