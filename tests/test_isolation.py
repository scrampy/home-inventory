"""One family can never reach another family's rows, whatever IDs it tries.

Every route that takes an ID is listed in CASES. test_every_id_route_is_covered
fails when a new ID-taking route is added without a case here.
"""

import pytest
from werkzeug.routing import IntegerConverter
from sqlalchemy import select

from helpers import invite, signup, user
from homeinv.extensions import db
from homeinv.models import Aisle, Family, Invitation, Item, Location, Membership, Stock, Store


@pytest.fixture
def two_families(client, new_client):
    """Ann's family (the attacker, logged in on `client`) and Eve's family with one of everything."""
    signup(client, "ann@example.com", family_name="Ann's")
    eve = new_client()
    signup(eve, "eve@example.com", family_name="Eve's")
    eve.post("/locations", data={"name": "Eve pantry"})
    eve.post("/stores", data={"name": "Eve store"})
    eve.post("/aisles", data={"name": "Eve aisle"})
    eve.post("/items", data={"name": "Eve item"})
    eve_loc = db.session.scalar(select(Location.id).filter_by(name="Eve pantry"))
    eve.post("/inventory/add", data={"location_id": eve_loc, "name": "Eve item"})
    invite(eve, "friend@example.com")
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
    }


# endpoint -> list of (method, url template, form data)
CASES = {
    "family.change_role": [("POST", "/family/members/{membership}/role", {"role": "member"})],
    "family.remove_member": [("POST", "/family/members/{membership}/remove", {})],
    "family.revoke_invitation": [("POST", "/family/invitations/{invitation}/revoke", {})],
    "family.switch": [("POST", "/family/switch/{family}", {})],
    "catalog.rename": [
        ("POST", "/locations/{location}/rename", {"name": "Hacked"}),
        ("POST", "/stores/{store}/rename", {"name": "Hacked"}),
        ("POST", "/aisles/{aisle}/rename", {"name": "Hacked"}),
    ],
    "catalog.delete": [
        ("POST", "/locations/{location}/delete", {}),
        ("POST", "/stores/{store}/delete", {}),
        ("POST", "/aisles/{aisle}/delete", {}),
    ],
    "catalog.item_edit": [
        ("GET", "/items/{item}", {}),
        ("POST", "/items/{item}", {"name": "Hacked", "aisle_id": "0"}),
    ],
    "catalog.item_delete": [("POST", "/items/{item}/delete", {})],
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
        resp = client.open(url, method=method, data=data)
        assert resp.status_code == 404, f"{method} {url} returned {resp.status_code}"
    assert snapshot() == before


def test_cannot_add_stock_to_other_familys_location(client, two_families):
    before = snapshot()
    resp = client.post("/inventory/add", data={"location_id": two_families["location"], "name": "Sneaky"})
    assert resp.status_code == 404
    assert client.get(f"/inventory?location={two_families['location']}").status_code == 404
    assert snapshot() == before


def test_ann_still_sees_only_her_own_rows(client, two_families):
    eve_names = [b"Eve pantry", b"Eve store", b"Eve aisle", b"Eve item", b"Eve&#39;s", b"eve@example.com"]
    for path in ("/inventory", "/items", "/locations", "/stores", "/aisles", "/family"):
        page = client.get(path).data
        assert not [n for n in eve_names if n in page], path


def test_every_id_route_is_covered(app):
    id_routes = {rule.endpoint for rule in app.url_map.iter_rules()
                 if any(isinstance(c, IntegerConverter) for c in rule._converters.values())}
    assert len(id_routes) >= len(CASES)  # the check itself finds the routes
    missing = id_routes - set(CASES)
    assert not missing, f"Add isolation cases for: {sorted(missing)}"
