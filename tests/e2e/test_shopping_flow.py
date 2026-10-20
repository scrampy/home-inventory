"""Browser test on a phone: shop at one store, tick things into the cart, put them away.
Run with: pytest -m e2e --browser-channel msedge"""

import pytest
from playwright.sync_api import expect
from sqlalchemy import select

from e2e_helpers import PHONE, assert_fits_phone, assert_not_reloaded, fill_signup, mark_page, tab
from homeinv.extensions import db
from homeinv.models import Item, Location, Stock, Store  # noqa: F401

pytestmark = pytest.mark.e2e


def test_shop_at_a_store_and_put_away(live_app, browser):
    base = live_app.config["APP_BASE_URL"]
    page = browser.new_context(viewport=PHONE).new_page()
    page.goto(base + "/signup")
    fill_signup(page, "Ann", "ann@example.com", "The Smiths")
    expect(page.get_by_role("heading", name="The Smiths")).to_be_visible()

    # Set up through the app itself: a place, two stores, items with stores.
    page.goto(base + "/places")
    page.locator("#add-place").get_by_label("Name of the new place").fill("Freezer")
    page.locator("#add-place").get_by_role("button", name="Add place").click()
    page.get_by_test_id("place").filter(has_text="Freezer").click()
    page.get_by_label("Item to add to Freezer").fill("Peas")
    page.get_by_role("button", name="Add", exact=True).click()
    for store in ("Costco", "Walmart"):
        page.goto(base + "/stores")
        page.get_by_label("New store").fill(store)
        page.get_by_role("button", name="Add").click()
    with live_app.app_context():
        peas = db.session.scalar(select(Item).filter_by(name="Peas"))
        costco = db.session.scalar(select(Store).filter_by(name="Costco"))
        peas_id, costco_id = peas.id, costco.id
    page.goto(f"{base}/items/{peas_id}")
    page.get_by_role("button", name="Costco").click()
    expect(page.get_by_role("button", name="✓ Costco")).to_be_visible()

    # Build the list: Peas (Costco), Milk (Walmart-only via item page), Batteries (any store).
    tab(page, "List")
    for name in ("Peas", "Batteries", "Milk"):
        page.get_by_label("Add an item to the shopping list").fill(name)
        page.get_by_role("button", name="Add", exact=True).click()
        expect(page.get_by_test_id("entry").filter(has_text=name)).to_have_count(1)
    with live_app.app_context():
        milk_id = db.session.scalar(select(Item.id).filter_by(name="Milk"))
    page.goto(f"{base}/items/{milk_id}")
    page.get_by_role("button", name="Walmart").click()

    # Shopping at Costco: Milk is hidden behind "more for other stores".
    tab(page, "List")
    page.get_by_role("link", name="Costco").click()
    expect(page.get_by_test_id("entry")).to_have_count(2)
    expect(page.get_by_text("1 more for other stores · show")).to_be_visible()
    assert_fits_phone(page)

    # Tick two into the cart, without reloading the page.
    mark_page(page)
    page.get_by_role("button", name="Put Peas in the cart").click()
    expect(page.get_by_test_id("cart-entry").filter(has_text="Peas")).to_have_count(1)
    page.get_by_role("button", name="Put Batteries in the cart").click()
    expect(page.get_by_text("In the cart · 2")).to_be_visible()
    assert_not_reloaded(page)

    # Done shopping: Peas go back to the Freezer (suggested), Batteries aren't kept anywhere.
    page.get_by_role("link", name="Done shopping · 2 in the cart").click()
    expect(page.get_by_role("heading", name="Put away what you bought?")).to_be_visible()
    expect(page.get_by_label("Peas")).to_have_value(str(_freezer_id(live_app)))
    page.get_by_label("Batteries").select_option(label="Don't add to the inventory")
    assert_fits_phone(page)
    page.get_by_role("button", name="Add to inventory and clear").click()
    expect(page.get_by_text("Put away: Peas → Freezer.")).to_be_visible()
    expect(page.get_by_test_id("cart-entry")).to_have_count(0)

    with live_app.app_context():
        stock = db.session.scalar(select(Stock).join(Stock.item).where(Item.name == "Peas"))
        assert stock.quantity == 2  # 1 already there + 1 bought


def _freezer_id(app):
    with app.app_context():
        return db.session.scalar(select(Location.id).filter_by(name="Freezer"))
