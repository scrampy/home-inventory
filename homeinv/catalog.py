"""The family's catalog: stores, aisles and items (places are in places.py).

Stores and aisles are simple named lists, so they share one set of routes and
one template, configured per kind in KINDS. Aisles also have an order: the
shopping list follows it, so it can match the walk through a store.
"""

from dataclasses import dataclass

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from .extensions import db
from .forms import ActionForm, ItemForm, NameForm
from .models import Aisle, Item, Store, clean_name, item_store, name_key
from .security import (current_family_id, family_required, family_rows, family_select,
                       get_for_family_or_404, name_in_use)

bp = Blueprint("catalog", __name__)


@dataclass(frozen=True)
class Kind:
    slug: str
    model: type
    singular: str
    plural: str
    blurb: str
    delete_warning: str
    suggestions: tuple = ()
    ordered: bool = False  # rows have a position the family can change


KINDS = {
    "stores": Kind(
        "stores", Store, "store", "Stores",
        "Where you shop. Link items to stores to filter the shopping list by store.",
        "Delete {name}? Items stay, but won't be linked to it any more.",
    ),
    "aisles": Kind(
        "aisles", Aisle, "aisle", "Aisles",
        "Sections of a store. Put them in the order you walk through the store: the shopping list follows it.",
        "Delete {name}? Its items will have no aisle.",
        ("Produce", "Bakery", "Dairy & eggs", "Meat & seafood", "Pantry", "Canned goods",
         "Snacks", "Drinks", "Frozen", "Household"),
        ordered=True,
    ),
}
KIND = "<any(stores, aisles):kind>"


def rows_for(kind):
    if kind.ordered:
        return db.session.scalars(select(kind.model).where(kind.model.family_id == current_family_id())
                                  .order_by(kind.model.position, kind.model.name_key)).all()
    return family_rows(kind.model)


def ordered_aisles():
    return rows_for(KINDS["aisles"])


def _require_post_form():
    if not ActionForm().validate_on_submit():
        abort(400)


def add_named(model, name, **fields):
    """Add a row to the current family. Returns None if the name is already used."""
    if name_in_use(model, name):
        return None
    row = model(family_id=current_family_id(), **fields)
    if hasattr(model, "position") and "position" not in fields:
        last = db.session.scalar(select(func.max(model.position)).where(model.family_id == current_family_id()))
        row.position = (last or 0) + 1  # new ones go at the end
    row.set_name(name)
    db.session.add(row)
    try:
        db.session.commit()
    except IntegrityError:  # someone added the same name a moment ago
        db.session.rollback()
        return None
    return row


def usage_counts(kind):
    """{row id: number of items using it} for stores and aisles."""
    family_id = current_family_id()
    if kind.model is Aisle:
        query = (select(Item.aisle_id, func.count()).where(Item.family_id == family_id,
                 Item.aisle_id.is_not(None)).group_by(Item.aisle_id))
    else:
        query = (select(item_store.c.store_id, func.count()).join(Store, Store.id == item_store.c.store_id)
                 .where(Store.family_id == family_id).group_by(item_store.c.store_id))
    return dict(db.session.execute(query).all())


# --- Stores and aisles ------------------------------------------------------

@bp.route(f"/{KIND}", methods=["GET", "POST"])
@family_required
def named_list(kind):
    kind = KINDS[kind]
    form = NameForm()
    if form.validate_on_submit():
        row = add_named(kind.model, form.name.data)
        if row:
            flash(f"Added {row.name}.", "success")
            return redirect(url_for(".named_list", kind=kind.slug))
        form.name.errors.append(f"There's already a {kind.singular} called {clean_name(form.name.data)}.")
    rows = rows_for(kind)
    taken = {r.name_key for r in rows}
    suggestions = [s for s in kind.suggestions if name_key(s) not in taken]
    return render_template("catalog/named_list.html", kind=kind, rows=rows, form=form,
                           counts=usage_counts(kind), suggestions=suggestions)


@bp.route(f"/{KIND}/suggestions", methods=["POST"])
@family_required
def add_suggestions(kind):
    _require_post_form()
    kind = KINDS[kind]
    added = [s for s in kind.suggestions if add_named(kind.model, s)]
    if added:
        flash(f"Added {', '.join(added)}.", "success")
    return redirect(url_for(".named_list", kind=kind.slug))


@bp.route(f"/{KIND}/<int:row_id>/rename", methods=["POST"])
@family_required
def rename(kind, row_id):
    kind = KINDS[kind]
    row = get_for_family_or_404(kind.model, row_id)
    form = NameForm()
    if not form.validate_on_submit():
        flash("Enter a name.", "danger")
    elif name_in_use(kind.model, form.name.data, exclude_id=row.id):
        flash(f"There's already a {kind.singular} called {clean_name(form.name.data)}.", "danger")
    else:
        old = row.name
        row.set_name(form.name.data)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash(f"There's already a {kind.singular} called {clean_name(form.name.data)}.", "danger")
        else:
            if old != row.name:
                flash(f"Renamed {old} to {row.name}.", "success")
    return redirect(url_for(".named_list", kind=kind.slug))


@bp.route(f"/{KIND}/<int:row_id>/move", methods=["POST"])
@family_required
def move(kind, row_id):
    """Move an aisle up or down the store order."""
    _require_post_form()
    kind = KINDS[kind]
    if not kind.ordered:
        abort(404)
    row = get_for_family_or_404(kind.model, row_id)
    direction = request.form.get("direction")
    if direction not in ("up", "down"):
        abort(400)
    rows = rows_for(kind)
    index = rows.index(row)
    other = index - 1 if direction == "up" else index + 1
    if 0 <= other < len(rows):
        rows[index], rows[other] = rows[other], rows[index]
        for position, r in enumerate(rows, start=1):
            r.position = position
        db.session.commit()
    return redirect(url_for(".named_list", kind=kind.slug) + f"#row-{row.id}")


@bp.route(f"/{KIND}/<int:row_id>/delete", methods=["POST"])
@family_required
def delete(kind, row_id):
    _require_post_form()
    kind = KINDS[kind]
    row = get_for_family_or_404(kind.model, row_id)
    db.session.delete(row)
    db.session.commit()
    flash(f"Deleted {row.name}.", "info")
    return redirect(url_for(".named_list", kind=kind.slug))


# --- Items -----------------------------------------------------------------

@bp.route("/items", methods=["GET", "POST"])
@family_required
def items():
    form = NameForm()
    if form.validate_on_submit():
        item = add_named(Item, form.name.data)
        if item:
            flash(f"Added {item.name}.", "success")
            return redirect(url_for(".items"))
        form.name.errors.append(f"There's already an item called {clean_name(form.name.data)}.")

    search = (request.args.get("q") or "").strip()
    query = family_select(Item).options(selectinload(Item.stores), selectinload(Item.aisle))
    if search:
        query = query.where(Item.name_key.contains(name_key(search), autoescape=True))
    rows = db.session.scalars(query).all()
    return render_template("catalog/items.html", form=form, items=rows, search=search)


@bp.route("/items/<int:item_id>")
@family_required
def item(item_id):
    """What a family member wants to know: how many, where, is it on the list, where to buy it."""
    from .places import place_choices

    item = get_for_family_or_404(Item, item_id)
    stock = sorted(item.stock, key=lambda s: -s.quantity)
    kept_at = {s.location_id for s in stock}
    total = sum(s.quantity for s in stock)
    entry = item.list_entry
    return render_template(
        "catalog/item.html", item=item, stock=stock, total=total,
        is_out=bool(stock) and total <= 0,
        is_low=total > 0 and item.low_stock_threshold is not None and total <= item.low_stock_threshold,
        entry=entry if entry is not None and not entry.in_cart else None,
        in_cart=entry is not None and entry.in_cart,
        other_places=[c for c in place_choices() if c[0] not in kept_at],
        stores=family_rows(Store))


@bp.route("/items/<int:item_id>/stores/<int:store_id>", methods=["POST"])
@family_required
def toggle_store(item_id, store_id):
    """Tap a store on the item page to say whether it's sold there."""
    _require_post_form()
    item = get_for_family_or_404(Item, item_id)
    store = get_for_family_or_404(Store, store_id)
    if store in item.stores:
        item.stores.remove(store)
    else:
        item.stores.append(store)
    db.session.commit()
    return redirect(url_for(".item", item_id=item.id) + "#buy-at")


@bp.route("/items/<int:item_id>/edit", methods=["GET", "POST"])
@family_required
def item_edit(item_id):
    item = get_for_family_or_404(Item, item_id)
    aisles = ordered_aisles()
    stores = family_rows(Store)

    form = ItemForm(obj=item)
    form.aisle_id.choices = [(0, "No aisle")] + [(a.id, a.name) for a in aisles]
    form.store_ids.choices = [(s.id, s.name) for s in stores]
    if request.method == "GET":
        form.aisle_id.data = item.aisle_id or 0
        form.store_ids.data = [s.id for s in item.stores]

    if form.validate_on_submit():
        if name_in_use(Item, form.name.data, exclude_id=item.id):
            form.name.errors.append(f"There's already an item called {clean_name(form.name.data)}.")
        else:
            chosen = set(form.store_ids.data)
            item.set_name(form.name.data)
            item.aisle_id = form.aisle_id.data or None
            item.stores = [s for s in stores if s.id in chosen]
            item.default_unit = clean_name(form.default_unit.data) or None
            item.low_stock_threshold = form.low_stock_threshold.data
            item.notes = (form.notes.data or "").strip() or None
            db.session.commit()
            flash(f"Saved {item.name}.", "success")
            return redirect(url_for(".item", item_id=item.id))

    return render_template("catalog/item_edit.html", item=item, form=form,
                           has_aisles=bool(aisles), has_stores=bool(stores))


@bp.route("/items/<int:item_id>/delete", methods=["POST"])
@family_required
def item_delete(item_id):
    _require_post_form()
    item = get_for_family_or_404(Item, item_id)
    db.session.delete(item)
    db.session.commit()
    flash(f"Deleted {item.name}.", "info")
    return redirect(url_for(".items"))
