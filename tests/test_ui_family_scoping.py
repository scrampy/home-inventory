import pytest
from playwright.sync_api import sync_playwright
import requests
import random
import string
import sqlite3
import os

def print_db_path():
    db_path = os.path.abspath('test.db')
    print(f"DEBUG: test_ui_family_scoping.py using DB path: {db_path}")
    return db_path

def setup_test_user(email, password, family, base_url):
    resp = requests.post(f"{base_url}/test/setup-user", json={
        "email": email,
        "password": password,
        "family": family
    })
    assert resp.status_code == 200
    return resp.json()["family_id"]

def test_family_inventory_isolation_serial(flask_server):
    base_url = flask_server
    user1_email = "fam1user@example.com"
    user2_email = "fam2user@example.com"
    password = "pw1234"
    fam1 = "FamilyWebA"
    fam2 = "FamilyWebB"
    setup_test_user(user1_email, password, fam1, base_url)
    setup_test_user(user2_email, password, fam2, base_url)

    db_path = print_db_path()

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        # --- User 1 (Family A) ---
        page.goto(f"{base_url}/auth")
        page.fill('input[name="email"]', user1_email)
        page.fill('input[name="password"]', password)
        page.click('button[type="submit"]')
        page.wait_for_url(f"{base_url}/family", timeout=5000)
        # Add location and inventory for Family A
        page.goto(f"{base_url}/web/locations")
        page.fill('input[name="name"]', 'PantryA')
        page.click('form.mb-3 button.btn-primary')
        # Wait for PantryA to appear in the table
        try:
            page.wait_for_selector('td:text("PantryA")', timeout=2000)
        except Exception:
            print("DEBUG: Page content after add attempt:\n", page.content())
            raise AssertionError("PantryA not found in locations table after add attempt")
        page.wait_for_timeout(500)
        # --- DB DEBUG: Check for PantryA location in DB ---
        # 1. Direct SQLite query
        if os.path.exists(db_path):
            with sqlite3.connect(db_path) as conn:
                cur = conn.cursor()
                cur.execute("SELECT name FROM location WHERE name=?", ("PantryA",))
                rows = cur.fetchall()
                print("DEBUG: Locations with name PantryA after add attempt (sqlite):", rows, flush=True)
        else:
            print("DEBUG: test.db does not exist after add attempt", flush=True)
        # 2. Query Flask backend debug endpoint
        try:
            resp = requests.get(f"{base_url}/test/debug-locations")
            debug_data = resp.json()
            print(f"DEBUG: /test/debug-locations returned: {debug_data}", flush=True)
        except Exception as e:
            print(f"DEBUG: Failed to query /test/debug-locations: {e}", flush=True)
        # Updated assertion: check for Pantrya in the locations table for Family A
        if os.path.exists(db_path):
            with sqlite3.connect(db_path) as conn:
                cur = conn.cursor()
                cur.execute("SELECT name FROM location WHERE name=?", ("Pantrya",))
                rows = cur.fetchall()
                assert any(r[0] == "Pantrya" for r in rows), "Pantrya not found in DB after add attempt"
        # --- UI assertion: Pantrya should be visible in the locations list ---
        content = page.content()
        assert "Pantrya" in content, f"Pantrya not found in page content: {content[:500]}"
        # Try to view Family B's location (should not exist)
        assert "PantryB" not in content, "User 1 should not see Family B's location"
        page.goto(f"{base_url}/web/inventory")
        assert "Pantrya" in page.content()
        assert "PantryB" not in page.content(), "User 1 should not see Family B's inventory/location"
        # --- Add Master Item for Family A ---
        page.goto(f"{base_url}/web/master-items")
        page.fill('input[name="name"]', 'BreadA')
        page.click('form.mb-3 button.btn-primary')
        try:
            page.wait_for_selector('a:text("BreadA")', timeout=2000)
        except Exception:
            print("DEBUG: Page content after BreadA add attempt:\n", page.content())
            raise AssertionError("BreadA not found in master items table after add attempt")
        page.wait_for_timeout(500)
        # --- DB DEBUG: Check for BreadA item in DB ---
        if os.path.exists(db_path):
            with sqlite3.connect(db_path) as conn:
                cur = conn.cursor()
                cur.execute("SELECT name FROM master_item WHERE name=?", ("Breada",))
                rows = cur.fetchall()
                assert any(r[0] == "Breada" for r in rows), "Breada not found in DB after add attempt"
        # --- UI assertion: Breada should be visible in the master items list ---
        content = page.content()
        assert "Breada" in content, f"Breada not found in page content: {content[:500]}"
        assert "BreadB" not in content, "User 1 should not see Family B's item"
        # Logout
        if page.query_selector('a#logout'):
            page.click('a#logout')
        else:
            page.goto(f"{base_url}/logout")
        page.wait_for_timeout(500)

        # --- User 2 (Family B) ---
        page.goto(f"{base_url}/auth")
        page.fill('input[name="email"]', user2_email)
        page.fill('input[name="password"]', password)
        page.click('button[type="submit"]')
        page.wait_for_url(f"{base_url}/family", timeout=5000)
        page.goto(f"{base_url}/web/locations")
        page.fill('input[name="name"]', 'PantryB')
        page.click('form.mb-3 button.btn-primary')
        try:
            page.wait_for_selector('td:text("PantryB")', timeout=2000)
        except Exception:
            print("DEBUG: Page content after Family B add attempt:\n", page.content())
            raise AssertionError("PantryB not found in locations table after add attempt")
        page.wait_for_timeout(500)
        # --- DB DEBUG: Check for PantryB location in DB ---
        if os.path.exists(db_path):
            with sqlite3.connect(db_path) as conn:
                cur = conn.cursor()
                cur.execute("SELECT name FROM location WHERE name=?", ("Pantryb",))
                rows = cur.fetchall()
                print("DEBUG: Locations with name PantryB after add attempt (sqlite):", rows, flush=True)
        try:
            resp = requests.get(f"{base_url}/test/debug-locations")
            debug_data = resp.json()
            print(f"DEBUG: /test/debug-locations after Family B returned: {debug_data}", flush=True)
        except Exception as e:
            print(f"DEBUG: Failed to query /test/debug-locations after Family B: {e}", flush=True)
        # --- UI assertion: Pantryb should be visible in the locations list ---
        content = page.content()
        assert "Pantryb" in content, f"Pantryb not found in page content: {content[:500]}"
        assert "Pantrya" not in content, "User 2 should not see Family A's location"
        page.goto(f"{base_url}/web/inventory")
        assert "Pantryb" in page.content()
        assert "Pantrya" not in page.content(), "User 2 should not see Family A's inventory/location"
        # --- Add Master Item for Family B ---
        page.goto(f"{base_url}/web/master-items")
        page.fill('input[name="name"]', 'BreadB')
        page.click('form.mb-3 button.btn-primary')
        try:
            page.wait_for_selector('a:text("BreadB")', timeout=2000)
        except Exception:
            print("DEBUG: Page content after BreadB add attempt:\n", page.content())
            raise AssertionError("BreadB not found in master items table after add attempt")
        page.wait_for_timeout(500)
        # --- DB DEBUG: Check for BreadB item in DB ---
        if os.path.exists(db_path):
            with sqlite3.connect(db_path) as conn:
                cur = conn.cursor()
                cur.execute("SELECT name FROM master_item WHERE name=?", ("Breadb",))
                rows = cur.fetchall()
                assert any(r[0] == "Breadb" for r in rows), "Breadb not found in DB after add attempt"
        # --- UI assertion: Breadb should be visible in the master items list ---
        content = page.content()
        assert "Breadb" in content, f"Breadb not found in page content: {content[:500]}"
        assert "Breada" not in content, "User 2 should not see Family A's item"
        browser.close()
