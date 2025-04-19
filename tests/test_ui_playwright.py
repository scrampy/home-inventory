import pytest
from playwright.sync_api import sync_playwright
import threading
import time
import requests
import subprocess
import os

# Start Flask app in a background thread for the test
class FlaskServerThread(threading.Thread):
    def __init__(self):
        super().__init__()
        self.proc = None
    def run(self):
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        self.proc = subprocess.Popen(["py", "app.py"], cwd=project_root)
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
    assert wait_for_server("http://localhost:5000/auth"), "Flask app did not start"
    yield
    server.stop()

def test_signup_login_invite_flow(flask_server):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        # Go to auth page
        page.goto("http://localhost:5000/auth")
        # Debug: print page content if signup form not found
        try:
            page.click("#signup-tab")
            page.wait_for_selector('#signup.show.active', timeout=10000)
            page.wait_for_selector("#signupForm", state="visible", timeout=10000)
        except Exception as e:
            print("DEBUG: /auth page HTML:\n", page.content())
            page.screenshot(path="playwright_signup_tab_fail.png")
            raise
        page.fill("#signupEmail", "uiadmin@example.com")
        page.fill("#signupPassword", "pw1234")
        page.fill("#signupFamily", "UITestFam")
        page.click("#signupForm button[type=submit]")
        page.wait_for_url("**/family")
        assert "Family Dashboard" in page.content()
        # Invite a user
        page.fill("#inviteEmail", "invitee@example.com")
        page.click("#inviteForm button[type=submit]")
        page.wait_for_selector("#inviteMsg:not(.d-none)")
        assert "Invitation sent" in page.inner_text("#inviteMsg")
        # Logout
        page.click("text=Logout")
        page.wait_for_url("**/auth")
        # Login as admin
        page.fill("#loginEmail", "uiadmin@example.com")
        page.fill("#loginPassword", "pw1234")
        page.click("#loginForm button[type=submit]")
        page.wait_for_url("**/family")
        assert "UITestFam" in page.content()
        browser.close()

def test_base_nav_ui(flask_server):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        # Signup flow
        page.goto("http://localhost:5000/auth")
        page.click("#signup-tab")
        page.fill("#signupEmail", "navui@example.com")
        page.fill("#signupPassword", "pw1234")
        page.fill("#signupFamily", "NavUITestFam")
        page.click("#signupForm button[type=submit]")
        page.wait_for_url("**/family")
        # Check navbar after login
        assert "Logged in as navui@example.com" in page.content()
        assert "Profile" in page.content()
        assert "Logout" in page.content()
        # Logout
        page.click("text=Logout")
        page.wait_for_url("**/auth")
        # Check navbar after logout
        page.goto("http://localhost:5000/web/locations")
        assert "Login" in page.content()
        assert "Logged in as" not in page.content()
        assert "Logout" not in page.content()
        browser.close()
