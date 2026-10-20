"""Browser test of inventory on a phone: quick add and in-place +/-.
Run with: pytest -m e2e --browser-channel msedge"""

import pytest
from playwright.sync_api import expect

from e2e_helpers import PHONE, assert_fits_phone, fill_signup

pytestmark = pytest.mark.e2e


def test_inventory_in_place_updates(live_app, browser):
    page = browser.new_context(viewport=PHONE).new_page()
    base = live_app.config["APP_BASE_URL"]
    page.goto(base + "/signup")
    fill_signup(page, "Ann", "ann@example.com", "The Smiths")
    page.goto(base + "/locations")
    page.get_by_role("button", name="Add these").click()

    page.goto(base + "/inventory")
    page.get_by_role("link", name="Freezer").click()
    page.get_by_label("Item to add to Freezer").fill("Frozen peas")
    page.get_by_role("button", name="Add").click()
    expect(page.get_by_text("Added new item Frozen peas: 1 in Freezer.")).to_be_visible()
    assert_fits_phone(page)

    qty = page.get_by_label("Quantity of Frozen peas in Freezer")
    # Mark the page: a full reload would lose this, an in-place update keeps it.
    page.evaluate("window.__noReload = true")
    page.get_by_role("button", name="One more Frozen peas").click()
    expect(qty).to_have_value("2")
    page.get_by_role("button", name="One more Frozen peas").click()
    expect(qty).to_have_value("3")
    page.get_by_role("button", name="One less Frozen peas").click()
    expect(qty).to_have_value("2")
    qty.fill("0.5")
    qty.press("Enter")
    expect(page.get_by_test_id("stock").filter(has_text="Out")).to_have_count(0)
    expect(qty).to_have_value("0.5")
    page.get_by_role("button", name="One less Frozen peas").click()
    expect(qty).to_have_value("0")
    expect(page.get_by_test_id("stock").filter(has_text="Out")).to_have_count(1)
    expect(page.get_by_role("button", name="One less Frozen peas")).to_be_disabled()
    assert page.evaluate("window.__noReload") is True

    # The change was saved: it survives a reload, and shows in the All view.
    page.reload()
    expect(page.get_by_label("Quantity of Frozen peas in Freezer")).to_have_value("0")
    page.get_by_role("link", name="All", exact=True).click()
    expect(page.get_by_test_id("item-total").filter(has_text="Frozen peas")).to_contain_text("Out")
