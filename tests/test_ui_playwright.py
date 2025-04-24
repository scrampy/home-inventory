import os
os.environ['E2E_TEST'] = '1'
os.environ['TEST_DB_PATH'] = os.path.abspath('test.db')

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

# Start Flask app in a background thread for the test
class FlaskServerThread(threading.Thread):
    def __init__(self):
        super().__init__()
        self.proc = None
        self.logfile = None
        self.port = self._find_free_port()
    def _find_free_port(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            return s.getsockname()[1]
    def run(self):
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        env = os.environ.copy()
        env['FLASK_TESTING'] = '1'
        env['PORT'] = str(self.port)
        rand_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
        self.logfile = os.path.join(project_root, f'flask_server_{rand_suffix}.log')
        python_executable = sys.executable
        flask_app_script = os.path.join(project_root, "app.py")
        print(f"Attempting to start Flask with: {python_executable} {flask_app_script} on port {self.port}")
        print(f"Working directory: {project_root}")
        print(f"Environment keys: {env.keys()}")
        try:
            self.proc = subprocess.Popen(
                [python_executable, flask_app_script],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=project_root,
                env=env,
                text=True
            )
            time.sleep(1)
            self.proc.poll()
            if self.proc.returncode is not None:
                print(f"Flask process exited immediately with code: {self.proc.returncode}")
                stdout, stderr = self.proc.communicate(timeout=5)
                print("--- Flask Subprocess STDOUT ---")
                print(stdout)
                print("--- Flask Subprocess STDERR ---")
                print(stderr)
                print("-------------------------------")
                raise AssertionError("Flask app did not start")
            # Wait for Flask server to start (dynamic port)
            for i in range(20):
                try:
                    with socket.create_connection(("127.0.0.1", self.port), timeout=1):
                        print(f"Flask server started successfully on port {self.port}.")
                        return
                except Exception:
                    time.sleep(0.5)
            print("ERROR: Flask app did not start in time. Printing process output:")
            stdout, stderr = self.proc.communicate(timeout=5)
            print("--- Flask Subprocess STDOUT ---")
            print(stdout)
            print("--- Flask Subprocess STDERR ---")
            print(stderr)
            print("-------------------------------")
            raise AssertionError("Flask app did not start")
        except Exception as e:
            print(f"ERROR: Failed to launch Flask subprocess: {e}")
            raise
    def stop(self):
        if self.proc:
            self.proc.terminate()
            self.proc.wait()

def wait_for_server(url, timeout=10):
    start = time.time()
    while time.time() - start < timeout:
        try:
            r = requests.get(url)
            if r.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(0.5)
    return False

@pytest.fixture(scope="session", autouse=True)
def flask_server():
    server = FlaskServerThread()
    server.start()
    base_url = f"http://localhost:{server.port}"
    assert wait_for_server(f"{base_url}/auth"), "Flask app did not start"
    yield base_url
    server.stop()

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
