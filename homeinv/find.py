"""Find: the home page. "Do we have milk?" — search everything, see how much and where."""

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from .extensions import db
from .forms import ActionForm
from .inventory import find_or_create_item
from .models import Item, Stock, clean_name, name_key
from .security import current_family_id, family_required
from .shopping import open_count, running_low

bp = Blueprint("find", __name__)

MAX_RESULTS = 40


def search(query):
    key = name_key(query)
    items = db.session.scalars(
        select(Item).where(Item.family_id == current_family_id(), Item.name_key.contains(key, autoescape=True))
        .order_by(Item.name_key).limit(MAX_RESULTS)
        .options(selectinload(Item.stock).selectinload(Stock.location), selectinload(Item.list_entry))).all()
    # Names that start with the search come first: "milk" → "Milk" before "Coconut Milk".
    items.sort(key=lambda i: (not i.name_key.startswith(key), i.name_key))
    results = []
    for item in items:
        stock = sorted(item.stock, key=lambda s: -s.quantity)
        results.append({
            "item": item,
            "stock": stock,
            "total": sum(s.quantity for s in stock),
            "on_list": item.list_entry is not None and not item.list_entry.in_cart,
        })
    return results


@bp.route("/")
def index():
    if not current_user.is_authenticated:
        return redirect(url_for("auth.login"))
    return _find_page()


@family_required
def _find_page():
    query = clean_name(request.args.get("q"))
    return render_template(
        "find/index.html",
        query=query,
        results=search(query) if query else None,
        low=running_low(limit=8) if not query else [],
        list_count=open_count(),
        action_form=ActionForm(),
    )


@bp.route("/find/new-item", methods=["POST"])
@family_required
def new_item():
    """'We have some' after a search found nothing: create the item, then say where it's kept."""
    if not ActionForm().validate_on_submit():
        return redirect(url_for(".index"))
    name = clean_name(request.form.get("name"))
    if not name or len(name) > 80:
        flash("Enter an item name (up to 80 characters).", "danger")
        return redirect(url_for(".index"))
    item, created = find_or_create_item(name)
    flash(f"Added {item.name}. Now say where you keep it." if created else f"{item.name} is already here.", "success")
    return redirect(url_for("catalog.item", item_id=item.id))
