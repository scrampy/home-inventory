"""Inventory: how much of each item is kept where.

Changes made with the +/- buttons and the quantity box update the row in place
when JavaScript is available (static/app.js asks for just the row's HTML);
without it, the forms post normally and the page reloads.
"""

from flask import Blueprint, abort, flash, make_response, redirect, render_template, request, url_for
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from .catalog import add_named
from .extensions import db
from .forms import ActionForm
from .models import Item, Location, Stock, clean_name, format_quantity
from .security import (current_family_id, family_required, family_rows, get_for_family_or_404,
                       name_in_use, safe_next_url)

bp = Blueprint("inventory", __name__)

MAX_QUANTITY = 100_000


def _require_post_form():
    if not ActionForm().validate_on_submit():
        abort(400)


def _wants_row():
    return request.headers.get("X-Requested-With") == "fetch"


def _back(default):
    return redirect(safe_next_url(request.form.get("next") or request.args.get("next"), default))


def _render_row(stock, view, error=None, status=200):
    response = make_response(render_template("inventory/_row.html", stock=stock, view=view, error=error), status)
    response.headers["X-Row"] = "1"  # tells static/app.js this is a row it can swap in
    return response


def _row_response(stock, view):
    """After a change: the updated row for in-place updates, or a redirect back."""
    if _wants_row():
        return _render_row(stock, view)
    return _back(url_for(".index", location=stock.location_id))


@bp.app_template_filter("qty")
def qty_filter(value):
    return format_quantity(value)


def get_or_create_stock(item, location):
    stock = db.session.scalar(select(Stock).filter_by(item_id=item.id, location_id=location.id))
    if stock is None:
        stock = Stock(family_id=item.family_id, item=item, location=location, quantity=0)
        db.session.add(stock)
    return stock


@bp.route("/inventory")
@family_required
def index():
    locations = family_rows(Location)
    selected = None
    location_param = request.args.get("location", "")
    if location_param.isdigit():
        selected = get_for_family_or_404(Location, int(location_param))

    query = (select(Stock).where(Stock.family_id == current_family_id())
             .join(Stock.item).order_by(Item.name_key)
             .options(selectinload(Stock.item), selectinload(Stock.location)))
    if selected:
        rows = db.session.scalars(query.where(Stock.location_id == selected.id)).all()
        grouped = None
    else:
        rows = db.session.scalars(query).all()
        # "All locations": one line per item with its total and where it is.
        grouped = {}
        for stock in rows:
            grouped.setdefault(stock.item, []).append(stock)

    counts = {}
    for stock in db.session.scalars(select(Stock).where(Stock.family_id == current_family_id())):
        counts[stock.location_id] = counts.get(stock.location_id, 0) + 1

    item_names = [i.name for i in family_rows(Item)]
    return render_template("inventory/index.html", locations=locations, selected=selected,
                           rows=rows, grouped=grouped, counts=counts, item_names=item_names)


@bp.route("/inventory/add", methods=["POST"])
@family_required
def add():
    """Add an item to a location: +1 if it's already there, creating the item if it's new."""
    _require_post_form()
    location_id = request.form.get("location_id", "")
    name = clean_name(request.form.get("name"))
    if not location_id.isdigit():
        flash("Choose a location.", "danger")
        return _back(url_for(".index"))
    location = get_for_family_or_404(Location, int(location_id))
    if not name:
        flash("Enter an item name.", "danger")
        return _back(url_for(".index", location=location.id))
    if len(name) > 80:
        flash("Item names can be up to 80 characters.", "danger")
        return _back(url_for(".index", location=location.id))

    item = name_in_use(Item, name)
    created = False
    if item is None:
        item = add_named(Item, name)
        created = item is not None
        if item is None:  # added by someone else a moment ago
            item = name_in_use(Item, name)
    stock = get_or_create_stock(item, location)
    stock.quantity = min(stock.quantity + 1, MAX_QUANTITY)
    db.session.commit()
    what = f"Added new item {item.name}" if created else f"{item.name}"
    flash(f"{what}: {format_quantity(stock.quantity)} in {location.name}.", "success")
    return _back(url_for(".index", location=location.id))


@bp.route("/inventory/<int:stock_id>/adjust", methods=["POST"])
@family_required
def adjust(stock_id):
    _require_post_form()
    stock = get_for_family_or_404(Stock, stock_id)
    delta = request.form.get("delta")
    if delta not in ("1", "-1"):
        abort(400)
    stock.quantity = min(max(stock.quantity + int(delta), 0), MAX_QUANTITY)
    db.session.commit()
    return _row_response(stock, request.form.get("view", "location"))


@bp.route("/inventory/<int:stock_id>/set", methods=["POST"])
@family_required
def set_quantity(stock_id):
    _require_post_form()
    stock = get_for_family_or_404(Stock, stock_id)
    try:
        value = float(request.form.get("quantity", ""))
    except ValueError:
        value = None
    if value is None or not (0 <= value <= MAX_QUANTITY) or value != value:  # NaN check
        if _wants_row():
            return _render_row(stock, request.form.get("view", "location"), "Use a number, 0 or more.", 400)
        flash("Use a number, 0 or more.", "danger")
        return _back(url_for(".index", location=stock.location_id))
    stock.quantity = round(value, 2)
    db.session.commit()
    return _row_response(stock, request.form.get("view", "location"))


@bp.route("/inventory/<int:stock_id>/delete", methods=["POST"])
@family_required
def delete(stock_id):
    _require_post_form()
    stock = get_for_family_or_404(Stock, stock_id)
    name, place = stock.item.name, stock.location.name
    db.session.delete(stock)
    db.session.commit()
    flash(f"{name} is no longer kept in {place}.", "info")
    return _back(url_for(".index"))
