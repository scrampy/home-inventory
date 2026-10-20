"""Browser test on a phone: build a places tree, keep things in it, find them.
Run with: pytest -m e2e --browser-channel msedge"""

import pytest
from playwright.sync_api import expect

from e2e_helpers import PHONE, assert_fits_phone, assert_not_reloaded, fill_signup, mark_page, tab

pytestmark = pytest.mark.e2e


def add_place(page, name, inside=None):
    form = page.locator("#add-place")
    form.get_by_label("Name of the new place").fill(name)
    if inside:
        form.get_by_label("Inside").select_option(label=inside)
    form.get_by_role("button", name="Add place").click()


def test_places_tree_stock_and_find(live_app, browser):
    page = browser.new_context(viewport=PHONE).new_page()
    page.goto(live_app.config["APP_BASE_URL"] + "/signup")
    fill_signup(page, "Ann", "ann@example.com", "The Smiths")
    expect(page.get_by_role("heading", name="The Smiths")).to_be_visible()

    tab(page, "Places")
    add_place(page, "Home")
    add_place(page, "Basement", inside="Home")
    add_place(page, "Freezer", inside="Home › Basement")
    expect(page.get_by_text("Added Home › Basement › Freezer.")).to_be_visible()
    assert_fits_phone(page)

    page.get_by_test_id("place").filter(has_text="Freezer").click()
    expect(page.get_by_role("heading", name="Freezer")).to_be_visible()
    expect(page.get_by_role("navigation", name="Breadcrumb")).to_contain_text("Home")
    page.get_by_label("Item to add to Freezer").fill("Burgers")
    page.get_by_role("button", name="Add", exact=True).click()
    expect(page.get_by_text("Added new item Burgers: 1 in Freezer.")).to_be_visible()
    assert_fits_phone(page)

    # -/+ update in place; at zero the row offers the shopping list, also in place.
    mark_page(page)
    qty = page.get_by_label("Quantity of Burgers in Freezer")
    page.get_by_role("button", name="One more Burgers").click()
    expect(qty).to_have_value("2")
    page.get_by_role("button", name="One less Burgers").click()
    page.get_by_role("button", name="One less Burgers").click()
    expect(qty).to_have_value("0")
    expect(page.get_by_text("All gone. Get more?")).to_be_visible()
    page.get_by_role("button", name="Add Burgers to the shopping list").click()
    expect(page.get_by_role("button", name="Take Burgers off the shopping list")).to_be_visible()
    assert_not_reloaded(page)
    expect(page.get_by_role("navigation", name="Main")).to_contain_text("1")  # List badge updated

    # Places shows rolled-up counts.
    tab(page, "Places")
    expect(page.get_by_test_id("place").filter(has_text="Home")).to_contain_text("1 out")

    # Find: "do we have burgers?" with where they are, live as you type.
    tab(page, "Find")
    mark_page(page)
    page.get_by_label("Search everything we keep").fill("burg")
    result = page.get_by_test_id("result")
    expect(result).to_have_count(1)
    expect(result).to_contain_text("Out")
    expect(result).to_contain_text("Basement › Freezer")
    expect(result.get_by_role("button", name="On the shopping list ✓")).to_be_visible()
    assert_not_reloaded(page)
    assert_fits_phone(page)
