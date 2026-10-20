import re

from sqlalchemy import select

from helpers import signup, user
from homeinv.extensions import db
from homeinv.models import Aisle, Item, Location, Store, item_store


def add(client, kind, name):
    return client.post(f"/{kind}", data={"name": name}, follow_redirects=True)


def add_item(client, name):
    return client.post("/items", data={"name": name}, follow_redirects=True)


def one(model, name):
    return db.session.scalar(select(model).filter_by(name=name))


def names(model, family_id):
    return sorted(r.name for r in db.session.scalars(select(model).filter_by(family_id=family_id)))


def family_id(email):
    return user(email).memberships[0].family_id


def listed_items(client, query=""):
    """Item names in the order the list page shows them."""
    page = client.get("/items" + query).data.decode()
    return re.findall(r'data-testid="item">\s*<div[^>]*>\s*<span class="fw-medium">([^<]+)<', page)


def edit_item(client, item, **fields):
    data = {"name": item.name, "aisle_id": "0", "default_unit": "", "low_stock_threshold": "", "notes": ""}
    data.update(fields)
    return client.post(f"/items/{item.id}", data=data, follow_redirects=True)


# --- Locations, stores, aisles ---------------------------------------------

def test_add_rename_delete_location(client):
    signup(client, "ann@example.com")
    resp = add(client, "locations", "  Garage   freezer ")
    assert b"Added Garage freezer." in resp.data
    loc = one(Location, "Garage freezer")
    assert loc.name_key == "garage freezer"

    resp = client.post(f"/locations/{loc.id}/rename", data={"name": "Chest freezer"}, follow_redirects=True)
    assert b"Renamed Garage freezer to Chest freezer." in resp.data

    loc_id = loc.id
    resp = client.post(f"/locations/{loc_id}/delete", follow_redirects=True)
    assert b"Deleted Chest freezer." in resp.data
    assert db.session.get(Location, loc_id) is None


def test_names_are_unique_per_family_ignoring_case_and_spaces(client):
    signup(client, "ann@example.com")
    add(client, "stores", "Costco")
    resp = add(client, "stores", " costco ")
    assert b"There&#39;s already a store called costco." in resp.data
    assert names(Store, family_id("ann@example.com")) == ["Costco"]


def test_same_name_allowed_in_different_families(client, new_client):
    signup(client, "ann@example.com")
    eve = new_client()
    signup(eve, "eve@example.com")
    add(client, "stores", "Costco")
    resp = add(eve, "stores", "Costco")
    assert b"Added Costco." in resp.data


def test_rename_to_taken_name_rejected_but_recasing_allowed(client):
    signup(client, "ann@example.com")
    add(client, "aisles", "Dairy")
    add(client, "aisles", "Bakery")
    bakery = one(Aisle, "Bakery")

    resp = client.post(f"/aisles/{bakery.id}/rename", data={"name": "DAIRY"}, follow_redirects=True)
    assert b"already a aisle called DAIRY" in resp.data
    client.post(f"/aisles/{bakery.id}/rename", data={"name": "bakery"})
    assert db.session.get(Aisle, bakery.id).name == "bakery"


def test_blank_names_rejected(client):
    signup(client, "ann@example.com")
    resp = add(client, "locations", "   ")
    assert b"Enter a name." in resp.data
    assert names(Location, family_id("ann@example.com")) == []


def test_suggestions_add_only_missing_ones(client):
    signup(client, "ann@example.com")
    add(client, "locations", "pantry")
    resp = client.get("/locations")
    assert b"Common locations: Refrigerator, Freezer" in resp.data
    client.post("/locations/suggestions")
    assert names(Location, family_id("ann@example.com")) == ["Freezer", "Refrigerator", "pantry"]
    assert b"Add these" not in client.get("/locations").data


def test_unknown_kind_is_404(client):
    signup(client, "ann@example.com")
    assert client.get("/families").status_code == 404
    assert client.post("/items/suggestions").status_code in (404, 405)


def test_deleting_aisle_keeps_its_items(client):
    signup(client, "ann@example.com")
    add(client, "aisles", "Dairy")
    add_item(client, "Milk")
    milk, dairy = one(Item, "Milk"), one(Aisle, "Dairy")
    edit_item(client, milk, aisle_id=str(dairy.id))
    assert b"1 item" in client.get("/aisles").data

    client.post(f"/aisles/{dairy.id}/delete")
    milk = db.session.get(Item, milk.id)
    assert milk is not None and milk.aisle_id is None


def test_deleting_store_unlinks_items(client):
    signup(client, "ann@example.com")
    add(client, "stores", "Costco")
    add_item(client, "Milk")
    milk, costco = one(Item, "Milk"), one(Store, "Costco")
    edit_item(client, milk, store_ids=[str(costco.id)])
    assert b"1 item" in client.get("/stores").data

    client.post(f"/stores/{costco.id}/delete")
    assert db.session.get(Item, milk.id).stores == []
    assert db.session.execute(select(item_store)).all() == []


# --- Items -----------------------------------------------------------------

def test_add_and_list_items(client):
    signup(client, "ann@example.com")
    assert b"Added Milk." in add_item(client, "Milk").data
    assert b"already on the list" in add_item(client, "MILK").data
    add_item(client, "Bread")
    assert listed_items(client) == ["Bread", "Milk"]  # alphabetical


def test_edit_item_details(client):
    signup(client, "ann@example.com")
    for name in ("Costco", "Safeway", "No Frills"):
        add(client, "stores", name)
    add(client, "aisles", "Dairy")
    add_item(client, "Milk")
    milk = one(Item, "Milk")
    costco, safeway = one(Store, "Costco"), one(Store, "Safeway")

    resp = edit_item(client, milk, name="Milk 2%", aisle_id=str(one(Aisle, "Dairy").id),
                     store_ids=[str(costco.id), str(safeway.id)], default_unit=" carton ",
                     low_stock_threshold="1.5", notes="  Organic  ")
    assert b"Saved Milk 2%." in resp.data
    milk = db.session.get(Item, milk.id)
    assert milk.name == "Milk 2%" and milk.aisle.name == "Dairy"
    assert [s.name for s in milk.stores] == ["Costco", "Safeway"]
    assert (milk.default_unit, milk.low_stock_threshold, milk.notes) == ("carton", 1.5, "Organic")

    page = client.get("/items").data
    assert b"Costco, Safeway" in page and b"Dairy" in page

    # Clearing everything again.
    edit_item(client, milk)
    milk = db.session.get(Item, milk.id)
    assert (milk.aisle_id, milk.stores, milk.default_unit, milk.low_stock_threshold, milk.notes) == (
        None, [], None, None, None)


def test_edit_form_shows_current_values(client):
    signup(client, "ann@example.com")
    add(client, "stores", "Costco")
    add(client, "aisles", "Dairy")
    add_item(client, "Milk")
    milk = one(Item, "Milk")
    edit_item(client, milk, aisle_id=str(one(Aisle, "Dairy").id), store_ids=[str(one(Store, "Costco").id)])
    page = client.get(f"/items/{milk.id}").data.decode()
    assert f'<option selected value="{one(Aisle, "Dairy").id}">Dairy</option>' in page
    assert 'value="%d" autocomplete="off" checked' % one(Store, "Costco").id in page


def test_negative_threshold_and_duplicate_rename_rejected(client):
    signup(client, "ann@example.com")
    add_item(client, "Milk")
    add_item(client, "Eggs")
    eggs = one(Item, "Eggs")
    assert b"Use 0 or more." in edit_item(client, eggs, low_stock_threshold="-1").data
    assert b"already on the list" in edit_item(client, eggs, name="milk").data
    assert db.session.get(Item, eggs.id).name == "Eggs"


def test_item_cannot_use_another_familys_aisle_or_store(client, new_client):
    signup(client, "ann@example.com")
    eve = new_client()
    signup(eve, "eve@example.com")
    add(eve, "aisles", "Eve aisle")
    add(eve, "stores", "Eve store")
    add_item(client, "Milk")
    milk = one(Item, "Milk")

    resp = edit_item(client, milk, aisle_id=str(one(Aisle, "Eve aisle").id))
    assert b"Not a valid choice" in resp.data
    resp = edit_item(client, milk, store_ids=[str(one(Store, "Eve store").id)])
    assert b"is not a valid choice" in resp.data
    milk = db.session.get(Item, milk.id)
    assert milk.aisle_id is None and milk.stores == []


def test_search_items(client):
    signup(client, "ann@example.com")
    for name in ("Milk", "Oat milk", "Bread", "100% juice"):
        add_item(client, name)
    assert listed_items(client, "?q=MILK") == ["Milk", "Oat milk"]
    # % is matched literally, not as a wildcard.
    assert listed_items(client, "?q=%25") == ["100% juice"]
    assert b"No items match" in client.get("/items?q=zzz").data


def test_delete_item(client):
    signup(client, "ann@example.com")
    add(client, "stores", "Costco")
    add_item(client, "Milk")
    milk = one(Item, "Milk")
    edit_item(client, milk, store_ids=[str(one(Store, "Costco").id)])
    resp = client.post(f"/items/{milk.id}/delete", follow_redirects=True)
    assert b"Deleted Milk." in resp.data
    assert db.session.execute(select(item_store)).all() == []
    assert one(Store, "Costco") is not None


def test_catalog_follows_the_active_family(client):
    signup(client, "ann@example.com", family_name="Home")
    add_item(client, "Milk")
    client.post("/family/new", data={"name": "Cottage"})
    add_item(client, "Firewood")
    assert listed_items(client) == ["Firewood"]

    home_id = next(m.family_id for m in user("ann@example.com").memberships if m.family.name == "Home")
    client.post(f"/family/switch/{home_id}")
    assert listed_items(client) == ["Milk"]


def test_catalog_requires_a_family(client, new_client, outbox):
    # Someone who left their only family is sent to create one.
    from helpers import invite, link_path
    signup(client, "ann@example.com")
    invite(client, "bob@example.com")
    bob = new_client()
    signup(bob, "bob@example.com", invite=link_path(outbox[0]).split("/")[-1])
    bob.post("/family/leave")
    for path in ("/items", "/locations", "/stores", "/aisles"):
        resp = bob.get(path)
        assert resp.status_code == 302 and "/family/new" in resp.headers["Location"]
