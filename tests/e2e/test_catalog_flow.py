"""Browser test of setting up the catalog on a phone. Run with: pytest -m e2e --browser-channel msedge"""

import pytest
from playwright.sync_api import expect

from e2e_helpers import PHONE, assert_fits_phone, fill_signup, open_menu

pytestmark = pytest.mark.e2e


def test_set_up_catalog_on_phone(live_app, browser):
    page = browser.new_context(viewport=PHONE).new_page()
    page.goto(live_app.config["APP_BASE_URL"] + "/signup")
    fill_signup(page, "Ann", "ann@example.com", "The Smiths")
    # New accounts land on their family page.
    expect(page.get_by_role("heading", name="The Smiths")).to_be_visible()

    # Aisles: take the suggestions, then rename one in place.
    open_menu(page, "Aisles")
    page.get_by_role("button", name="Add these").click()
    expect(page.get_by_test_id("row")).to_have_count(10)
    assert_fits_phone(page)
    dairy = page.get_by_test_id("row").filter(has_text="Dairy")
    dairy.get_by_text("Rename").click()
    dairy.get_by_label("New name for Dairy").fill("Dairy & eggs")
    dairy.get_by_role("button", name="Save").click()
    expect(page.get_by_text("Renamed Dairy to Dairy & eggs.")).to_be_visible()

    # Stores.
    open_menu(page, "Stores")
    for store in ("Costco", "Safeway"):
        page.get_by_label("New store").fill(store)
        page.get_by_role("button", name="Add").click()
    expect(page.get_by_test_id("row")).to_have_count(2)

    # Items: quick add, then fill in details.
    open_menu(page, "Items")
    page.get_by_label("New item").fill("Milk")
    page.get_by_role("button", name="Add").click()
    expect(page.get_by_text("Added Milk.")).to_be_visible()
    page.get_by_test_id("item").filter(has_text="Milk").click()
    assert_fits_phone(page)
    page.get_by_label("Aisle").select_option(label="Dairy & eggs")
    page.get_by_text("Costco", exact=True).click()
    page.get_by_label("Unit").fill("carton")
    page.get_by_label("Running low at").fill("1")
    page.get_by_role("button", name="Save").click()

    expect(page.get_by_text("Saved Milk.")).to_be_visible()
    milk = page.get_by_test_id("item").filter(has_text="Milk")
    expect(milk).to_contain_text("Dairy & eggs")
    expect(milk).to_contain_text("Costco")
    assert_fits_phone(page)

    # Deleting asks first.
    page.get_by_test_id("item").filter(has_text="Milk").click()
    page.once("dialog", lambda dialog: dialog.accept())
    page.get_by_role("button", name="Delete item").click()
    expect(page.get_by_text("Deleted Milk.")).to_be_visible()
    expect(page.get_by_test_id("item")).to_have_count(0)
