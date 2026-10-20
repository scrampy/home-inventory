"""Prices: what the family usually pays for an item, and whether a shelf price is a good one.

Kept light: a price is an amount, stamped with the day and (optionally) the
store. "Usual" is the median of the last few prices, so one sale or one
expensive week doesn't swing it.
"""

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from statistics import median

from flask import Blueprint, abort, flash, redirect, request, session, url_for
from flask_login import current_user

from .extensions import db
from .forms import ActionForm
from .models import Item, Price, Store, utcnow
from .security import current_family_id, family_required, get_for_family_or_404, safe_next_url

bp = Blueprint("prices", __name__)

RECENT = 5          # prices that make up "usual"
CLOSE_ENOUGH = 0.05  # within 5% of usual counts as "about usual"
MAX_CENTS = 10_000_000  # $100,000


# --- Money -----------------------------------------------------------------

def parse_money(text):
    """'$4.99', '4.99', '4,99', ' 5 ' -> cents. None if it isn't a sensible price."""
    raw = (text or "").strip().replace("$", "").replace(" ", "")
    if "," in raw and "." not in raw:
        raw = raw.replace(",", ".")  # 4,99
    raw = raw.replace(",", "")       # 1,299.00
    if not raw:
        return None
    try:
        value = Decimal(raw)
    except InvalidOperation:
        return None
    if not value.is_finite() or value <= 0:
        return None
    cents = int((value * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    return cents if 0 < cents <= MAX_CENTS else None


def money(cents):
    if cents is None:
        return ""
    return f"${cents // 100:,}.{cents % 100:02d}"


def ago(moment):
    """'today', 'yesterday', '5 days ago', '3 weeks ago', 'Mar 4'."""
    days = (utcnow().date() - moment.date()).days
    if days <= 0:
        return "today"
    if days == 1:
        return "yesterday"
    if days < 14:
        return f"{days} days ago"
    if days < 60:
        return f"{days // 7} weeks ago"
    text = f"{moment.strftime('%b')} {moment.day}"  # "Mar 4" (no zero padding on any platform)
    return f"{text}, {moment.year}" if days > 330 else text


@bp.app_template_filter("money")
def money_filter(cents):
    return money(cents)


@bp.app_template_filter("ago")
def ago_filter(moment):
    return ago(moment)


# --- Summary and verdict ---------------------------------------------------

def _usual(cents_list):
    return int(round(median(cents_list))) if cents_list else None


def summary(item):
    """What we know about an item's price, or None if nothing's been recorded.

    Uses item.prices, newest first (load it with selectinload for lists of items).
    """
    prices = list(item.prices)
    if not prices:
        return None
    by_store = {}
    for p in prices:
        if p.store is not None:
            by_store.setdefault(p.store, []).append(p.cents)
    return {
        "usual": _usual([p.cents for p in prices[:RECENT]]),
        "last": prices[0],
        "lowest": min(prices, key=lambda p: (p.cents, -p.recorded_at.timestamp())),
        "count": len(prices),
        # Usual at each store, from its last few prices; cheapest first.
        "stores": sorted(((store, _usual(cents[:RECENT])) for store, cents in by_store.items()),
                         key=lambda pair: (pair[1], pair[0].name_key)),
    }


def verdict(cents, info):
    """How a shelf price compares with what we usually pay."""
    if info is None:
        return {"kind": "new", "text": "No price recorded yet. Save this one to compare next time."}
    usual = info["usual"]
    change = (cents - usual) / usual
    pct = round(abs(change) * 100)
    if cents < info["lowest"].cents:
        return {"kind": "good", "text": f"Lowest yet: {pct}% below usual ({money(usual)})."}
    if change <= -CLOSE_ENOUGH:
        return {"kind": "good", "text": f"Good price: {pct}% below usual ({money(usual)})."}
    if change >= CLOSE_ENOUGH:
        return {"kind": "high", "text": f"Higher than usual: {pct}% above {money(usual)}."}
    return {"kind": "usual", "text": f"About what we usually pay ({money(usual)})."}


def shopping_store():
    """The store picked on the shopping list, if any: the best guess for where a price was seen."""
    value = session.get("list_store")
    if value and str(value).isdigit():
        store = db.session.get(Store, int(value))
        if store is not None and store.family_id == current_family_id():
            return store
    return None


def record(item, cents, store=None):
    price = Price(family_id=item.family_id, item=item, store=store, cents=cents,
                  added_by_id=current_user.id if current_user.is_authenticated else None)
    db.session.add(price)
    return price


# --- Routes ----------------------------------------------------------------

def _require_post_form():
    if not ActionForm().validate_on_submit():
        abort(400)


@bp.route("/items/<int:item_id>/prices", methods=["POST"])
@family_required
def add(item_id):
    _require_post_form()
    item = get_for_family_or_404(Item, item_id)
    back = safe_next_url(request.form.get("next"), url_for("catalog.item", item_id=item.id))
    cents = parse_money(request.form.get("price"))
    if cents is None:
        flash("Enter a price like 4.99.", "danger")
        return redirect(back)
    store = None
    store_id = request.form.get("store_id", "")
    if store_id:
        if not store_id.isdigit():
            abort(400)
        store = get_for_family_or_404(Store, int(store_id))
    record(item, cents, store)
    db.session.commit()
    flash(f"Saved {money(cents)} for {item.name}" + (f" at {store.name}." if store else "."), "success")
    return redirect(back)


@bp.route("/prices/<int:price_id>/delete", methods=["POST"])
@family_required
def delete(price_id):
    _require_post_form()
    price = get_for_family_or_404(Price, price_id)
    item_id = price.item_id
    db.session.delete(price)
    db.session.commit()
    flash("Price removed.", "info")
    return redirect(url_for("catalog.item", item_id=item_id) + "#prices")
