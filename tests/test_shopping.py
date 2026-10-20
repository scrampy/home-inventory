"""Find, and the shopping list with store mode and put-away."""

import re

from sqlalchemy import select

from helpers import signup
from homeinv.extensions import db
from homeinv.models import Aisle, Item, ListEntry, Location, Stock, Store


def setup(client):
    """Ann's family: Home › Fridge and Home › Freezer, two stores, aisles, and some items."""
    signup(client, "ann@example.com")
    client.post("/places/add", data={"name": "Home"})
    home = db.session.scalar(select(Location).filter_by(name="Home"))
    for name in ("Fridge", "Freezer"):
        client.post("/places/add", data={"name": name, "parent_id": str(home.id)})
    for store in ("Costco", "Walmart"):
        client.post("/stores", data={"name": store})
    for aisle in ("Dairy", "Frozen"):
        client.post("/aisles", data={"name": aisle})
    ids = {r.name: r.id for model in (Location, Store, Aisle) for r in db.session.scalars(select(model))}
    return ids


def item_named(name):
    return db.session.scalar(select(Item).filter_by(name=name))


def put(client, place_id, name, quantity=None):
    client.post("/inventory/add", data={"location_id": place_id, "name": name})
    if quantity is not None:
        s = db.session.scalar(select(Stock).join(Stock.item).where(Item.name == name, Stock.location_id == place_id))
        client.post(f"/inventory/{s.id}/set", data={"quantity": str(quantity)})


def edit(client, name, **fields):
    item = item_named(name)
    data = {"name": item.name, "aisle_id": "0", "default_unit": "", "low_stock_threshold": "", "notes": ""}
    data.update(fields)
    client.post(f"/items/{item.id}/edit", data=data)


def entries():
    return sorted((e.item.name, e.quantity, e.in_cart) for e in db.session.scalars(select(ListEntry)))


def list_rows(client, query=""):
    page = client.get("/list" + query).data.decode()
    groups = re.findall(r'<h2 class="section-label">([^<]+)</h2>(.*?)</ul>', page, re.S)
    return [(g.strip(), re.findall(r'<span class="row-title">([^<]+)</span>', body)) for g, body in groups]


# --- Find ------------------------------------------------------------------

def test_find_shows_amount_and_where(client):
    ids = setup(client)
    put(client, ids["Freezer"], "Burgers", 2)
    put(client, ids["Fridge"], "Coconut Milk", 1)
    client.post("/items", data={"name": "Milk"})

    page = client.get("/?q=milk").data.decode()
    names = re.findall(r'data-testid="result">.*?<span class="fw-bold" style="font-size: 1.125rem">([^<]+)</span>', page, re.S)
    assert names == ["Milk", "Coconut Milk"]  # starts-with first
    assert "Not counted anywhere" in page and "Fridge" in page

    page = client.get("/?q=burg").data.decode()
    assert "2 in stock" in page and "Freezer" in page


def test_find_nothing_offers_list_or_create(client):
    setup(client)
    page = client.get("/?q=zucchini").data.decode()
    assert "Nothing called “zucchini” yet." in page
    resp = client.post("/find/new-item", data={"name": "Zucchini"}, follow_redirects=True)
    assert b"Added Zucchini. Now say where you keep it." in resp.data
    assert resp.request.path == f"/items/{item_named('Zucchini').id}"


def test_running_low_on_find_and_list(client):
    ids = setup(client)
    put(client, ids["Freezer"], "Burgers", 0)
    put(client, ids["Fridge"], "Yogurt", 1)
    put(client, ids["Fridge"], "Cheese", 3)
    edit(client, "Yogurt", low_stock_threshold="1")
    edit(client, "Cheese", low_stock_threshold="1")

    page = client.get("/").data.decode()
    low = re.findall(r'data-testid="low">.*?<span class="row-title">([^<]+)</span>', page, re.S)
    assert low == ["Burgers", "Yogurt"]  # out first; Cheese has plenty
    assert "+ Burgers" in client.get("/list").data.decode()


# --- The list --------------------------------------------------------------

def test_add_by_name_creates_item_and_skips_duplicates(client):
    setup(client)
    resp = client.post("/list/add", data={"name": "  Oat  milk "}, follow_redirects=True)
    assert b"Added Oat milk to the list. (New item.)" in resp.data
    resp = client.post("/list/add", data={"name": "OAT MILK"}, follow_redirects=True)
    assert b"Oat milk is already on the list." in resp.data
    assert entries() == [("Oat milk", 1, False)]
    assert b"Type what you need." in client.post("/list/add", data={"name": " "}, follow_redirects=True).data


def test_toggle_from_anywhere(client):
    setup(client)
    client.post("/items", data={"name": "Eggs"})
    eggs = item_named("Eggs")
    client.post(f"/list/items/{eggs.id}/toggle")
    assert entries() == [("Eggs", 1, False)]
    client.post(f"/list/items/{eggs.id}/toggle")
    assert entries() == []


def test_groups_follow_aisle_order_and_other_last(client):
    ids = setup(client)
    for name in ("Peas", "Milk", "Batteries"):
        client.post("/list/add", data={"name": name})
    edit(client, "Peas", aisle_id=str(ids["Frozen"]))
    edit(client, "Milk", aisle_id=str(ids["Dairy"]))
    assert list_rows(client) == [("Dairy", ["Milk"]), ("Frozen", ["Peas"]), ("Other", ["Batteries"])]

    client.post(f"/aisles/{ids['Frozen']}/move", data={"direction": "up"})
    assert [g for g, _ in list_rows(client)] == ["Frozen", "Dairy", "Other"]


def test_store_mode_filters_and_remembers(client):
    ids = setup(client)
    for name in ("Peas", "Milk", "Batteries"):
        client.post("/list/add", data={"name": name})
    edit(client, "Peas", store_ids=[str(ids["Costco"])])
    edit(client, "Milk", store_ids=[str(ids["Walmart"])])
    # Batteries: no store, so "any store".

    rows = [n for _, names in list_rows(client, f"?store={ids['Costco']}") for n in names]
    assert sorted(rows) == ["Batteries", "Peas"]
    page = client.get("/list").data.decode()  # remembered
    assert "1 more for other stores" in page and "Milk" not in re.sub(r'<datalist.*?</datalist>', "", page, flags=re.S)

    rows = [n for _, names in list_rows(client, f"?store={ids['Costco']}&all=1") for n in names]
    assert sorted(rows) == ["Batteries", "Milk", "Peas"]
    rows = [n for _, names in list_rows(client, "?store=all") for n in names]
    assert sorted(rows) == ["Batteries", "Milk", "Peas"]


def test_cart_and_quantity(client):
    setup(client)
    client.post("/list/add", data={"name": "Eggs"})
    entry = db.session.scalar(select(ListEntry))
    client.post(f"/list/{entry.id}/quantity", data={"delta": "1"})
    client.post(f"/list/{entry.id}/quantity", data={"delta": "1"})
    client.post(f"/list/{entry.id}/quantity", data={"delta": "-1"})
    assert entries() == [("Eggs", 2, False)]
    client.post(f"/list/{entry.id}/quantity", data={"delta": "-1"})
    client.post(f"/list/{entry.id}/quantity", data={"delta": "-1"})  # never below 1
    assert entries() == [("Eggs", 1, False)]

    client.post(f"/list/{entry.id}/cart")
    page = client.get("/list").data.decode()
    assert "In the cart · 1" in page and "Done shopping · 1 in the cart" in page
    client.post(f"/list/{entry.id}/cart")
    assert entries() == [("Eggs", 1, False)]
    client.post(f"/list/{entry.id}/remove")
    assert entries() == []


def test_done_shopping_puts_away_into_suggested_places(client):
    ids = setup(client)
    put(client, ids["Freezer"], "Peas", 0)  # Peas usually live in the freezer
    client.post("/list/add", data={"name": "Peas"})
    client.post("/list/add", data={"name": "Batteries"})  # not kept anywhere yet
    client.post("/list/add", data={"name": "Milk"})        # stays on the list
    peas, batteries = (db.session.scalar(select(ListEntry).join(ListEntry.item).where(Item.name == n))
                       for n in ("Peas", "Batteries"))
    client.post(f"/list/{peas.id}/quantity", data={"delta": "1"})  # buying 2
    for e in (peas, batteries):
        client.post(f"/list/{e.id}/cart")

    page = client.get("/list/done").data.decode()
    assert f'<option value="{ids["Freezer"]}" selected>Home › Freezer</option>' in page
    assert 'name="place_%d"' % batteries.id in page

    resp = client.post("/list/done", data={"action": "put_away", f"place_{peas.id}": str(ids["Freezer"]),
                                           f"place_{batteries.id}": ""}, follow_redirects=True)
    assert b"Put away: Peas" in resp.data and b"Cleared 2 items from the list." in resp.data
    assert entries() == [("Milk", 1, False)]
    freezer_peas = db.session.scalar(select(Stock).join(Stock.item).where(Item.name == "Peas"))
    assert freezer_peas.quantity == 2
    assert db.session.scalar(select(Stock).join(Stock.item).where(Item.name == "Batteries")) is None


def test_done_shopping_just_clear(client):
    ids = setup(client)
    put(client, ids["Fridge"], "Milk", 1)
    client.post("/list/add", data={"name": "Milk"})
    entry = db.session.scalar(select(ListEntry))
    client.post(f"/list/{entry.id}/cart")
    client.post("/list/done", data={"action": "clear", f"place_{entry.id}": str(ids["Fridge"])})
    assert entries() == []
    assert db.session.scalar(select(Stock)).quantity == 1  # unchanged


def test_done_with_empty_cart(client):
    setup(client)
    resp = client.get("/list/done", follow_redirects=True)
    assert b"Nothing in the cart yet" in resp.data
    assert client.post("/list/done", data={"action": "explode"}).status_code == 302  # empty cart: back to list


def test_list_badge(client):
    setup(client)
    assert b"tab-badge" not in client.get("/").data
    client.post("/list/add", data={"name": "Eggs"})
    client.post("/list/add", data={"name": "Milk"})
    assert re.search(rb'class="tab-badge">2<', client.get("/").data)


def test_store_toggle_on_item_page(client):
    ids = setup(client)
    client.post("/items", data={"name": "Eggs"})
    eggs = item_named("Eggs")
    client.post(f"/items/{eggs.id}/stores/{ids['Costco']}")
    assert [s.name for s in item_named("Eggs").stores] == ["Costco"]
    client.post(f"/items/{eggs.id}/stores/{ids['Costco']}")
    assert item_named("Eggs").stores == []
