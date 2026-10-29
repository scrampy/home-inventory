"""When an item comes back into stock, it comes off the shopping list.

The rule: the item's total across all places goes from zero to more than zero,
and its list entry is still "to get" (not ticked into the cart).
"""

from sqlalchemy import select

from helpers import signup
from homeinv.extensions import db
from homeinv.models import Item, ListEntry, Location, Stock

FETCH = {"X-Requested-With": "fetch"}


def setup(client):
    signup(client, "ann@example.com")
    for name in ("Freezer", "Pantry"):
        client.post("/places/add", data={"name": name})
    return {p.name: p.id for p in db.session.scalars(select(Location))}


def put(client, place_id, name, quantity=None):
    resp = client.post("/inventory/add", data={"location_id": place_id, "name": name}, follow_redirects=True)
    if quantity is not None:
        s = stock(name, place_id)
        client.post(f"/inventory/{s.id}/set", data={"quantity": str(quantity)})
    return resp


def stock(name, place_id):
    return db.session.scalar(select(Stock).join(Stock.item).where(Item.name == name, Stock.location_id == place_id))


def on_list(name):
    entry = db.session.scalar(select(ListEntry).join(ListEntry.item).where(Item.name == name))
    return None if entry is None else ("cart" if entry.in_cart else "to get")


def add_to_list(client, name):
    client.post("/list/add", data={"name": name})


def test_plus_from_zero_takes_it_off_the_list(client):
    places = setup(client)
    put(client, places["Freezer"], "Burgers", 0)
    add_to_list(client, "Burgers")
    row = stock("Burgers", places["Freezer"])

    resp = client.post(f"/inventory/{row.id}/adjust", data={"delta": "1", "view": "location",
                                                            "next": f"/places/{places['Freezer']}"}, headers=FETCH)
    assert on_list("Burgers") is None
    body = resp.data.decode()
    assert "Taken off the shopping list." in body and "Undo" in body
    assert resp.headers["X-List-Count"] == "0"  # for the List tab's badge

    # Undo puts it back.
    burgers = db.session.scalar(select(Item).filter_by(name="Burgers"))
    client.post(f"/list/items/{burgers.id}/toggle", data={"next": f"/places/{places['Freezer']}"})
    assert on_list("Burgers") == "to get"
    # ...and the next + doesn't take it off again: it wasn't at zero any more.
    client.post(f"/inventory/{row.id}/adjust", data={"delta": "1"})
    assert on_list("Burgers") == "to get"


def test_typing_a_quantity_from_zero_takes_it_off(client):
    places = setup(client)
    put(client, places["Freezer"], "Peas", 0)
    add_to_list(client, "Peas")
    client.post(f"/inventory/{stock('Peas', places['Freezer']).id}/set", data={"quantity": "0.5"})
    assert on_list("Peas") is None


def test_putting_something_in_a_place_takes_it_off(client):
    places = setup(client)
    add_to_list(client, "Batteries")  # never counted anywhere: total is zero
    resp = put(client, places["Pantry"], "Batteries")
    assert on_list("Batteries") is None
    assert b"Took Batteries off the shopping list: you have some now." in resp.data


def test_without_javascript_says_so(client):
    places = setup(client)
    put(client, places["Freezer"], "Burgers", 0)
    add_to_list(client, "Burgers")
    resp = client.post(f"/inventory/{stock('Burgers', places['Freezer']).id}/adjust", data={"delta": "1"},
                       follow_redirects=True)
    assert b"Took Burgers off the shopping list: you have some now." in resp.data


def test_stays_on_list_when_there_was_some_elsewhere(client):
    """Moving one from the freezer to the pantry isn't 'restocking': you wanted more."""
    places = setup(client)
    put(client, places["Freezer"], "Rice", 3)
    put(client, places["Pantry"], "Rice", 0)
    add_to_list(client, "Rice")
    client.post(f"/inventory/{stock('Rice', places['Pantry']).id}/adjust", data={"delta": "1"})
    assert on_list("Rice") == "to get"
    put(client, places["Pantry"], "Rice")
    assert on_list("Rice") == "to get"


def test_items_in_the_cart_are_left_for_done_shopping(client):
    places = setup(client)
    put(client, places["Freezer"], "Burgers", 0)
    add_to_list(client, "Burgers")
    entry = db.session.scalar(select(ListEntry))
    client.post(f"/list/{entry.id}/cart")
    client.post(f"/inventory/{stock('Burgers', places['Freezer']).id}/adjust", data={"delta": "1"})
    assert on_list("Burgers") == "cart"


def test_going_down_never_removes(client):
    places = setup(client)
    put(client, places["Freezer"], "Burgers", 2)
    add_to_list(client, "Burgers")
    row = stock("Burgers", places["Freezer"])
    for _ in range(3):
        client.post(f"/inventory/{row.id}/adjust", data={"delta": "-1"})
    client.post(f"/inventory/{row.id}/set", data={"quantity": "0"})
    assert on_list("Burgers") == "to get"
    resp = client.post(f"/inventory/{row.id}/adjust", data={"delta": "1", "view": "location"}, headers=FETCH)
    assert on_list("Burgers") is None  # back from zero
    assert b"Taken off the shopping list." in resp.data


def test_other_items_on_the_list_are_untouched(client):
    places = setup(client)
    put(client, places["Freezer"], "Burgers", 0)
    add_to_list(client, "Burgers")
    add_to_list(client, "Milk")
    client.post(f"/inventory/{stock('Burgers', places['Freezer']).id}/adjust", data={"delta": "1"})
    assert on_list("Burgers") is None and on_list("Milk") == "to get"
