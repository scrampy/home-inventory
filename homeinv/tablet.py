"""Tablets: an old tablet kept in one place (say the cold room) for quick stock changes.

Setting one up: someone signs in on the tablet, opens the place, and taps "Use
this tablet here". That signs them out and leaves the tablet holding a
long-lived cookie, sent only to /tablet pages. With it the tablet can see and
change stock in that place and the places inside it, and nothing else. Unpair
from the place page to stop it.

The screen is built for old, slow browsers (Fire OS 5's Silk): plain forms that
work without JavaScript, plus static/tablet.js (ES5) to update one tile without
reloading the page.
"""

from datetime import timedelta
from functools import wraps

from flask import (Blueprint, abort, current_app, flash, g, make_response, redirect, render_template, request,
                   url_for)
from flask_login import current_user, logout_user
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from .extensions import db
from .forms import ActionForm
from .inventory import (MAX_QUANTITY, find_or_create_item, get_or_create_stock, take_off_list_if_restocked,
                        total_stock)
from .models import Item, Location, Stock, Tablet, clean_name, format_quantity, utcnow
from .places import descendants_and_self
from .security import current_family_id, family_required, get_for_family_or_404
from .shopping import entry_for, put_on_list

bp = Blueprint("tablet", __name__)

COOKIE = "homeinv_tablet"
COOKIE_PATH = "/tablet"
COOKIE_MAX_AGE = 5 * 365 * 24 * 60 * 60  # stays set up until unpaired
SEEN_EVERY = timedelta(minutes=10)  # how often "last used" is written


def _require_post_form():
    if not ActionForm().validate_on_submit():
        abort(400)


def _wants_tile():
    return request.headers.get("X-Requested-With") == "fetch"


def _no_store(response):
    # A tablet screen left open should never show a cached count.
    response.headers["Cache-Control"] = "no-store"
    return response


def _load_tablet():
    """The set-up tablet making this request (also kept as g.tablet), or None."""
    tablet = Tablet.find_by_token(request.cookies.get(COOKIE))
    if tablet is not None:
        g.tablet = tablet
        if utcnow() - tablet.last_seen_at > SEEN_EVERY:
            tablet.last_seen_at = utcnow()
            db.session.commit()
    return tablet


def tablet_required(view):
    """Only for a set-up tablet. Anything else goes back to the start page."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        if _load_tablet() is None:
            if _wants_tile():
                abort(401)  # tablet.js reloads, which shows the "not set up" page
            return redirect(url_for(".index"))
        return view(*args, **kwargs)

    return wrapped


def _place_ids():
    """The tablet's place and every place inside it."""
    if "tablet_place_ids" not in g:
        g.tablet_place_ids = set(descendants_and_self(g.tablet.location))
    return g.tablet_place_ids


def _stock_here_or_404(stock_id):
    stock = get_for_family_or_404(Stock, stock_id)
    if stock.location_id not in _place_ids():
        abort(404)
    return stock


def _tile_response(stock, list_removed=False):
    """The updated tile for tablet.js, or a redirect back to the screen."""
    if _wants_tile():
        response = make_response(render_template("tablet/_tile.html", stock=stock, here=g.tablet.location,
                                                 list_removed=list_removed))
        response.headers["X-Tile"] = "1"
        return _no_store(response)
    if list_removed:
        flash(f"Took {stock.item.name} off the shopping list.", "info")
    return redirect(url_for(".index") + f"#tile-{stock.id}")


# --- The tablet screen -----------------------------------------------------

@bp.route("/tablet")
def index():
    """The start page to point the tablet's browser at: its place's stock, or how to set it up."""
    if _load_tablet() is None:
        return _no_store(make_response(render_template("tablet/not_set_up.html")))
    here = g.tablet.location
    rows = db.session.scalars(
        select(Stock).where(Stock.location_id.in_(_place_ids())).join(Stock.item)
        .order_by(Item.name_key, Stock.location_id)
        .options(selectinload(Stock.item).selectinload(Item.list_entry), selectinload(Stock.location))
    ).all()
    item_names = db.session.scalars(
        select(Item.name).where(Item.family_id == current_family_id()).order_by(Item.name_key)).all()
    return _no_store(make_response(render_template("tablet/screen.html", here=here, rows=rows,
                                                   item_names=item_names)))


@bp.route("/tablet/stock/<int:stock_id>/adjust", methods=["POST"])
@tablet_required
def adjust(stock_id):
    _require_post_form()
    stock = _stock_here_or_404(stock_id)
    delta = request.form.get("delta")
    if delta not in ("1", "-1"):
        abort(400)
    before = total_stock(stock.item)
    stock.quantity = min(max(stock.quantity + int(delta), 0), MAX_QUANTITY)
    removed = take_off_list_if_restocked(stock.item, before)
    db.session.commit()
    return _tile_response(stock, list_removed=removed)


@bp.route("/tablet/stock/<int:stock_id>/list", methods=["POST"])
@tablet_required
def toggle_list(stock_id):
    """Put the item on the shopping list, or take it off again."""
    _require_post_form()
    stock = _stock_here_or_404(stock_id)
    entry = entry_for(stock.item)
    if entry is not None and not entry.in_cart:
        db.session.delete(entry)
    else:
        put_on_list(stock.item)
    db.session.commit()
    return _tile_response(stock)


@bp.route("/tablet/add", methods=["POST"])
@tablet_required
def add():
    """One more of an item in the tablet's place, creating the item if it's new."""
    _require_post_form()
    here = g.tablet.location
    name = clean_name(request.form.get("name"))
    if not name:
        flash("Type the name of what you're putting here.", "danger")
        return redirect(url_for(".index"))
    if len(name) > 80:
        flash("Item names can be up to 80 characters.", "danger")
        return redirect(url_for(".index"))
    item, created = find_or_create_item(name)
    before = total_stock(item)
    stock = get_or_create_stock(item, here)
    stock.quantity = min(stock.quantity + 1, MAX_QUANTITY)
    db.session.flush()
    removed = take_off_list_if_restocked(item, before)
    db.session.commit()
    flash(f"{'Added new item ' if created else ''}{item.name}: {format_quantity(stock.quantity)} in {here.name}.",
          "success")
    if removed:
        flash(f"Took {item.name} off the shopping list.", "info")
    return redirect(url_for(".index") + f"#tile-{stock.id}")


# --- Setting up and unpairing (from the place page, signed in) --------------

@bp.route("/tablet/setup", methods=["POST"])
@family_required
def setup():
    """Turn the device this is tapped on into the tablet for a place, and sign out on it."""
    _require_post_form()
    location_id = request.form.get("location_id", "")
    if not location_id.isdigit():
        abort(400)
    place = get_for_family_or_404(Location, int(location_id))

    # Set up before on this device? That pairing is replaced.
    old = Tablet.find_by_token(request.cookies.get(COOKIE))
    if old is not None:
        db.session.delete(old)
    tablet, token = Tablet.create(place, current_user._get_current_object())
    db.session.add(tablet)
    db.session.commit()

    place_name = place.name
    logout_user()
    flash(f"This tablet now looks after {place_name}.", "success")
    response = redirect(url_for(".index"))
    response.set_cookie(COOKIE, token, max_age=COOKIE_MAX_AGE, path=COOKIE_PATH, httponly=True,
                        samesite="Lax", secure=current_app.config.get("SESSION_COOKIE_SECURE", False))
    return response


@bp.route("/tablets/<int:tablet_id>/unpair", methods=["POST"])
@family_required
def unpair(tablet_id):
    _require_post_form()
    tablet = get_for_family_or_404(Tablet, tablet_id)
    place_id, place_name = tablet.location_id, tablet.location.name
    db.session.delete(tablet)
    db.session.commit()
    flash(f"Unpaired the {place_name} tablet. It can't change anything now.", "info")
    return redirect(url_for("places.show", place_id=place_id) + "#tablets")
