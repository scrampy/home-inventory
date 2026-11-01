"""Tablets: a device set up to look after one place's stock (tablet.py)."""

from sqlalchemy import select

from helpers import login, signup
from homeinv.extensions import db
from homeinv.models import Item, ListEntry, Location, Stock, Tablet

FETCH = {"X-Requested-With": "fetch"}


def places():
    return {p.name: p.id for p in db.session.scalars(select(Location))}


def stock(name, place_id):
    return db.session.scalar(select(Stock).join(Stock.item).where(Item.name == name, Stock.location_id == place_id))


def put(client, place_id, name, quantity):
    client.post("/inventory/add", data={"location_id": place_id, "name": name})
    client.post(f"/inventory/{stock(name, place_id).id}/set", data={"quantity": str(quantity)})


def home(client):
    """Ann's family: Cold Room (with a Top Shelf inside) and a Pantry, with some stock."""
    signup(client, "ann@example.com", name="Ann")
    client.post("/places/add", data={"name": "Cold Room"})
    client.post("/places/add", data={"name": "Pantry"})
    client.post("/places/add", data={"name": "Top Shelf", "parent_id": places()["Cold Room"]})
    ids = places()
    put(client, ids["Cold Room"], "Potatoes", 3)
    put(client, ids["Top Shelf"], "Jam", 2)
    put(client, ids["Pantry"], "Rice", 1)
    return ids


def set_up_tablet(app, place_id):
    """A separate browser (the tablet): Ann signs in on it and sets it up for the place."""
    tablet = app.test_client()
    login(tablet, "ann@example.com")
    resp = tablet.post("/tablet/setup", data={"location_id": place_id})
    assert resp.status_code == 302 and resp.headers["Location"].endswith("/tablet")
    return tablet


def test_setting_up_signs_out_and_shows_the_place(app, client):
    ids = home(client)
    tablet = set_up_tablet(app, ids["Cold Room"])

    cookie = tablet.get_cookie("homeinv_tablet", path="/tablet")
    assert cookie is not None and cookie.http_only and cookie.max_age > 365 * 24 * 3600
    assert db.session.scalar(select(Tablet)).location_id == ids["Cold Room"]

    # Signed out: the main app wants a login. The tablet cookie doesn't count as one.
    assert "/login" in tablet.get("/").headers["Location"]
    assert "/login" in tablet.get(f"/places/{ids['Cold Room']}").headers["Location"]

    body = tablet.get("/tablet").data.decode()
    assert "This tablet now looks after Cold Room." in body
    assert "Potatoes" in body and "Jam" in body and "Top Shelf" in body  # places inside count too
    assert 'data-name="rice"' not in body  # no tile: the Pantry isn't this tablet's (it's only a typing suggestion)


def test_without_setup_it_explains_how(client):
    resp = client.get("/tablet")
    assert resp.status_code == 200 and "isn't set up yet" in resp.data.decode()
    assert resp.headers["Cache-Control"] == "no-store"
    assert client.post("/tablet/add", data={"name": "Milk"}).headers["Location"].endswith("/tablet")


def test_plus_and_minus(app, client):
    ids = home(client)
    tablet = set_up_tablet(app, ids["Cold Room"])
    potatoes = stock("Potatoes", ids["Cold Room"])

    resp = tablet.post(f"/tablet/stock/{potatoes.id}/adjust", data={"delta": "-1"}, headers=FETCH)
    assert resp.headers["X-Tile"] == "1" and 'data-qty>2<' in resp.data.decode()
    tablet.post(f"/tablet/stock/{potatoes.id}/adjust", data={"delta": "1"})
    tablet.post(f"/tablet/stock/{potatoes.id}/adjust", data={"delta": "1"})
    assert stock("Potatoes", ids["Cold Room"]).quantity == 4

    for _ in range(6):
        tablet.post(f"/tablet/stock/{potatoes.id}/adjust", data={"delta": "-1"})
    assert stock("Potatoes", ids["Cold Room"]).quantity == 0  # never below zero

    assert tablet.post(f"/tablet/stock/{potatoes.id}/adjust", data={"delta": "5"}).status_code == 400


def test_only_its_own_places(app, client):
    ids = home(client)
    tablet = set_up_tablet(app, ids["Cold Room"])
    rice = stock("Rice", ids["Pantry"])
    jam = stock("Jam", ids["Top Shelf"])

    assert tablet.post(f"/tablet/stock/{rice.id}/adjust", data={"delta": "1"}).status_code == 404
    assert tablet.post(f"/tablet/stock/{rice.id}/list", data={}).status_code == 404
    assert stock("Rice", ids["Pantry"]).quantity == 1

    tablet.post(f"/tablet/stock/{jam.id}/adjust", data={"delta": "1"})
    assert stock("Jam", ids["Top Shelf"]).quantity == 3


def test_add_puts_one_in_the_tablets_place(app, client):
    ids = home(client)
    tablet = set_up_tablet(app, ids["Cold Room"])

    body = tablet.post("/tablet/add", data={"name": "  carrots "}, follow_redirects=True).data.decode()
    assert "Added new item carrots: 1 in Cold Room." in body
    assert stock("carrots", ids["Cold Room"]).quantity == 1

    tablet.post("/tablet/add", data={"name": "POTATOES"})  # an item the family already has
    assert stock("Potatoes", ids["Cold Room"]).quantity == 4

    tablet.post("/tablet/add", data={"name": "Rice"})  # kept in the Pantry too; now also here
    assert stock("Rice", ids["Cold Room"]).quantity == 1 and stock("Rice", ids["Pantry"]).quantity == 1

    body = tablet.post("/tablet/add", data={"name": "   "}, follow_redirects=True).data.decode()
    assert "Type the name" in body


def test_shopping_list_when_out_and_restock(app, client):
    ids = home(client)
    tablet = set_up_tablet(app, ids["Cold Room"])
    potatoes = stock("Potatoes", ids["Cold Room"])
    for _ in range(3):
        tablet.post(f"/tablet/stock/{potatoes.id}/adjust", data={"delta": "-1"})

    tile = tablet.post(f"/tablet/stock/{potatoes.id}/list", data={}, headers=FETCH).data.decode()
    assert "On the list ✓" in tile
    entry = db.session.scalar(select(ListEntry))
    assert entry.item.name == "Potatoes" and entry.added_by_id is None

    # Putting some back takes it off the list again, as on the place page.
    tile = tablet.post(f"/tablet/stock/{potatoes.id}/adjust", data={"delta": "1"}, headers=FETCH).data.decode()
    assert "Taken off the shopping list" in tile
    assert db.session.scalar(select(ListEntry)) is None


def test_unpair_stops_it(app, client):
    ids = home(client)
    tablet = set_up_tablet(app, ids["Cold Room"])
    paired = db.session.scalar(select(Tablet))

    page = client.get(f"/places/{ids['Cold Room']}").data.decode()
    assert "1 set up" in page and "by Ann" in page

    client.post(f"/tablets/{paired.id}/unpair")
    assert db.session.scalar(select(Tablet)) is None
    assert "isn't set up yet" in tablet.get("/tablet").data.decode()
    potatoes = stock("Potatoes", ids["Cold Room"])
    assert tablet.post(f"/tablet/stock/{potatoes.id}/adjust", data={"delta": "1"}, headers=FETCH).status_code == 401
    assert stock("Potatoes", ids["Cold Room"]).quantity == 3


def test_setting_up_again_replaces_the_old_pairing(app, client):
    ids = home(client)
    tablet = set_up_tablet(app, ids["Cold Room"])
    login(tablet, "ann@example.com")
    tablet.post("/tablet/setup", data={"location_id": ids["Pantry"]})
    assert [t.location_id for t in db.session.scalars(select(Tablet))] == [ids["Pantry"]]
    assert "Rice" in tablet.get("/tablet").data.decode()


def test_deleting_the_place_removes_its_tablet(app, client):
    ids = home(client)
    set_up_tablet(app, ids["Pantry"])
    client.post(f"/places/{ids['Pantry']}/delete")
    assert db.session.scalar(select(Tablet)) is None


def test_other_families_cant_touch_it(app, client, new_client):
    ids = home(client)
    set_up_tablet(app, ids["Cold Room"])
    paired = db.session.scalar(select(Tablet))

    bob = new_client()
    signup(bob, "bob@example.com")
    assert bob.post(f"/tablets/{paired.id}/unpair").status_code == 404
    assert bob.post("/tablet/setup", data={"location_id": ids["Cold Room"]}).status_code == 404
    assert db.session.scalar(select(Tablet)) is not None
