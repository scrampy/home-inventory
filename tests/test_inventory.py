import re

from sqlalchemy import select

from helpers import signup
from homeinv.extensions import db
from homeinv.models import Item, Location, Stock

FETCH = {"X-Requested-With": "fetch"}


def setup_family(client, *locations):
    signup(client, "ann@example.com")
    for name in locations or ("Pantry", "Freezer"):
        client.post("/locations", data={"name": name})
    return {loc.name: loc.id for loc in db.session.scalars(select(Location))}


def add(client, location_id, name, **extra):
    return client.post("/inventory/add", data={"location_id": location_id, "name": name, **extra},
                       follow_redirects=True)


def stock(item_name, location_name):
    return db.session.scalar(select(Stock).join(Stock.item).join(Stock.location)
                             .where(Item.name == item_name, Location.name == location_name))


def rows_shown(client, query=""):
    """Item names of the stock rows on an inventory page."""
    page = client.get("/inventory" + query).data.decode()
    return re.findall(r'data-testid="stock">.*?<a class="fw-medium[^>]*>([^<]+)</a>', page, re.S)


def test_home_is_inventory(client):
    setup_family(client)
    resp = client.get("/")
    assert resp.status_code == 302 and resp.headers["Location"] == "/inventory"


def test_add_creates_item_and_then_counts_up(client):
    locs = setup_family(client)
    resp = add(client, locs["Freezer"], "  Frozen   peas ")
    assert b"Added new item Frozen peas: 1 in Freezer." in resp.data
    assert stock("Frozen peas", "Freezer").quantity == 1

    resp = add(client, locs["Freezer"], "frozen PEAS")  # same item, any case
    assert b"Frozen peas: 2 in Freezer." in resp.data
    assert db.session.query(Item).count() == 1


def test_add_existing_item_to_second_location(client):
    locs = setup_family(client)
    client.post("/items", data={"name": "Rice"})
    add(client, locs["Pantry"], "Rice")
    add(client, locs["Freezer"], "Rice")
    assert stock("Rice", "Pantry").quantity == 1 and stock("Rice", "Freezer").quantity == 1


def test_add_validation(client):
    locs = setup_family(client)
    assert b"Enter an item name." in add(client, locs["Pantry"], "   ").data
    assert b"Choose a location." in client.post("/inventory/add", data={"name": "Rice"}, follow_redirects=True).data
    assert b"up to 80 characters" in add(client, locs["Pantry"], "x" * 81).data
    assert db.session.query(Stock).count() == 0


def test_plus_minus_and_floor_at_zero(client):
    locs = setup_family(client)
    add(client, locs["Pantry"], "Rice")
    row = stock("Rice", "Pantry")
    client.post(f"/inventory/{row.id}/adjust", data={"delta": "1"})
    assert db.session.get(Stock, row.id).quantity == 2
    for _ in range(3):
        client.post(f"/inventory/{row.id}/adjust", data={"delta": "-1"})
    assert db.session.get(Stock, row.id).quantity == 0
    assert client.post(f"/inventory/{row.id}/adjust", data={"delta": "5"}).status_code == 400


def test_minus_from_a_half_goes_to_zero(client):
    locs = setup_family(client)
    add(client, locs["Pantry"], "Rice")
    row = stock("Rice", "Pantry")
    client.post(f"/inventory/{row.id}/set", data={"quantity": "0.5"})
    client.post(f"/inventory/{row.id}/adjust", data={"delta": "-1"})
    assert db.session.get(Stock, row.id).quantity == 0


def test_set_exact_quantity(client):
    locs = setup_family(client)
    add(client, locs["Pantry"], "Rice")
    row = stock("Rice", "Pantry")
    client.post(f"/inventory/{row.id}/set", data={"quantity": "2.5"})
    assert db.session.get(Stock, row.id).quantity == 2.5
    for bad in ("-1", "lots", "", "nan", "1e9"):
        resp = client.post(f"/inventory/{row.id}/set", data={"quantity": bad}, follow_redirects=True)
        assert b"Use a number, 0 or more." in resp.data, bad
    assert db.session.get(Stock, row.id).quantity == 2.5


def test_in_place_updates_return_just_the_row(client):
    locs = setup_family(client)
    add(client, locs["Pantry"], "Rice")
    row = stock("Rice", "Pantry")

    resp = client.post(f"/inventory/{row.id}/adjust", data={"delta": "1", "view": "location"}, headers=FETCH)
    assert resp.status_code == 200 and resp.headers["X-Row"] == "1"
    body = resp.data.decode()
    assert body.lstrip().startswith("<li") and 'value="2"' in body and "<html" not in body

    resp = client.post(f"/inventory/{row.id}/set", data={"quantity": "-3"}, headers=FETCH)
    assert resp.status_code == 400 and resp.headers["X-Row"] == "1"
    assert b"Use a number, 0 or more." in resp.data


def test_without_javascript_changes_redirect_back(client):
    locs = setup_family(client)
    add(client, locs["Pantry"], "Rice")
    row = stock("Rice", "Pantry")
    resp = client.post(f"/inventory/{row.id}/adjust", data={"delta": "1", "next": "/inventory?location=1"})
    assert resp.status_code == 302 and resp.headers["Location"] == "/inventory?location=1"
    # `next` never leaves the site.
    resp = client.post(f"/inventory/{row.id}/adjust", data={"delta": "1", "next": "https://evil.example/"})
    assert resp.headers["Location"] == f"/inventory?location={row.location_id}"


def test_location_view_and_totals_across_locations(client):
    locs = setup_family(client)
    add(client, locs["Pantry"], "Rice")
    add(client, locs["Freezer"], "Rice")
    add(client, locs["Freezer"], "Peas")
    client.post(f"/inventory/{stock('Rice', 'Freezer').id}/set", data={"quantity": "1.5"})
    client.post(f"/inventory/{stock('Peas', 'Freezer').id}/set", data={"quantity": "0"})

    assert rows_shown(client, f"?location={locs['Pantry']}") == ["Rice"]

    page = client.get("/inventory").data.decode()
    assert "Freezer 1.5 · Pantry 1" in page or "Pantry 1 · Freezer 1.5" in page
    assert ">2.5<" in page  # Rice total
    assert "Out" in page  # Peas


def test_low_stock_badge_uses_item_threshold(client):
    locs = setup_family(client)
    add(client, locs["Pantry"], "Rice")
    rice = db.session.scalar(select(Item).filter_by(name="Rice"))
    client.post(f"/items/{rice.id}", data={"name": "Rice", "aisle_id": "0", "low_stock_threshold": "1"})
    assert b">Low<" in client.get("/inventory").data
    client.post(f"/inventory/{stock('Rice', 'Pantry').id}/adjust", data={"delta": "1"})
    assert b">Low<" not in client.get("/inventory").data


def test_stop_keeping_item_somewhere(client):
    locs = setup_family(client)
    add(client, locs["Pantry"], "Rice")
    row = stock("Rice", "Pantry")
    resp = client.post(f"/inventory/{row.id}/delete", follow_redirects=True)
    assert b"Rice is no longer kept in Pantry." in resp.data
    assert db.session.query(Stock).count() == 0
    assert db.session.query(Item).count() == 1  # the item itself stays


def test_item_page_shows_and_adds_stock(client):
    locs = setup_family(client)
    add(client, locs["Pantry"], "Rice")
    rice = db.session.scalar(select(Item).filter_by(name="Rice"))
    page = client.get(f"/items/{rice.id}").data.decode()
    assert "Where it's kept" in page and "Total: <strong>1</strong>" in page
    assert '<option value="%d">Freezer</option>' % locs["Freezer"] in page  # can add to Freezer
    assert '<option value="%d">Pantry</option>' % locs["Pantry"] not in page  # already kept there

    client.post("/inventory/add", data={"location_id": locs["Freezer"], "name": "Rice",
                                        "next": f"/items/{rice.id}"})
    assert stock("Rice", "Freezer").quantity == 1


def test_deleting_location_or_item_removes_its_stock(client):
    locs = setup_family(client)
    add(client, locs["Pantry"], "Rice")
    add(client, locs["Freezer"], "Rice")
    add(client, locs["Freezer"], "Peas")
    assert b"2 items" in client.get("/locations").data  # Freezer

    client.post(f"/locations/{locs['Freezer']}/delete")
    assert [(s.item.name, s.location.name) for s in db.session.scalars(select(Stock))] == [("Rice", "Pantry")]

    rice = db.session.scalar(select(Item).filter_by(name="Rice"))
    client.post(f"/items/{rice.id}/delete")
    assert db.session.query(Stock).count() == 0


def test_inventory_without_locations_points_to_setup(client):
    signup(client, "ann@example.com")
    assert b"Add locations" in client.get("/inventory").data
