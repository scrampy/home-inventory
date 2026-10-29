"""Stock changes: how much of an item is kept in a place.

The pages that show stock are the place pages (places.py), the item page and
Find. Changes made with the +/- buttons and the quantity box update the row in
place when JavaScript is available (static/app.js asks for just the row's
HTML); without it the forms post normally and the page reloads.
"""

from flask import Blueprint, abort, flash, make_response, redirect, render_template, request, url_for
from sqlalchemy import select

from .catalog import add_named
from .extensions import db
from .forms import ActionForm
from .models import Item, ListEntry, Location, Stock, clean_name, format_quantity
from .security import family_required, get_for_family_or_404, name_in_use, safe_next_url

bp = Blueprint("inventory", __name__)

MAX_QUANTITY = 100_000


def _require_post_form():
    if not ActionForm().validate_on_submit():
        abort(400)


def _wants_row():
    return request.headers.get("X-Requested-With") == "fetch"


def _back(default):
    return redirect(safe_next_url(request.form.get("next") or request.args.get("next"), default))


def _render_row(stock, view, error=None, status=200, list_removed=False):
    response = make_response(render_template("inventory/_row.html", stock=stock, view=view, error=error,
                                             list_removed=list_removed), status)
    response.headers["X-Row"] = "1"  # tells static/app.js this is a row it can swap in
    if list_removed:
        from .shopping import open_count  # imported here: shopping imports this module
        response.headers["X-List-Count"] = str(open_count())  # so the List tab's badge can update
    return response


def _row_response(stock, view, list_removed=False):
    """After a change: the updated row for in-place updates, or a redirect back."""
    if _wants_row():
        return _render_row(stock, view, list_removed=list_removed)
    if list_removed:
        flash(_removed_message(stock.item), "info")
    return _back(url_for("places.show", place_id=stock.location_id))


def total_stock(item):
    return sum(s.quantity for s in item.stock)


def take_off_list_if_restocked(item, total_before):
    """If the item was out everywhere and now isn't, its shopping-list entry is done: remove it.

    Only entries still "to get". Ticked-into-the-cart ones are left for Done
    shopping, which puts them away and records the price. Returns True if one
    was removed.
    """
    if total_before > 0 or total_stock(item) <= 0:
        return False
    entry = db.session.scalar(select(ListEntry).filter_by(family_id=item.family_id, item_id=item.id))
    if entry is None or entry.in_cart:
        return False
    db.session.delete(entry)
    return True


def _removed_message(item):
    return f"Took {item.name} off the shopping list: you have some now."


@bp.app_template_filter("qty")
def qty_filter(value):
    return format_quantity(value)


def get_or_create_stock(item, location):
    stock = db.session.scalar(select(Stock).filter_by(item_id=item.id, location_id=location.id))
    if stock is None:
        stock = Stock(family_id=item.family_id, item=item, location=location, quantity=0)
        db.session.add(stock)
    return stock


def find_or_create_item(name):
    """The family's item with this name (any case), created if new. Returns (item, created)."""
    item = name_in_use(Item, name)
    if item is not None:
        return item, False
    item = add_named(Item, name)
    if item is None:  # added by someone else a moment ago
        return name_in_use(Item, name), False
    return item, True


@bp.route("/inventory/add", methods=["POST"])
@family_required
def add():
    """Put an item in a place: +1 if it's already there, creating the item if it's new."""
    _require_post_form()
    location_id = request.form.get("location_id", "")
    name = clean_name(request.form.get("name"))
    if not location_id.isdigit():
        flash("Choose a place.", "danger")
        return _back(url_for("places.index"))
    location = get_for_family_or_404(Location, int(location_id))
    back = url_for("places.show", place_id=location.id)
    if not name:
        flash("Enter an item name.", "danger")
        return _back(back)
    if len(name) > 80:
        flash("Item names can be up to 80 characters.", "danger")
        return _back(back)

    item, created = find_or_create_item(name)
    before = total_stock(item)
    stock = get_or_create_stock(item, location)
    stock.quantity = min(stock.quantity + 1, MAX_QUANTITY)
    db.session.flush()
    removed = take_off_list_if_restocked(item, before)
    db.session.commit()
    what = f"Added new item {item.name}" if created else item.name
    flash(f"{what}: {format_quantity(stock.quantity)} in {location.name}.", "success")
    if removed:
        flash(_removed_message(item), "info")
    return _back(back)


@bp.route("/inventory/<int:stock_id>/adjust", methods=["POST"])
@family_required
def adjust(stock_id):
    _require_post_form()
    stock = get_for_family_or_404(Stock, stock_id)
    delta = request.form.get("delta")
    if delta not in ("1", "-1"):
        abort(400)
    before = total_stock(stock.item)
    stock.quantity = min(max(stock.quantity + int(delta), 0), MAX_QUANTITY)
    removed = take_off_list_if_restocked(stock.item, before)
    db.session.commit()
    return _row_response(stock, request.form.get("view", "location"), list_removed=removed)


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
        return _back(url_for("places.show", place_id=stock.location_id))
    before = total_stock(stock.item)
    stock.quantity = round(value, 2)
    removed = take_off_list_if_restocked(stock.item, before)
    db.session.commit()
    return _row_response(stock, request.form.get("view", "location"), list_removed=removed)


@bp.route("/inventory/<int:stock_id>/delete", methods=["POST"])
@family_required
def delete(stock_id):
    _require_post_form()
    stock = get_for_family_or_404(Stock, stock_id)
    name, place, place_id = stock.item.name, stock.location.name, stock.location_id
    db.session.delete(stock)
    db.session.commit()
    flash(f"{name} is no longer kept in {place}.", "info")
    return _back(url_for("places.show", place_id=place_id))
