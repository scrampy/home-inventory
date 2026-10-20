"""One family can never reach another family's rows, whatever IDs it tries.

Every route that takes an ID is listed in CASES. test_every_id_route_is_covered
fails when a new ID-taking route is added without a case here.
"""

import pytest
from werkzeug.routing import IntegerConverter
from sqlalchemy import select

from helpers import invite, signup, user
from homeinv.extensions import db
from homeinv.models import Aisle, Family, Invitation, Item, ListEntry, Location, Membership, Price, Stock, Store


@pytest.fixture
def two_families(client, new_client):
    """Ann's family (the attacker, logged in on `client`) and Eve's family with one of everything."""
    signup(client, "ann@example.com", family_name="Ann's")
    eve = new_client()
    signup(eve, "eve@example.com", family_name="Eve's")
    eve.post("/places/add", data={"name": "Eve home"})
    eve_home = db.session.scalar(select(Location.id).filter_by(name="Eve home"))
    eve.post("/places/add", data={"name": "Eve pantry", "parent_id": str(eve_home)})
    eve.post("/stores", data={"name": "Eve store"})
    eve.post("/aisles", data={"name": "Eve aisle"})
    eve.post("/aisles", data={"name": "Eve aisle 2"})
    eve.post("/items", data={"name": "Eve item"})
    eve_loc = db.session.scalar(select(Location.id).filter_by(name="Eve pantry"))
    eve.post("/inventory/add", data={"location_id": eve_loc, "name": "Eve item"})
    eve.post("/list/add", data={"name": "Eve item"})
    eve_item = db.session.scalar(select(Item.id).filter_by(name="Eve item"))
    eve.post(f"/items/{eve_item}/prices", data={"price": "4.99"})
    invite(eve, "friend@example.com")
    # Ann's own rows, to mix with Eve's IDs.
    client.post("/stores", data={"name": "Ann store"})
    client.post("/items", data={"name": "Ann item"})
    family = db.session.get(Family, user("eve@example.com").memberships[0].family_id)
    return {
        "family": family.id,
        "membership": user("eve@example.com").memberships[0].id,
        "invitation": db.session.scalar(select(Invitation.id)),
        "location": db.session.scalar(select(Location.id).filter_by(name="Eve pantry")),
        "store": db.session.scalar(select(Store.id).filter_by(name="Eve store")),
        "aisle": db.session.scalar(select(Aisle.id).filter_by(name="Eve aisle")),
        "item": db.session.scalar(select(Item.id).filter_by(name="Eve item")),
        "stock": db.session.scalar(select(Stock.id)),
        "entry": db.session.scalar(select(ListEntry.id)),
        "price": db.session.scalar(select(Price.id)),
        "ann_store": db.session.scalar(select(Store.id).filter_by(name="Ann store")),
        "ann_item": db.session.scalar(select(Item.id).filter_by(name="Ann item")),
    }


# endpoint -> list of (method, url template, form data)
CASES = {
    "family.change_role": [("POST", "/family/members/{membership}/role", {"role": "member"})],
    "family.remove_member": [("POST", "/family/members/{membership}/remove", {})],
    "family.revoke_invitation": [("POST", "/family/invitations/{invitation}/revoke", {})],
    "family.switch": [("POST", "/family/switch/{family}", {})],
    "catalog.rename": [
        ("POST", "/stores/{store}/rename", {"name": "Hacked"}),
        ("POST", "/aisles/{aisle}/rename", {"name": "Hacked"}),
    ],
    "catalog.delete": [
        ("POST", "/stores/{store}/delete", {}),
        ("POST", "/aisles/{aisle}/delete", {}),
    ],
    "catalog.move": [("POST", "/aisles/{aisle}/move", {"direction": "down"})],
    "catalog.item": [("GET", "/items/{item}", {})],
    "catalog.item_edit": [
        ("GET", "/items/{item}/edit", {}),
        ("POST", "/items/{item}/edit", {"name": "Hacked", "aisle_id": "0"}),
    ],
    "catalog.item_delete": [("POST", "/items/{item}/delete", {})],
    "catalog.toggle_store": [
        ("POST", "/items/{item}/stores/{ann_store}", {}),   # Eve's item, Ann's store
        ("POST", "/items/{ann_item}/stores/{store}", {}),   # Ann's item, Eve's store
    ],
    "places.show": [("GET", "/places/{location}", {})],
    "places.rename": [("POST", "/places/{location}/rename", {"name": "Hacked"})],
    "places.move": [("POST", "/places/{location}/move", {"parent_id": ""})],
    "places.delete": [("POST", "/places/{location}/delete", {})],
    "shopping.toggle_item": [("POST", "/list/items/{item}/toggle", {})],
    "shopping.toggle_cart": [("POST", "/list/{entry}/cart", {})],
    "shopping.quantity": [("POST", "/list/{entry}/quantity", {"delta": "1"})],
    "shopping.remove": [("POST", "/list/{entry}/remove", {})],
    "prices.add": [
        ("POST", "/items/{item}/prices", {"price": "0.01"}),                              # Eve's item
        ("POST", "/items/{ann_item}/prices", {"price": "0.01", "store_id": "{store}"}),   # Eve's store in the form
    ],
    "prices.delete": [("POST", "/prices/{price}/delete", {})],
    "inventory.adjust": [("POST", "/inventory/{stock}/adjust", {"delta": "1"})],
    "inventory.set_quantity": [("POST", "/inventory/{stock}/set", {"quantity": "99"})],
    "inventory.delete": [("POST", "/inventory/{stock}/delete", {})],
}


def snapshot():
    """Everything Eve's family has, to prove nothing changed."""
    eve_family = user("eve@example.com").memberships[0].family
    rows = {}
    for model in (Location, Store, Aisle, Item):
        rows[model.__name__] = sorted(r.name for r in db.session.scalars(
            select(model).filter_by(family_id=eve_family.id)))
    rows["stock"] = sorted((s.item.name, s.location.name, s.quantity) for s in db.session.scalars(
        select(Stock).filter_by(family_id=eve_family.id)))
    rows["places"] = sorted((loc.name, loc.parent_id) for loc in db.session.scalars(
        select(Location).filter_by(family_id=eve_family.id)))
    rows["aisle_order"] = [a.name for a in db.session.scalars(
        select(Aisle).filter_by(family_id=eve_family.id).order_by(Aisle.position))]
    rows["list"] = sorted((e.item.name, e.quantity, e.in_cart) for e in db.session.scalars(
        select(ListEntry).filter_by(family_id=eve_family.id)))
    rows["item_stores"] = sorted((i.name, tuple(s.name for s in i.stores)) for i in db.session.scalars(
        select(Item)))
    rows["prices"] = sorted((pr.item.name, pr.cents) for pr in db.session.scalars(
        select(Price).filter_by(family_id=eve_family.id)))
    rows["all_prices"] = db.session.query(Price).count()
    rows["family"] = eve_family.name
    rows["members"] = sorted((m.user.email, m.role) for m in eve_family.memberships)
    rows["invites"] = [(i.email, i.revoked_at) for i in eve_family.invitations]
    return rows


@pytest.mark.parametrize("endpoint", sorted(CASES))
def test_other_familys_ids_are_not_found(client, two_families, endpoint):
    # Ann is an admin of her own family, so any refusal is about Eve's data, not Ann's role.
    before = snapshot()
    for method, template, data in CASES[endpoint]:
        url = template.format(**two_families)
        data = {k: (v.format(**two_families) if isinstance(v, str) else v) for k, v in data.items()}
        resp = client.open(url, method=method, data=data)
        assert resp.status_code == 404, f"{method} {url} returned {resp.status_code}"
    assert snapshot() == before


def test_cannot_use_other_familys_place_in_forms(client, two_families):
    """IDs inside form fields (not the URL) are checked too."""
    before = snapshot()
    eve_place = str(two_families["location"])
    assert client.post("/inventory/add", data={"location_id": eve_place, "name": "Sneaky"}).status_code == 404
    assert client.post("/places/add", data={"name": "Sneaky", "parent_id": eve_place}).status_code == 404
    client.post("/places/add", data={"name": "Ann home"})
    ann_home = db.session.scalar(select(Location.id).filter_by(name="Ann home"))
    assert client.post(f"/places/{ann_home}/move", data={"parent_id": eve_place}).status_code == 404

    # Put-away into Eve's place.
    client.post("/list/add", data={"name": "Ann item"})
    entry = db.session.scalar(select(ListEntry).join(ListEntry.item).where(Item.name == "Ann item"))
    client.post(f"/list/{entry.id}/cart")
    assert client.post("/list/done", data={"action": "put_away", f"place_{entry.id}": eve_place}).status_code == 404
    assert snapshot() == before


def test_ann_still_sees_only_her_own_rows(client, two_families):
    eve_names = [b"Eve home", b"Eve pantry", b"Eve store", b"Eve aisle", b"Eve item", b"Eve&#39;s", b"eve@example.com"]
    for path in ("/", "/?q=eve", "/places", "/list", "/list/done", "/more", "/items", "/stores", "/aisles", "/family"):
        page = client.get(path).data
        assert not [n for n in eve_names if n in page], path


def test_every_id_route_is_covered(app):
    id_routes = {rule.endpoint for rule in app.url_map.iter_rules()
                 if any(isinstance(c, IntegerConverter) for c in rule._converters.values())}
    assert len(id_routes) >= len(CASES)  # the check itself finds the routes
    missing = id_routes - set(CASES)
    assert not missing, f"Add isolation cases for: {sorted(missing)}"
