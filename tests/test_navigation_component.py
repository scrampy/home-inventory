import os
import pytest
from playwright.sync_api import expect
import requests
import time

# Set environment variables for testing
os.environ['E2E_TEST'] = '1'
os.environ['TEST_DB_PATH'] = os.path.abspath('test.db')

# Utility for UI tests: setup user and login via test endpoint
def setup_test_user(email, password, family, base_url):
    resp = requests.post(f"{base_url}/test/setup-user", json={
        "email": email,
        "password": password,
        "family": family
    })
    assert resp.status_code == 200
    return resp.json()

# Mock data for API responses
MOCK_LOCATIONS = [
    {"id": 1, "name": "Kitchen", "item_count": 5},
    {"id": 2, "name": "Garage", "item_count": 3},
    {"id": 3, "name": "Bathroom", "item_count": 2}
]
MOCK_SHOPPING_COUNT = 7

# We'll use the flask_server fixture from conftest.py

@pytest.fixture
def authenticated_page(flask_server, page):
    """Setup an authenticated page session."""
    base_url = flask_server
    
    # Setup test user
    setup_test_user("navtest@example.com", "pw1234", "NavTestFamily", base_url)
    
    # Login
    page.goto(f"{base_url}/auth")
    page.fill('#loginEmail', "navtest@example.com")
    page.fill('#loginPassword', "pw1234")
    page.locator('button[type="submit"]:has-text("Login")').click()
    
    # Wait for navigation to complete
    page.wait_for_url(f"{base_url}/family")
    
    # Mock API responses for locations and shopping list count
    def handle_route(route):
        url = route.request.url
        if "/locations" in url:
            route.fulfill(json=MOCK_LOCATIONS)
        elif "/api/shopping-list/count" in url:
            route.fulfill(json={"count": MOCK_SHOPPING_COUNT})
        else:
            route.continue_()
    
    page.route('**/api/**', handle_route)
    page.route('**/locations', handle_route)
    
    # Wait for everything to load
    page.wait_for_timeout(500)
    
    return page

def test_navigation_component_structure(flask_server, authenticated_page):
    """Test the basic structure of the navigation component."""
    page = authenticated_page
    
    # Take a screenshot for debugging
    page.screenshot(path="tests/evidence/navigation_structure.png")
    
    # 1. Verify sidebar exists and is visible
    sidebar = page.locator("#sidebar")
    expect(sidebar).to_be_visible()
    
    # 2. Verify navbar is visible
    navbar = page.locator(".navbar")
    expect(navbar).to_be_visible()
    
    # 3. Verify sidebar toggle button exists
    sidebar_toggle = page.locator("#sidebarToggle")
    expect(sidebar_toggle).to_be_visible()
    
    # 4. Verify main navigation links
    # Home link
    home_link = page.locator(".nav-link:has-text('Home')")
    expect(home_link).to_be_visible()
    
    # Locations dropdown
    locations_link = page.locator(".nav-link:has-text('Locations')")
    expect(locations_link).to_be_visible()
    
    # Shopping List link
    shopping_link = page.locator(".nav-link:has-text('Shopping List')")
    expect(shopping_link).to_be_visible()
    
    # Manage dropdown
    manage_link = page.locator(".nav-link:has-text('Manage')")
    expect(manage_link).to_be_visible()
    
    # 5. Verify user info is displayed in navbar
    user_info = page.locator(".navbar-text:has-text('navtest@example.com')")
    expect(user_info).to_be_visible()
    
    # 6. Verify user section in sidebar
    user_section = sidebar.locator(".nav-link:has-text('navtest@example.com')")
    expect(user_section).to_be_visible()
    
    # 7. Verify logout link
    logout_link = sidebar.locator(".nav-link:has-text('Logout')")
    expect(logout_link).to_be_visible()

def test_navigation_collapsible_sections(flask_server, authenticated_page):
    """Test that collapsible sections work correctly."""
    page = authenticated_page
    
    # Take a screenshot for debugging
    page.screenshot(path="tests/evidence/navigation_collapsible.png")
    
    # 1. Test Locations dropdown
    locations_link = page.locator(".nav-link:has-text('Locations')")
    locations_submenu = page.locator("#locationsSubmenu")
    
    # Check initial state - should be expanded by default (has 'show' class)
    expect(locations_submenu).to_have_class("show")
    
    # Toggle to collapse
    locations_link.click()
    page.wait_for_timeout(300)  # Wait for animation
    
    # Verify submenu is now hidden
    expect(locations_submenu).not_to_have_class("show")
    
    # Toggle again to expand
    locations_link.click()
    page.wait_for_timeout(300)  # Wait for animation
    
    # Verify submenu is visible again
    expect(locations_submenu).to_have_class("show")
    
    # 2. Test Manage dropdown
    manage_link = page.locator(".nav-link:has-text('Manage')")
    manage_submenu = page.locator("#manageSubmenu")
    
    # Check initial state - should be collapsed by default
    expect(manage_submenu).not_to_have_class("show")
    
    # Toggle to expand
    manage_link.click()
    page.wait_for_timeout(300)  # Wait for animation
    
    # Verify manage submenu is now visible
    expect(manage_submenu).to_have_class("show")
    
    # Verify manage submenu has expected items
    expect(manage_submenu.locator(".nav-link:has-text('Aisles')")).to_be_visible()
    expect(manage_submenu.locator(".nav-link:has-text('Stores')")).to_be_visible()
    expect(manage_submenu.locator(".nav-link:has-text('Master Items')")).to_be_visible()
    
    # Toggle again to collapse
    manage_link.click()
    page.wait_for_timeout(300)  # Wait for animation
    
    # Verify submenu is hidden again
    expect(manage_submenu).not_to_have_class("show")

def test_navigation_api_integration(flask_server, authenticated_page):
    """Test that the navigation component loads and displays API data correctly."""
    page = authenticated_page
    
    # Refresh the page to ensure API data is loaded
    page.reload()
    page.wait_for_timeout(500)  # Wait for API calls to complete
    
    # Take a screenshot for evidence
    page.screenshot(path="tests/evidence/navigation_api_integration.png")
    
    # 1. Verify locations are loaded from API
    locations_submenu = page.locator("#locationsSubmenu")
    
    # Make sure locations submenu is visible
    if not locations_submenu.is_visible():
        page.locator(".nav-link:has-text('Locations')").click()
        page.wait_for_timeout(300)  # Wait for animation
    
    # Check if locations are populated (there should be at least one location)
    location_items = locations_submenu.locator("li")
    expect(location_items).to_have_count(3)  # We added 3 mock locations
    
    # Check for specific location names from our mock data
    for location in MOCK_LOCATIONS:
        location_item = locations_submenu.locator(f".nav-link:has-text('{location['name']}')")
        expect(location_item).to_be_visible()
    
    # 2. Verify shopping list count is displayed
    shopping_count = page.locator("#shopping-list-count")
    expect(shopping_count).to_be_visible()
    
    # The count should match our mock data (7 items)
    expect(shopping_count).to_have_text(str(MOCK_SHOPPING_COUNT))

def test_mobile_navigation(flask_server, authenticated_page):
    """Test navigation component on mobile viewport."""
    page = authenticated_page
    
    # 1. Set mobile viewport
    page.set_viewport_size({"width": 375, "height": 812})
    page.wait_for_timeout(500)  # Wait for responsive changes
    
    # Take a screenshot for evidence
    page.screenshot(path="tests/evidence/navigation_mobile.png")
    
    # 2. Verify sidebar toggle is visible on mobile
    sidebar_toggle = page.locator("#sidebarToggle")
    expect(sidebar_toggle).to_be_visible()
    
    # 3. Verify sidebar is initially not active on mobile
    sidebar = page.locator("#sidebar")
    
    # Check if sidebar has 'active' class (which means it's visible on mobile)
    sidebar_has_active = sidebar.evaluate("el => el.classList.contains('active')")
    
    # If sidebar is already active, click toggle to hide it first
    if sidebar_has_active:
        sidebar_toggle.click()
        page.wait_for_timeout(300)  # Wait for animation
    
    # Verify sidebar is not taking up full screen (not active)
    expect(sidebar).not_to_have_class("active")
    
    # 4. Test sidebar toggle functionality
    sidebar_toggle.click()
    page.wait_for_timeout(300)  # Wait for animation
    
    # Verify sidebar is now visible (has active class)
    expect(sidebar).to_have_class("active")
    
    # 5. Test sidebar collapse button
    sidebar_collapse = page.locator("#sidebarCollapse")
    expect(sidebar_collapse).to_be_visible()
    
    # Click collapse button
    sidebar_collapse.click()
    page.wait_for_timeout(300)  # Wait for animation
    
    # Verify sidebar is hidden again
    expect(sidebar).not_to_have_class("active")

def test_unauthenticated_navigation(flask_server, page):
    """Test navigation component when user is not authenticated."""
    # Go to home page without authentication
    base_url = flask_server
    page.goto(f"{base_url}/")
    
    # Take a screenshot for evidence
    page.screenshot(path="tests/evidence/navigation_unauthenticated.png")
    
    # 1. Verify we're redirected to login page
    expect(page).to_have_url(f"{flask_server}/auth")
    
    # 2. Verify login form is visible
    expect(page.locator("#loginEmail")).to_be_visible()
    expect(page.locator("#loginPassword")).to_be_visible()
    
    # 3. Verify navigation shows limited options for unauthenticated users
    sidebar = page.locator("#sidebar")
    expect(sidebar).to_be_visible()
    
    # 4. Verify login link is visible
    expect(sidebar.locator(".nav-link:has-text('Login')")).to_be_visible()
    
    # 5. Verify authenticated-only links are not visible
    expect(sidebar.locator(".nav-link:has-text('Home')")).to_be_hidden()
    expect(sidebar.locator(".nav-link:has-text('Locations')")).to_be_hidden()
    expect(sidebar.locator(".nav-link:has-text('Shopping List')")).to_be_hidden()
    expect(sidebar.locator(".nav-link:has-text('Manage')")).to_be_hidden()
    
    # 6. Verify navbar shows "Guest" for unauthenticated users
    navbar_text = page.locator(".navbar-text")
    expect(navbar_text).to_be_visible()
    expect(navbar_text).to_have_text("Guest")

def test_navigation_links(flask_server, authenticated_page):
    """Test that navigation links work correctly."""
    page = authenticated_page
    base_url = flask_server
    
    # 1. Test Home link
    home_link = page.locator(".nav-link:has-text('Home')").first
    home_link.click()
    page.wait_for_timeout(300)  # Wait for navigation
    expect(page).to_have_url(f"{base_url}/family")
    
    # 2. Test Shopping List link
    shopping_link = page.locator(".nav-link:has-text('Shopping List')").first
    shopping_link.click()
    page.wait_for_timeout(300)  # Wait for navigation
    expect(page).to_have_url(f"{base_url}/web/shopping-list")
    
    # 3. Test a location link
    # First make sure locations submenu is visible
    locations_link = page.locator(".nav-link:has-text('Locations')").first
    locations_submenu = page.locator("#locationsSubmenu")
    if not locations_submenu.is_visible():
        locations_link.click()
        page.wait_for_timeout(300)  # Wait for animation
    
    # Click the first location link
    first_location = locations_submenu.locator("li a").first
    first_location.click()
    page.wait_for_timeout(300)  # Wait for navigation
    # URL should contain inventory and location_id
    expect(page.url).to_contain("/inventory?location_id=")
    
    # 4. Test Manage > Aisles link
    # First make sure manage submenu is visible
    manage_link = page.locator(".nav-link:has-text('Manage')").first
    manage_submenu = page.locator("#manageSubmenu")
    if not manage_submenu.is_visible():
        manage_link.click()
        page.wait_for_timeout(300)  # Wait for animation
    
    # Click the Aisles link
    aisles_link = manage_submenu.locator(".nav-link:has-text('Aisles')")
    aisles_link.click()
    page.wait_for_timeout(300)  # Wait for navigation
    expect(page).to_have_url(f"{base_url}/web/aisles")
    
    # 5. Test Profile link
    profile_link = page.locator(".nav-link:has-text('navtest@example.com')")
    profile_link.click()
    page.wait_for_timeout(300)  # Wait for navigation
    expect(page).to_have_url(f"{base_url}/user/profile")
