"""Places: where things are kept, as a tree (Home › Basement › Freezer).

Stored as Location rows with a parent. A place's counts include everything in
the places inside it.
"""

from dataclasses import dataclass, field

from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from .extensions import db
from .forms import ActionForm
from .models import Item, Location, Stock, clean_name, name_key
from .security import current_family_id, family_required, get_for_family_or_404

bp = Blueprint("places", __name__)

SEPARATOR = " › "


# --- The tree --------------------------------------------------------------

@dataclass
class Node:
    place: Location
    children: list = field(default_factory=list)
    items: int = 0  # stock rows here and below
    out: int = 0    # of those, how many are at zero
    depth: int = 0


def family_places():
    """All the current family's places, loaded once per request."""
    if "family_places" not in g:
        g.family_places = db.session.scalars(
            select(Location).where(Location.family_id == current_family_id()).order_by(Location.name_key)
        ).all()
    return g.family_places


def build_tree():
    """Root nodes, each with children, depth and rolled-up counts."""
    places = family_places()
    nodes = {p.id: Node(p) for p in places}
    roots = []
    for p in places:
        (nodes[p.parent_id].children if p.parent_id in nodes else roots).append(nodes[p.id])

    direct = {}
    for location_id, quantity in db.session.execute(
            select(Stock.location_id, Stock.quantity).where(Stock.family_id == current_family_id())):
        items, out = direct.get(location_id, (0, 0))
        direct[location_id] = (items + 1, out + (1 if quantity <= 0 else 0))

    def fill(node, depth):
        node.depth = depth
        node.items, node.out = direct.get(node.place.id, (0, 0))
        for child in node.children:
            fill(child, depth + 1)
            node.items += child.items
            node.out += child.out

    for root in roots:
        fill(root, 0)
    return roots, nodes


def ancestors(place):
    """From the top down, not including the place itself."""
    by_id = {p.id: p for p in family_places()}
    chain, seen = [], set()
    current = by_id.get(place.parent_id)
    while current is not None and current.id not in seen:
        seen.add(current.id)
        chain.append(current)
        current = by_id.get(current.parent_id)
    return list(reversed(chain))


def place_path(place, short=True):
    """ "Basement › Freezer". With one top-level place (like Home), it's left out when short."""
    names = [p.name for p in ancestors(place)] + [place.name]
    if short and len(names) > 1 and sum(1 for p in family_places() if p.parent_id is None) == 1:
        names = names[1:]
    return SEPARATOR.join(names)


def place_choices(exclude=None):
    """(id, label) for every place, in tree order. `exclude` drops that place and everything inside it."""
    roots, _ = build_tree()
    out = []

    def walk(node):
        if exclude is not None and node.place.id == exclude.id:
            return
        out.append((node.place.id, place_path(node.place, short=False)))
        for child in node.children:
            walk(child)

    for root in roots:
        walk(root)
    return out


def descendants_and_self(place):
    _, nodes = build_tree()
    ids, stack = [], [nodes[place.id]]
    while stack:
        node = stack.pop()
        ids.append(node.place.id)
        stack.extend(node.children)
    return ids


@bp.app_template_global("place_path")
def place_path_global(place, short=True):
    return place_path(place, short)


# --- Helpers for changes ---------------------------------------------------

def _require_post_form():
    if not ActionForm().validate_on_submit():
        abort(400)


def _sibling_with_name(name, parent_id, exclude_id=None):
    query = select(Location).where(Location.family_id == current_family_id(),
                                   Location.name_key == name_key(name),
                                   Location.parent_id.is_(None) if parent_id is None else Location.parent_id == parent_id)
    if exclude_id is not None:
        query = query.where(Location.id != exclude_id)
    return db.session.scalar(query)


def _parent_from_form(field="parent_id"):
    """The chosen parent place (or None for top level). Another family's place is a 404."""
    value = request.form.get(field, "")
    if not value:
        return None
    if not value.isdigit():
        abort(400)
    return get_for_family_or_404(Location, int(value))


def _name_from_form():
    name = clean_name(request.form.get("name"))
    if not name:
        flash("Give the place a name.", "danger")
        return None
    if len(name) > 80:
        flash("Place names can be up to 80 characters.", "danger")
        return None
    return name


def create_place(name, parent):
    place = Location(family_id=current_family_id(), parent=parent)
    place.set_name(name)
    db.session.add(place)
    db.session.commit()
    g.pop("family_places", None)
    return place


# --- Pages -----------------------------------------------------------------

@bp.route("/places")
@family_required
def index():
    roots, _ = build_tree()
    return render_template("places/index.html", roots=roots, choices=place_choices(),
                           open_ids=set(request.args.getlist("open", type=int)))


@bp.route("/places/add", methods=["POST"])
@family_required
def add():
    _require_post_form()
    parent = _parent_from_form()
    name = _name_from_form()
    if request.form.get("from") == "tree":
        # Added from the Places tab: go back there with the new place's branch open.
        opened = ([p.id for p in ancestors(parent)] + [parent.id]) if parent else []
        back = url_for(".index", open=opened) + "#add-place"
    else:
        back = url_for(".show", place_id=parent.id) if parent else url_for(".index")
    if name is None:
        return redirect(back)
    if _sibling_with_name(name, parent.id if parent else None):
        where = f"in {parent.name}" if parent else "at the top level"
        flash(f"There's already a place called {name} {where}.", "danger")
        return redirect(back)
    place = create_place(name, parent)
    flash(f"Added {place_path(place, short=False)}.", "success")
    return redirect(back)


@bp.route("/places/<int:place_id>")
@family_required
def show(place_id):
    place = get_for_family_or_404(Location, place_id)
    _, nodes = build_tree()
    node = nodes[place.id]
    rows = db.session.scalars(
        select(Stock).where(Stock.location_id == place.id).join(Stock.item).order_by(Item.name_key)
        .options(selectinload(Stock.item).selectinload(Item.list_entry))
    ).all()
    item_names = db.session.scalars(
        select(Item.name).where(Item.family_id == current_family_id()).order_by(Item.name_key)).all()
    return render_template(
        "places/show.html", place=place, node=node, trail=ancestors(place), rows=rows,
        item_names=item_names, move_choices=place_choices(exclude=place),
        out=sum(1 for r in rows if r.quantity <= 0))


@bp.route("/places/<int:place_id>/rename", methods=["POST"])
@family_required
def rename(place_id):
    _require_post_form()
    place = get_for_family_or_404(Location, place_id)
    name = _name_from_form()
    if name and _sibling_with_name(name, place.parent_id, exclude_id=place.id):
        flash(f"There's already a place called {name} there.", "danger")
    elif name:
        place.set_name(name)
        try:
            db.session.commit()
            flash(f"Renamed to {name}.", "success")
        except IntegrityError:
            db.session.rollback()
            flash(f"There's already a place called {name} there.", "danger")
    return redirect(url_for(".show", place_id=place.id))


@bp.route("/places/<int:place_id>/move", methods=["POST"])
@family_required
def move(place_id):
    _require_post_form()
    place = get_for_family_or_404(Location, place_id)
    parent = _parent_from_form()
    if parent is not None and parent.id in descendants_and_self(place):
        flash("A place can't go inside itself.", "danger")
    elif _sibling_with_name(place.name, parent.id if parent else None, exclude_id=place.id):
        flash(f"There's already a place called {place.name} there.", "danger")
    else:
        place.parent = parent
        db.session.commit()
        g.pop("family_places", None)
        flash(f"Moved to {place_path(place, short=False)}.", "success")
    return redirect(url_for(".show", place_id=place.id))


@bp.route("/places/<int:place_id>/delete", methods=["POST"])
@family_required
def delete(place_id):
    _require_post_form()
    place = get_for_family_or_404(Location, place_id)
    if place.children:
        flash(f"{place.name} has places inside it. Move or delete those first.", "danger")
        return redirect(url_for(".show", place_id=place.id))
    parent_id, name = place.parent_id, place.name
    db.session.delete(place)  # its stock rows go with it (the confirmation says so)
    db.session.commit()
    flash(f"Deleted {name}.", "info")
    return redirect(url_for(".show", place_id=parent_id) if parent_id else url_for(".index"))


# Old addresses from before places were a tree.
@bp.route("/locations")
@bp.route("/inventory")
def old_locations():
    return redirect(url_for(".index"))
