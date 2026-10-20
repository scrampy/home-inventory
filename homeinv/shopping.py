"""The family's shopping list.

One list per family. When shopping, pick the store you're at: the list shows
what that store sells plus anything not tied to a store, grouped by aisle in
the family's aisle order. Ticked items move to "In the cart"; "Done shopping"
can add them to the inventory.
"""

from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from .extensions import db
from .forms import ActionForm
from .inventory import MAX_QUANTITY, find_or_create_item, get_or_create_stock
from .models import Aisle, Item, ListEntry, Location, Stock, Store, clean_name, format_quantity
from .places import place_choices
from .prices import parse_money, record as record_price, shopping_store, summary as price_summary
from .security import current_family_id, family_required, family_rows, get_for_family_or_404, safe_next_url
from flask_login import current_user

bp = Blueprint("shopping", __name__)

OTHER = "Other"


def _require_post_form():
    if not ActionForm().validate_on_submit():
        abort(400)


def _back(default):
    return redirect(safe_next_url(request.form.get("next") or request.args.get("next"), default))


def open_count():
    """Items still to get, for the List tab's badge."""
    return db.session.scalar(select(func.count()).select_from(ListEntry).where(
        ListEntry.family_id == current_family_id(), ListEntry.in_cart.is_(False))) or 0


def entry_for(item):
    return db.session.scalar(select(ListEntry).filter_by(family_id=item.family_id, item_id=item.id))


def put_on_list(item, quantity=1):
    """Put an item on the list (or back from the cart). Returns (entry, was_already_there)."""
    entry = entry_for(item)
    if entry is not None:
        already = not entry.in_cart
        entry.in_cart = False
        return entry, already
    entry = ListEntry(family_id=item.family_id, item=item, quantity=quantity,
                      added_by_id=current_user.id if current_user.is_authenticated else None)
    db.session.add(entry)
    return entry, False


def running_low(limit=None):
    """Items that are out or at/below their warning level, with where they are. Most urgent first."""
    items = db.session.scalars(
        select(Item).where(Item.family_id == current_family_id())
        .options(selectinload(Item.stock).selectinload(Stock.location), selectinload(Item.list_entry))
        .order_by(Item.name_key)).all()
    low = []
    for item in items:
        if not item.stock:
            continue
        total = sum(s.quantity for s in item.stock)
        out = total <= 0
        if out or (item.low_stock_threshold is not None and total <= item.low_stock_threshold):
            low.append({"item": item, "total": total, "out": out,
                        "on_list": item.list_entry is not None and not item.list_entry.in_cart})
    low.sort(key=lambda r: (not r["out"], r["item"].name_key))
    return low[:limit] if limit else low


def _store_choice():
    """The store picked on the list (remembered per person), or None for all stores."""
    value = request.args.get("store")
    if value is not None:
        session["list_store"] = value
    else:
        value = session.get("list_store", "all")
    if value and value.isdigit():
        store = db.session.get(Store, int(value))
        if store is not None and store.family_id == current_family_id():
            return store
    return None


def _sold_at(entry, store):
    return store is None or not entry.item.stores or store in entry.item.stores


@bp.route("/list")
@family_required
def index():
    store = _store_choice()
    show_all = request.args.get("all") == "1"
    entries = db.session.scalars(
        select(ListEntry).where(ListEntry.family_id == current_family_id())
        .join(ListEntry.item).order_by(Item.name_key)
        .options(selectinload(ListEntry.item).selectinload(Item.stores),
                 selectinload(ListEntry.item).selectinload(Item.aisle),
                 selectinload(ListEntry.item).selectinload(Item.prices))).all()
    to_get = [e for e in entries if not e.in_cart]
    cart = [e for e in entries if e.in_cart]
    visible = [e for e in to_get if show_all or _sold_at(e, store)]

    aisles = db.session.scalars(select(Aisle).where(Aisle.family_id == current_family_id())
                                .order_by(Aisle.position, Aisle.name_key)).all()
    groups = []
    for aisle in aisles:
        rows = [e for e in visible if e.item.aisle_id == aisle.id]
        if rows:
            groups.append((aisle.name, rows))
    other = [e for e in visible if e.item.aisle_id is None]
    if other:
        groups.append((OTHER, other))

    on_list = {e.item_id for e in entries}
    suggestions = [r for r in running_low() if r["item"].id not in on_list][:8]
    item_names = db.session.scalars(select(Item.name).where(Item.family_id == current_family_id())
                                    .order_by(Item.name_key)).all()
    usual = {}
    for e in entries:
        info = price_summary(e.item)
        if info:
            at_store = dict(info["stores"]).get(store) if store else None
            usual[e.id] = at_store or info["usual"]
    return render_template(
        "shopping/index.html", store=store, usual=usual, stores=family_rows(Store), groups=groups, cart=cart,
        to_get=to_get, hidden=len(to_get) - len(visible), show_all=show_all,
        suggestions=suggestions, item_names=item_names)


@bp.route("/list/add", methods=["POST"])
@family_required
def add():
    """Add by name, creating the item if it's new."""
    _require_post_form()
    name = clean_name(request.form.get("name"))
    if not name:
        flash("Type what you need.", "danger")
        return _back(url_for(".index"))
    if len(name) > 80:
        flash("Item names can be up to 80 characters.", "danger")
        return _back(url_for(".index"))
    item, created = find_or_create_item(name)
    entry, already = put_on_list(item)
    db.session.commit()
    if already:
        flash(f"{item.name} is already on the list.", "info")
    else:
        flash(f"Added {item.name} to the list." + (" (New item.)" if created else ""), "success")
    return _back(url_for(".index"))


@bp.route("/list/items/<int:item_id>/toggle", methods=["POST"])
@family_required
def toggle_item(item_id):
    """Add an item to the list, or take it off. Used from Find, places and the item page."""
    _require_post_form()
    item = get_for_family_or_404(Item, item_id)
    entry = entry_for(item)
    if entry is not None and not entry.in_cart:
        db.session.delete(entry)
        message = f"Took {item.name} off the list."
    else:
        put_on_list(item)
        message = f"Added {item.name} to the list."
    db.session.commit()
    flash(message, "success")
    return _back(url_for(".index"))


@bp.route("/list/<int:entry_id>/cart", methods=["POST"])
@family_required
def toggle_cart(entry_id):
    _require_post_form()
    entry = get_for_family_or_404(ListEntry, entry_id)
    entry.in_cart = not entry.in_cart
    db.session.commit()
    return _back(url_for(".index"))


@bp.route("/list/<int:entry_id>/quantity", methods=["POST"])
@family_required
def quantity(entry_id):
    _require_post_form()
    entry = get_for_family_or_404(ListEntry, entry_id)
    delta = request.form.get("delta")
    if delta not in ("1", "-1"):
        abort(400)
    entry.quantity = min(max(entry.quantity + int(delta), 1), MAX_QUANTITY)
    db.session.commit()
    return _back(url_for(".index"))


@bp.route("/list/<int:entry_id>/remove", methods=["POST"])
@family_required
def remove(entry_id):
    _require_post_form()
    entry = get_for_family_or_404(ListEntry, entry_id)
    name = entry.item.name
    db.session.delete(entry)
    db.session.commit()
    flash(f"Took {name} off the list.", "info")
    return _back(url_for(".index"))


def _suggested_place(item):
    """Where bought items usually go: the place with the most of it, else the place it was last counted in."""
    if not item.stock:
        return None
    return max(item.stock, key=lambda s: (s.quantity, s.updated_at)).location_id


@bp.route("/list/done", methods=["GET", "POST"])
@family_required
def done():
    """Finish shopping: add what's in the cart to the inventory (or just clear it)."""
    cart = db.session.scalars(
        select(ListEntry).where(ListEntry.family_id == current_family_id(), ListEntry.in_cart.is_(True))
        .join(ListEntry.item).order_by(Item.name_key)
        .options(selectinload(ListEntry.item).selectinload(Item.stock))).all()
    if not cart:
        flash("Nothing in the cart yet. Tap items on the list as you pick them up.", "info")
        return redirect(url_for(".index"))

    if request.method == "POST":
        _require_post_form()
        action = request.form.get("action")
        if action not in ("put_away", "clear"):
            abort(400)
        added = []
        bought_at = None
        store_id = request.form.get("store_id", "")
        if store_id:
            if not store_id.isdigit():
                abort(400)
            bought_at = get_for_family_or_404(Store, int(store_id))
        priced = 0
        for entry in cart:
            cents = parse_money(request.form.get(f"price_{entry.id}"))
            if cents is not None:
                record_price(entry.item, cents, bought_at)
                priced += 1
        if action == "put_away":
            for entry in cart:
                value = request.form.get(f"place_{entry.id}", "")
                if not value.isdigit():
                    continue  # "Don't add" for this one
                place = get_for_family_or_404(Location, int(value))
                stock = get_or_create_stock(entry.item, place)
                stock.quantity = min(stock.quantity + entry.quantity, MAX_QUANTITY)
                added.append(f"{entry.item.name} → {place.name}")
        names = len(cart)
        for entry in cart:
            db.session.delete(entry)
        db.session.commit()
        if added:
            flash("Put away: " + ", ".join(added) + ".", "success")
        if priced:
            flash(f"Saved {priced} price{'s' if priced != 1 else ''}.", "success")
        flash(f"Cleared {names} item{'s' if names != 1 else ''} from the list.", "info")
        return redirect(url_for(".index"))

    rows = [{"entry": e, "suggested": _suggested_place(e.item),
             "qty": format_quantity(e.quantity)} for e in cart]
    return render_template("shopping/done.html", rows=rows, choices=place_choices(),
                           stores=family_rows(Store), bought_at=shopping_store())
