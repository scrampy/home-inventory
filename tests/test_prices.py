"""Price tracking: usual price, shelf-price check, recording at Done shopping."""

from datetime import timedelta

import pytest
from sqlalchemy import select

from helpers import signup
from homeinv.extensions import db
from homeinv.models import Item, ListEntry, Price, Store, utcnow
from homeinv.prices import ago, money, parse_money


# --- Money and dates -------------------------------------------------------

@pytest.mark.parametrize("text, cents", [
    ("4.99", 499), ("$4.99", 499), (" 5 ", 500), ("4,99", 499), ("1,299.00", 129900),
    ("0.5", 50), ("12.345", 1235),
])
def test_parse_money(text, cents):
    assert parse_money(text) == cents


@pytest.mark.parametrize("text", ["", "abc", "-1", "0", "nan", "inf", "1e9", "4.99.1"])
def test_parse_money_rejects(text):
    assert parse_money(text) is None


def test_money_and_ago():
    assert money(499) == "$4.99" and money(5) == "$0.05" and money(129900) == "$1,299.00"
    now = utcnow()
    assert ago(now) == "today"
    assert ago(now - timedelta(days=1)) == "yesterday"
    assert ago(now - timedelta(days=5)) == "5 days ago"
    assert ago(now - timedelta(days=21)) == "3 weeks ago"
    assert ago(now - timedelta(days=90)).count(" ") == 1          # "Jul 22"
    assert ago(now - timedelta(days=400)).endswith(str((now - timedelta(days=400)).year))


# --- Fixtures --------------------------------------------------------------

def setup(client):
    signup(client, "ann@example.com")
    for name in ("Costco", "Walmart"):
        client.post("/stores", data={"name": name})
    client.post("/items", data={"name": "Butter"})
    item = db.session.scalar(select(Item).filter_by(name="Butter"))
    stores = {s.name: s.id for s in db.session.scalars(select(Store))}
    return item, stores


def add_prices(item, *entries):
    """entries: (cents, store_name or None, days ago). Written directly to set their dates."""
    stores = {s.name: s for s in db.session.scalars(select(Store))}
    for cents, store, days in entries:
        db.session.add(Price(family_id=item.family_id, item_id=item.id, cents=cents,
                             store=stores.get(store), recorded_at=utcnow() - timedelta(days=days)))
    db.session.commit()


def check(client, item, text):
    return client.get(f"/items/{item.id}?check={text}").data.decode()


# --- Item page -------------------------------------------------------------

def test_no_prices_yet(client):
    item, _ = setup(client)
    page = client.get(f"/items/{item.id}").data.decode()
    assert "No prices yet" in page
    page = check(client, item, "5.49")
    assert "No price recorded yet. Save this one to compare next time." in page


def test_usual_is_median_of_last_five(client):
    item, _ = setup(client)
    # Newest first: 5.00, 5.20, 4.80, 9.99 (a spike), 5.10, then an old 3.00 that no longer counts.
    add_prices(item, (500, "Costco", 1), (520, "Walmart", 5), (480, "Costco", 9),
               (999, "Walmart", 15), (510, "Costco", 20), (300, None, 200))
    page = client.get(f"/items/{item.id}").data.decode()
    assert 'data-testid="usual-price">$5.10<' in page  # median(500, 520, 480, 999, 510)
    assert "Last paid $5.00 at Costco · yesterday" in page
    assert "Lowest $3.00" in page
    assert "Costco $5.00 · Walmart $7.60" in page  # per store, cheapest first
    assert "Price history (6)" in page


@pytest.mark.parametrize("shelf, kind, words", [
    ("4.50", "good", "Good price: 12% below usual ($5.10)."),
    ("2.99", "good", "Lowest yet: 41% below usual ($5.10)."),
    ("5.25", "usual", "About what we usually pay ($5.10)."),
    ("5.99", "high", "Higher than usual: 17% above $5.10."),
])
def test_shelf_price_verdicts(client, shelf, kind, words):
    item, _ = setup(client)
    add_prices(item, (500, "Costco", 1), (520, "Walmart", 5), (480, "Costco", 9), (999, None, 15), (510, None, 20),
               (300, None, 200))
    page = check(client, item, shelf)
    assert words in page
    assert {"good": "verdict-good", "high": "verdict-high", "usual": "verdict-usual"}[kind] in page


def test_bad_shelf_price(client):
    item, _ = setup(client)
    assert "Enter a price like 4.99." in check(client, item, "cheap")


def test_save_checked_price_at_store(client):
    item, stores = setup(client)
    client.get(f"/list?store={stores['Walmart']}")  # shopping at Walmart
    page = check(client, item, "4.79")
    assert f'<option value="{stores["Walmart"]}" selected>at Walmart</option>' in page  # store pre-picked
    resp = client.post(f"/items/{item.id}/prices", data={"price": "4.79", "store_id": stores["Walmart"]},
                       follow_redirects=True)
    assert b"Saved $4.79 for Butter at Walmart." in resp.data
    [p] = db.session.scalars(select(Price)).all()
    assert (p.cents, p.store.name, p.recorded_at.date()) == (479, "Walmart", utcnow().date())

    resp = client.post(f"/items/{item.id}/prices", data={"price": "free"}, follow_redirects=True)
    assert b"Enter a price like 4.99." in resp.data
    assert db.session.query(Price).count() == 1


def test_remove_a_wrong_price(client):
    item, _ = setup(client)
    add_prices(item, (499, None, 1), (49900, None, 0))  # oops, a typo
    typo = db.session.scalar(select(Price).filter_by(cents=49900))
    client.post(f"/prices/{typo.id}/delete")
    assert [p.cents for p in db.session.scalars(select(Price))] == [499]


def test_deleting_store_keeps_its_prices(client):
    item, stores = setup(client)
    add_prices(item, (499, "Costco", 1))
    client.post(f"/stores/{stores['Costco']}/delete")
    [p] = db.session.scalars(select(Price)).all()
    assert p.store_id is None and p.cents == 499


# --- Find, List and Done shopping ------------------------------------------

def test_usual_price_on_find_and_list(client):
    item, stores = setup(client)
    add_prices(item, (500, "Costco", 1), (600, "Walmart", 3))
    assert "Usually $5.50 · last $5.00 at Costco" in client.get("/?q=butter").data.decode()

    client.post("/list/add", data={"name": "Butter"})
    assert "usually $5.50" in client.get("/list?store=all").data.decode()
    assert "usually $6.00" in client.get(f"/list?store={stores['Walmart']}").data.decode()  # at that store


def test_prices_recorded_when_done_shopping(client):
    item, stores = setup(client)
    client.post("/list/add", data={"name": "Butter"})
    client.post("/list/add", data={"name": "Eggs"})
    butter, eggs = (db.session.scalar(select(ListEntry).join(ListEntry.item).where(Item.name == n))
                    for n in ("Butter", "Eggs"))
    for e in (butter, eggs):
        client.post(f"/list/{e.id}/cart")
    client.get(f"/list?store={stores['Costco']}")
    assert f'<option value="{stores["Costco"]}" selected>Costco</option>' in client.get("/list/done").data.decode()

    resp = client.post("/list/done", data={
        "action": "clear", "store_id": stores["Costco"],
        f"price_{butter.id}": "$4.49", f"price_{eggs.id}": "",  # no price for eggs: fine
    }, follow_redirects=True)
    assert b"Saved 1 price." in resp.data
    [p] = db.session.scalars(select(Price)).all()
    assert (p.item.name, p.cents, p.store.name) == ("Butter", 449, "Costco")
