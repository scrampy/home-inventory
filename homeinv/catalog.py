"""The family's catalog: locations, stores, aisles and items.

Locations, stores and aisles are simple named lists, so they share one set of
routes and one template, configured per kind in KINDS.
"""

from dataclasses import dataclass

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from .extensions import db
from .forms import ActionForm, ItemForm, NameForm
from .models import Aisle, Item, Location, Stock, Store, clean_name, item_store, name_key
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


KINDS = {
    "locations": Kind(
        "locations", Location, "location", "Locations",
        "Places you keep things, like the pantry or the garage freezer.",
        "Delete {name}? Anything recorded there is removed from the inventory.",
        ("Pantry", "Refrigerator", "Freezer"),
    ),
    "stores": Kind(
        "stores", Store, "store", "Stores",
        "Where you shop. Link items to stores to filter the shopping list by store.",
        "Delete {name}? Items stay, but won't be linked to it any more.",
    ),
    "aisles": Kind(
        "aisles", Aisle, "aisle", "Aisles",
        "Sections of a store, used to group the shopping list.",
        "Delete {name}? Its items will have no aisle.",
        ("Produce", "Bakery", "Dairy", "Meat & seafood", "Frozen", "Canned goods",
         "Dry goods", "Snacks", "Drinks", "Household"),
    ),
}
KIND = "<any(locations, stores, aisles):kind>"


def _require_post_form():
    if not ActionForm().validate_on_submit():
        abort(400)


def add_named(model, name, **fields):
    """Add a row to the current family. Returns None if the name is already used."""
    if name_in_use(model, name):
        return None
    row = model(family_id=current_family_id(), **fields)
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
    elif kind.model is Store:
        query = (select(item_store.c.store_id, func.count()).join(Store, Store.id == item_store.c.store_id)
                 .where(Store.family_id == family_id).group_by(item_store.c.store_id))
    else:
        query = (select(Stock.location_id, func.count()).where(Stock.family_id == family_id)
                 .group_by(Stock.location_id))
    return dict(db.session.execute(query).all())


# --- Locations, stores, aisles ---------------------------------------------

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
    rows = family_rows(kind.model)
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
        form.name.errors.append(f"{clean_name(form.name.data)} is already on the list.")

    search = (request.args.get("q") or "").strip()
    query = family_select(Item).options(selectinload(Item.stores), selectinload(Item.aisle))
    if search:
        query = query.where(Item.name_key.contains(name_key(search), autoescape=True))
    rows = db.session.scalars(query).all()
    return render_template("catalog/items.html", form=form, items=rows, search=search)


@bp.route("/items/<int:item_id>", methods=["GET", "POST"])
@family_required
def item_edit(item_id):
    item = get_for_family_or_404(Item, item_id)
    aisles = family_rows(Aisle)
    stores = family_rows(Store)

    form = ItemForm(obj=item)
    form.aisle_id.choices = [(0, "No aisle")] + [(a.id, a.name) for a in aisles]
    form.store_ids.choices = [(s.id, s.name) for s in stores]
    if request.method == "GET":
        form.aisle_id.data = item.aisle_id or 0
        form.store_ids.data = [s.id for s in item.stores]

    if form.validate_on_submit():
        if name_in_use(Item, form.name.data, exclude_id=item.id):
            form.name.errors.append(f"{clean_name(form.name.data)} is already on the list.")
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
            return redirect(url_for(".items"))

    stock = sorted(item.stock, key=lambda s: s.location.name_key)
    kept_at = {s.location_id for s in stock}
    other_locations = [loc for loc in family_rows(Location) if loc.id not in kept_at]
    return render_template("catalog/item_edit.html", item=item, form=form,
                           has_aisles=bool(aisles), has_stores=bool(stores),
                           stock=stock, other_locations=other_locations)


@bp.route("/items/<int:item_id>/delete", methods=["POST"])
@family_required
def item_delete(item_id):
    _require_post_form()
    item = get_for_family_or_404(Item, item_id)
    db.session.delete(item)
    db.session.commit()
    flash(f"Deleted {item.name}.", "info")
    return redirect(url_for(".items"))
