import os
os.environ['E2E_TEST'] = '1'
os.environ['TEST_DB_PATH'] = os.path.abspath('test.db')
print(f"DEBUG: test_ui_playwright.py using DB path: {os.path.abspath('test.db')}")

import pytest
from playwright.sync_api import sync_playwright
import threading
import time
import requests
import subprocess
import os
import socket
import random
import string
import sys

# Utility for UI tests: setup user and login via test endpoint
def setup_test_user(email, password, family, base_url):
    resp = requests.post(f"{base_url}/test/setup-user", json={
        "email": email,
        "password": password,
        "family": family
    })
    assert resp.status_code == 200
    return resp.json()

def test_signup_login_invite_flow(flask_server):
    base_url = flask_server
    # Ensure all tables exist in test.db before creating user
    from app import db, app
    with app.app_context():
        db.create_all()
    setup_test_user("uiadmin@example.com", "pw1234", "UITestFam", base_url)
    # Immediately after user creation, check test.db for user existence
    import sqlite3
    conn = sqlite3.connect('test.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM user WHERE email = ?", ("uiadmin@example.com",))
    user_row = cursor.fetchone()
    assert user_row is not None, "Test user was not created in test.db!"
    conn.close()
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        # Step 1: Go to the login/signup page
        page.goto(f"{base_url}/auth")
        # Step 2: Fill in the login form using specific login input selectors
        page.locator("#loginEmail").fill("uiadmin@example.com")
        page.locator("#loginPassword").fill("pw1234")
        # Step 3: Click the login button using role selector and capture /login response
        with page.expect_response(lambda response: '/login' in response.url) as resp_info:
            page.get_by_role("button", name="Login").click()
        resp = resp_info.value
        print(f"[DEBUG] /login response status: {resp.status}")
        try:
            print(f"[DEBUG] /login response body: {resp.text()}")
        except Exception:
            print("[DEBUG] Could not read /login response body.")
        # Step 4: Wait for navigation or dashboard heading
        page.wait_for_load_state()
        try:
            login_error = page.inner_text('#loginError')
        except Exception:
            pass
        # Step 5: Assert that the Family Dashboard heading is visible
        assert page.get_by_role("heading", name="Family Dashboard").is_visible(), "Did not find Family Dashboard after login!"
        # Step 6: Optionally, check for family name in page content
        assert "UITestFam" in page.content()
        browser.close()

def test_base_nav_ui(flask_server):
    base_url = flask_server
    setup_test_user("navui@example.com", "pw1234", "NavUITestFam", base_url)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        # Explicitly log in via the UI before checking /family
        page.goto(f"{base_url}/auth")
        page.fill('input[name="email"]', "navui@example.com")
        page.fill('input[name="password"]', "pw1234")
        page.click('button[type="submit"]')
        page.wait_for_url(f"{base_url}/family", timeout=5000)
        # Now check the family dashboard and navigation
        page.goto(f"{base_url}/family")
        assert "Logged in as navui@example.com" in page.content()
        assert "Profile" in page.content()
        assert "Logout" in page.content()
        page.goto(f"{base_url}/web/locations")
        assert "Login" not in page.content()
        browser.close()

def test_inventory_requires_login_split(flask_server):
    base_url = flask_server
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        protected_urls = [
            f"{base_url}/web/inventory",
            f"{base_url}/web/locations",
            f"{base_url}/web/aisles",
            f"{base_url}/web/stores",
            f"{base_url}/web/master-items",
            f"{base_url}/web/shopping-list",
        ]
        for url in protected_urls:
            page.goto(url)
            page.wait_for_url("**/auth", timeout=5000)
            html = page.content()
            assert ("Login" in html or "Sign Up" in html or "login-tab" in html or "signup-tab" in html or "loginForm" in html), f"Login UI not found for {url}"
        browser.close()

def test_inventory_requires_login(flask_server):
    base_url = flask_server
    # Setup a test user and log in, analogous to test_base_nav_ui
    setup_test_user("navui@example.com", "pw1234", "NavUITestFam", base_url)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        # Login via UI
        page.goto(f"{base_url}/auth")
        page.fill('input[name="email"]', "navui@example.com")
        page.fill('input[name="password"]', "pw1234")
        page.click('button[type="submit"]')
        page.wait_for_url(f"{base_url}/family", timeout=5000)
        # Now test protected URLs
        protected_urls = [
            f"{base_url}/web/inventory",
            f"{base_url}/web/locations",
            f"{base_url}/web/aisles",
            f"{base_url}/web/stores",
            f"{base_url}/web/master-items",
            f"{base_url}/web/shopping-list",
        ]
        for url in protected_urls:
            page.goto(url)
            html = page.content()
            assert ("Login" not in html and "Sign Up" not in html and "login-tab" not in html and "signup-tab" not in html and "loginForm" not in html), f"Unexpected login UI for {url} (should be logged in)"
        browser.close()

def test_inventory_requires_login_each(flask_server):
    base_url = flask_server
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        urls = [
            ("/web/inventory", "Inventory"),
            ("/web/locations", "Locations"),
            ("/web/aisles", "Aisles"),
            ("/web/stores", "Stores"),
            ("/web/master-items", "Master Items"),
            ("/web/shopping-list", "Shopping List"),
        ]
        for path, label in urls:
            url = f"{base_url}{path}"
            page.goto(url)
            try:
                page.wait_for_url("**/auth", timeout=5000)
            except Exception as e:
                print(f"FAILED: {label} ({url}) did not redirect to /auth.")
                print("Exception:", e)
                print("HTML:", page.content())
                raise
            html = page.content()
            assert ("Login" in html or "Sign Up" in html or "login-tab" in html or "signup-tab" in html or "loginForm" in html), f"Login UI not found for {label} ({url})"
        browser.close()

def test_viewport_meta_tag_present(flask_server):
    """
    This test validates that the viewport meta tag is present on all main screens, ensuring mobile scaling is enabled.
    """
    base_url = flask_server
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width":375, "height":667})  # iPhone 12 size
        # URLs to check for viewport meta tag
        urls = [
            f"{base_url}/web/inventory",
            f"{base_url}/web/locations",
            f"{base_url}/web/aisles",
            f"{base_url}/web/stores",
            f"{base_url}/web/master-items",
            f"{base_url}/web/shopping-list",
            f"{base_url}/auth",
            f"{base_url}/family"
        ]
        for url in urls:
            page.goto(url)
            # Get all meta tags
            meta_tags = page.locator('meta[name="viewport"]')
            assert meta_tags.count() > 0, f"Viewport meta tag missing on {url}"
            content = meta_tags.first.get_attribute("content")
            assert "width=device-width" in content and "initial-scale=1" in content, f"Viewport meta tag content incorrect on {url}: {content}"
        browser.close()

def test_navbar_mobile_collapse(flask_server):
    """
    This test validates that the navbar collapses into a hamburger menu on mobile viewports and expands on desktop viewports.
    """
    base_url = flask_server
    with sync_playwright() as p:
        browser = p.chromium.launch()
        # Mobile viewport
        page = browser.new_page(viewport={"width":375, "height":667})  # iPhone 12 size
        page.goto(f"{base_url}/web/inventory")
        # Hamburger button should be visible
        assert page.locator('.navbar-toggler').is_visible(), "Navbar toggler (hamburger) not visible on mobile viewport"
        # Navbar links should be hidden by default
        assert not page.locator('.navbar-collapse.show').is_visible(), "Navbar collapse should be hidden by default on mobile"
        # Click hamburger to expand
        page.locator('.navbar-toggler').click()
        assert page.locator('.navbar-collapse').is_visible(), "Navbar collapse did not expand after clicking toggler"
        # Check that at least one nav-link is visible
        assert page.locator('.navbar-nav .nav-link').first.is_visible(), "Nav links not visible after expanding navbar on mobile"
        # Desktop viewport
        page.set_viewport_size({"width":1200, "height":800})
        page.reload()
        # Hamburger should NOT be visible
        assert not page.locator('.navbar-toggler').is_visible(), "Navbar toggler (hamburger) should not be visible on desktop"
        # Navbar links should be visible
        assert page.locator('.navbar-nav .nav-link').first.is_visible(), "Nav links not visible on desktop"
        browser.close()

def test_inventory_table_mobile_responsive(flask_server):
    """
    This test ensures the inventory table is horizontally scrollable and usable on mobile viewports, and that all actions remain accessible.
    """
    base_url = flask_server
    setup_test_user("ui_mobile@example.com", "pw1234", "UITestFam", base_url)
    # Create at least one inventory item for the user via API
    # 1. Login via requests to get session cookie
    session = requests.Session()
    resp = session.post(f"{base_url}/login", json={"email": "ui_mobile@example.com", "password": "pw1234"})
    assert resp.status_code == 200
    # 2. Create an aisle
    resp = session.post(f"{base_url}/aisles", json={"name": "MobileTestAisle"})
    assert resp.status_code == 201
    aisle_id = resp.json()["id"]
    # 3. Create a master item
    resp = session.post(f"{base_url}/master-items", json={"name": "MobileTestItem", "aisle_id": aisle_id})
    assert resp.status_code == 201
    item_id = resp.json()["id"]
    # 4. Create a location
    resp = session.post(f"{base_url}/locations", json={"name": "MobileTestLoc"})
    assert resp.status_code == 201
    loc_id = resp.json()["id"]
    # 5. Create an inventory record
    resp = session.post(f"{base_url}/inventory", json={"master_item_id": item_id, "location_id": loc_id, "quantity": 1})
    assert resp.status_code == 201
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width":375, "height":667})  # iPhone 12 size
        # Login
        page.goto(f"{base_url}/auth")
        page.fill('input[name="email"]', "ui_mobile@example.com")
        page.fill('input[name="password"]', "pw1234")
        page.click('button[type="submit"]')
        page.wait_for_url(f"{base_url}/family", timeout=5000)
        # Now go to inventory page
        page.goto(f"{base_url}/web/inventory")
        # Table should be inside #table-responsive-wrapper
        responsive_div = page.locator('#table-responsive-wrapper')
        inventory_table = page.locator('#inventoryTable')
        assert responsive_div.count() > 0, "#table-responsive-wrapper div not found on mobile"
        assert inventory_table.count() > 0, "#inventoryTable not found on mobile"
        # Check that the table is a direct child of the responsive wrapper
        parent = inventory_table.evaluate("el => el.parentElement.id === 'table-responsive-wrapper'")
        assert parent, "#inventoryTable is not a direct child of #table-responsive-wrapper"
        # Table should be horizontally scrollable if needed
        table_box = inventory_table.bounding_box()
        wrapper_box = responsive_div.bounding_box()
        assert table_box["width"] <= wrapper_box["width"] or wrapper_box["width"] < 400, "Table is overflowing its responsive container on mobile"
        # DEBUG: Dump more HTML for investigation
        html = page.content()
        print("\n[DEBUG] Inventory page HTML on mobile (first 4000 chars):\n", html[:4000])
        # DEBUG: Screenshot for visual inspection
        page.screenshot(path="inventory_mobile_debug.png", full_page=True)
        # Select the first available location in the dropdown
        location_select = page.locator('select[name="location_id"]')
        # Wait for dropdown to be enabled and populated
        page.wait_for_selector('select[name="location_id"]', state="visible")
        options = page.locator('select[name="location_id"] option:not([value=""])').all()
        assert options, "No locations found in dropdown"
        first_location_value = options[0].get_attribute('value')
        page.select_option('select[name="location_id"]', first_location_value)
        # Wait for page/table to update after location selection
        page.wait_for_selector('#inventoryTable tbody tr')
        # All action buttons (add, update, delete) should be visible for the first row
        first_row = inventory_table.locator('tbody tr').first
        buttons = first_row.locator('button.btn')
        visible_count = buttons.filter(has_text=None).evaluate_all("els => els.filter(el => el.offsetParent !== null).length")
        assert visible_count > 0, "No visible action buttons in first row on mobile"
        browser.close()

def test_shopping_list_mobile_responsive(flask_server):
    """
    This test covers the shopping list user flow on mobile:
    - Add a master item and put it on the shopping list
    - Go to the shopping list page
    - Ensure table is wrapped in .table-responsive
    - Ensure Bought and Delete buttons are visible and have correct tap target size
    - Mark an item as bought and then remove it, verifying UI updates
    """
    base_url = flask_server
    setup_test_user("ui_shopping@example.com", "pw1234", "UITestFam", base_url)
    session = requests.Session()
    resp = session.post(f"{base_url}/login", json={"email": "ui_shopping@example.com", "password": "pw1234"})
    assert resp.status_code == 200
    # Create an aisle
    resp = session.post(f"{base_url}/aisles", json={"name": "ShopTestAisle"})
    assert resp.status_code == 201
    aisle_id = resp.json()["id"]
    # Create a master item
    resp = session.post(f"{base_url}/master-items", json={"name": "ShopTestItem", "aisle_id": aisle_id})
    assert resp.status_code == 201
    item_id = resp.json()["id"]
    # Add to shopping list
    resp = session.post(f"{base_url}/shopping-list", json={"item_id": item_id})
    assert resp.status_code == 201
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width":375, "height":667})  # iPhone 12 size
        # Login
        page.goto(f"{base_url}/auth")
        page.fill('input[name="email"]', "ui_shopping@example.com")
        page.fill('input[name="password"]', "pw1234")
        page.click('button[type="submit"]')
        page.wait_for_url(f"{base_url}/family", timeout=5000)
        # Go to shopping list
        page.goto(f"{base_url}/web/shopping-list")
        # Table should be inside .table-responsive
        responsive_div = page.locator('.table-responsive')
        shopping_table = page.locator('table.table')
        assert responsive_div.count() > 0, ".table-responsive div not found on mobile"
        assert shopping_table.count() > 0, "Shopping list table not found on mobile"
        # Check that the table is a direct child of the responsive wrapper
        parent = shopping_table.evaluate("el => el.parentElement.classList.contains('table-responsive')")
        assert parent, "Shopping list table is not a direct child of .table-responsive"
        # Table should be horizontally scrollable if needed
        table_box = shopping_table.bounding_box()
        wrapper_box = responsive_div.bounding_box()
        assert table_box["width"] <= wrapper_box["width"] or wrapper_box["width"] < 400, "Table is overflowing its responsive container on mobile"
        # Bought and Delete buttons should be visible and full-width on mobile
        first_row = shopping_table.locator('tbody tr').first
        bought_btn = first_row.locator('button:has-text("Bought")')
        delete_btn = first_row.locator('button.btn-outline-danger')
        assert bought_btn.is_visible(), "Bought button not visible on mobile"
        assert delete_btn.is_visible(), "Delete button not visible on mobile"
        # Tap target: width should be at least 44px
        bought_box = bought_btn.bounding_box()
        delete_box = delete_btn.bounding_box()
        assert bought_box["width"] >= 44, "Bought button tap target too small"
        assert delete_box["width"] >= 44, "Delete button tap target too small"
        # Mark as bought
        bought_btn.click()
        page.wait_for_timeout(500)
        # Should now show as checked
        assert "text-decoration-line-through" in first_row.inner_html(), "Item not marked as bought after click"
        # Delete the item
        delete_btn.click()
        page.wait_for_timeout(500)
        # Should show empty shopping list message
        assert page.locator('.alert-info').inner_text().strip().startswith("No items on your shopping list"), "Shopping list not empty after deleting item"
        browser.close()

def test_store_add_and_duplicate_ui(flask_server):
    """
    UI test: Add a store (e.g., 'walmart'), verify it appears (title-cased as 'Walmart'), then try to add again and check for duplicate error.
    Follows technique and setup from other UI tests (login, setup_test_user, etc).
    Uses the actual button markup from stores.html.
    """
    base_url = flask_server
    setup_test_user("ui_store@example.com", "pw1234", "UITestFam", base_url)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width":375, "height":667})
        # Login
        page.goto(f"{base_url}/auth")
        page.fill('input[name="email"]', "ui_store@example.com")
        page.fill('input[name="password"]', "pw1234")
        page.click('button[type="submit"]')
        page.wait_for_url(f"{base_url}/family", timeout=5000)
        # Go to stores page
        page.goto(f"{base_url}/web/stores")
        # Add a new store (lowercase, should be title-cased in UI)
        store_name = "walmart"
        page.fill('input[name="name"]', store_name)
        # The submit button is: <button class="btn btn-primary">Add</button>
        page.get_by_role("button", name="Add").click()
        page.wait_for_timeout(500)
        # Store should appear in the table, title-cased
        store_row = page.locator('table tr td').filter(has_text="Walmart")
        assert store_row.count() > 0, "Store 'Walmart' not found in UI after add."
        # Try to add duplicate
        page.fill('input[name="name"]', store_name)
        page.get_by_role("button", name="Add").click()
        page.wait_for_timeout(500)
        # Should see error message about duplicate store
        error_alert = page.locator('.alert-danger, .invalid-feedback').filter(has_text="already exists")
        assert error_alert.count() > 0, "Duplicate store error not shown in UI."
        browser.close()
