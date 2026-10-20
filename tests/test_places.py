"""Places as a tree, and the stock kept in them."""

import re

from sqlalchemy import select

from helpers import signup
from homeinv.extensions import db
from homeinv.models import Item, Location, Stock

FETCH = {"X-Requested-With": "fetch"}


def add_place(client, name, parent=None, **kw):
    data = {"name": name, "parent_id": str(parent) if parent else ""}
    return client.post("/places/add", data=data, follow_redirects=True, **kw)


def place(name, parent_name=None):
    query = select(Location).filter_by(name=name)
    rows = db.session.scalars(query).all()
    if parent_name is not None:
        rows = [r for r in rows if r.parent and r.parent.name == parent_name]
    assert len(rows) == 1, (name, parent_name, rows)
    return rows[0]


def put(client, place_obj, item_name):
    return client.post("/inventory/add", data={"location_id": place_obj.id, "name": item_name}, follow_redirects=True)


def stock(item_name, place_obj):
    return db.session.scalar(select(Stock).join(Stock.item)
                             .where(Item.name == item_name, Stock.location_id == place_obj.id))


def make_home(client):
    """Home › Kitchen › {Fridge, Freezer} and Home › Basement › Freezer."""
    signup(client, "ann@example.com")
    add_place(client, "Home")
    home = place("Home")
    add_place(client, "Kitchen", home.id)
    add_place(client, "Basement", home.id)
    add_place(client, "Fridge", place("Kitchen").id)
    add_place(client, "Freezer", place("Kitchen").id)
    add_place(client, "Freezer", place("Basement").id)  # same name, different parent: fine
    return {"home": home, "kitchen": place("Kitchen"), "basement": place("Basement"),
            "fridge": place("Fridge"), "kfreezer": place("Freezer", "Kitchen"), "bfreezer": place("Freezer", "Basement")}


def rows_shown(client, place_obj):
    page = client.get(f"/places/{place_obj.id}").data.decode()
    return re.findall(r'data-testid="stock">.*?<span class="row-title">([^<]+)</span>', page, re.S)


# --- The tree --------------------------------------------------------------

def test_tree_with_rolled_up_counts(client):
    p = make_home(client)
    put(client, p["bfreezer"], "Burgers")
    put(client, p["bfreezer"], "Pizza")
    put(client, p["kfreezer"], "Peas")
    client.post(f"/inventory/{stock('Burgers', p['bfreezer']).id}/set", data={"quantity": "0"})

    page = client.get("/places").data.decode()
    counts = dict(re.findall(r'<span class="tree-name[^"]*">([^<]+)</span>.*?aria-label="(\d+) items"', page, re.S))
    assert counts["Home"] == "3" and counts["Basement"] == "2" and counts["Kitchen"] == "1"
    assert "1 out" in page  # Burgers, rolled up


def test_sibling_names_must_differ(client):
    p = make_home(client)
    resp = add_place(client, "freezer", p["kitchen"].id)
    assert b"already a place called freezer in Kitchen" in resp.data
    resp = add_place(client, "HOME")
    assert b"already a place called HOME at the top level" in resp.data


def test_place_page_breadcrumb_children_and_paths(client):
    p = make_home(client)
    put(client, p["bfreezer"], "Burgers")
    page = client.get(f"/places/{p['bfreezer'].id}").data.decode()
    assert ">Home</a>" in page and ">Basement</a>" in page
    assert rows_shown(client, p["bfreezer"]) == ["Burgers"]

    page = client.get(f"/places/{p['basement'].id}").data.decode()
    assert 'data-testid="children"' in page and "1 more inside" in page

    # With a single top-level place, paths leave it out: "Basement › Freezer".
    burgers = db.session.scalar(select(Item).filter_by(name="Burgers"))
    assert "Basement › Freezer" in client.get(f"/items/{burgers.id}").data.decode()


def test_rename_move_and_cycles(client):
    p = make_home(client)
    client.post(f"/places/{p['fridge'].id}/rename", data={"name": "Big fridge"})
    assert db.session.get(Location, p["fridge"].id).name == "Big fridge"

    client.post(f"/places/{p['fridge'].id}/move", data={"parent_id": str(p["basement"].id)})
    assert db.session.get(Location, p["fridge"].id).parent_id == p["basement"].id

    # Can't move Home inside its own descendant.
    resp = client.post(f"/places/{p['home'].id}/move", data={"parent_id": str(p["kfreezer"].id)}, follow_redirects=True)
    assert b"can&#39;t go inside itself" in resp.data
    assert db.session.get(Location, p["home"].id).parent_id is None

    # Moving into a parent that already has a place with that name is refused.
    resp = client.post(f"/places/{p['kfreezer'].id}/move", data={"parent_id": str(p["basement"].id)}, follow_redirects=True)
    assert b"already a place called Freezer there" in resp.data


def test_delete_rules(client):
    p = make_home(client)
    put(client, p["bfreezer"], "Burgers")
    resp = client.post(f"/places/{p['basement'].id}/delete", follow_redirects=True)
    assert b"has places inside it" in resp.data
    resp = client.post(f"/places/{p['bfreezer'].id}/delete", follow_redirects=True)
    assert b"Deleted Freezer." in resp.data
    assert db.session.query(Stock).count() == 0  # its stock went with it
    assert db.session.query(Item).count() == 1   # the item stays


def test_old_addresses_redirect(client):
    make_home(client)
    for old in ("/locations", "/inventory"):
        resp = client.get(old)
        assert resp.status_code == 302 and resp.headers["Location"] == "/places"


# --- Stock in a place ------------------------------------------------------

def test_put_creates_item_then_counts_up(client):
    p = make_home(client)
    assert b"Added new item Frozen peas: 1 in Freezer." in put(client, p["kfreezer"], "  Frozen   peas ").data
    assert b"Frozen peas: 2 in Freezer." in put(client, p["kfreezer"], "frozen PEAS").data
    assert db.session.query(Item).count() == 1
    assert b"Enter an item name." in put(client, p["kfreezer"], "  ").data
    assert b"up to 80 characters" in put(client, p["kfreezer"], "x" * 81).data


def test_plus_minus_set_and_floor(client):
    p = make_home(client)
    put(client, p["fridge"], "Milk")
    row = stock("Milk", p["fridge"])
    client.post(f"/inventory/{row.id}/adjust", data={"delta": "1"})
    assert db.session.get(Stock, row.id).quantity == 2
    client.post(f"/inventory/{row.id}/set", data={"quantity": "0.5"})
    client.post(f"/inventory/{row.id}/adjust", data={"delta": "-1"})
    assert db.session.get(Stock, row.id).quantity == 0
    assert client.post(f"/inventory/{row.id}/adjust", data={"delta": "5"}).status_code == 400
    for bad in ("-1", "lots", "", "nan", "1e9"):
        assert b"Use a number, 0 or more." in client.post(
            f"/inventory/{row.id}/set", data={"quantity": bad}, follow_redirects=True).data, bad


def test_in_place_row_and_redirects(client):
    p = make_home(client)
    put(client, p["fridge"], "Milk")
    row = stock("Milk", p["fridge"])
    resp = client.post(f"/inventory/{row.id}/adjust", data={"delta": "1", "view": "location"}, headers=FETCH)
    assert resp.headers["X-Row"] == "1" and resp.data.decode().lstrip().startswith("<li")
    resp = client.post(f"/inventory/{row.id}/adjust", data={"delta": "1"})
    assert resp.headers["Location"] == f"/places/{p['fridge'].id}"
    resp = client.post(f"/inventory/{row.id}/adjust", data={"delta": "1", "next": "https://evil.example/"})
    assert resp.headers["Location"] == f"/places/{p['fridge'].id}"


def test_out_of_stock_row_offers_the_list(client):
    p = make_home(client)
    put(client, p["fridge"], "Milk")
    row = stock("Milk", p["fridge"])
    resp = client.post(f"/inventory/{row.id}/set", data={"quantity": "0", "view": "location"}, headers=FETCH)
    assert b"All gone. Get more?" in resp.data and b"+ List" in resp.data
    # In a row made by a background update, the list button still returns to the place page.
    assert f'name="next" value="/places/{p["fridge"].id}"'.encode() in client.post(
        f"/inventory/{row.id}/adjust", data={"delta": "-1", "view": "location", "next": f"/places/{p['fridge'].id}"},
        headers=FETCH).data
    milk = db.session.scalar(select(Item).filter_by(name="Milk"))
    client.post(f"/list/items/{milk.id}/toggle", data={"next": f"/places/{p['fridge'].id}"})
    assert b"On list" in client.get(f"/places/{p['fridge'].id}").data


def test_item_page_where_kept_and_keep_elsewhere(client):
    p = make_home(client)
    put(client, p["fridge"], "Milk")
    milk = db.session.scalar(select(Item).filter_by(name="Milk"))
    page = client.get(f"/items/{milk.id}").data.decode()
    assert "Where it's kept" in page and "Kitchen › Fridge" in page
    assert f'<option value="{p["fridge"].id}">' not in page  # already kept there
    assert f'<option value="{p["bfreezer"].id}">Home › Basement › Freezer</option>' in page
    client.post("/inventory/add", data={"location_id": p["bfreezer"].id, "name": "Milk"})
    assert stock("Milk", p["bfreezer"]).quantity == 1
    client.post(f"/inventory/{stock('Milk', p['fridge']).id}/delete")
    assert stock("Milk", p["fridge"]) is None
