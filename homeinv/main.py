from flask import Blueprint, render_template
from sqlalchemy import func, select, text

from .extensions import db, limiter
from .models import Aisle, Item, Location, Store
from .security import current_family_id, current_membership, family_required

bp = Blueprint("main", __name__)


@bp.route("/more")
@family_required
def more():
    """The set-up pages, kept out of the everyday Find / Places / List screens."""
    def count(model):
        return db.session.scalar(select(func.count()).select_from(model).where(model.family_id == current_family_id()))

    return render_template("more.html", membership=current_membership(),
                           counts={"items": count(Item), "stores": count(Store),
                                   "aisles": count(Aisle), "places": count(Location)})


@bp.route("/healthz")
@limiter.exempt
def healthz():
    db.session.execute(text("SELECT 1"))
    return {"status": "ok"}
