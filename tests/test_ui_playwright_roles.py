import pytest
from playwright.sync_api import sync_playwright
import threading
import time
import requests
import subprocess
import os

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

def test_role_management_ui(flask_server):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        try:
            # Admin signup
            page.goto("http://localhost:5000/auth")
            page.wait_for_url("**/auth")
            page.click("#signup-tab")
            page.wait_for_selector("#signupForm", state="visible")
            page.fill("#signupEmail", "admin2@example.com")
            page.fill("#signupPassword", "pw1234")
            page.fill("#signupFamily", "RoleFamUI")
            page.click("#signupForm button[type=submit]")
            page.wait_for_url("**/family")
            # Invite a member via UI only
            page.wait_for_selector("#inviteForm", state="visible")
            page.fill("#inviteEmail", "member2@example.com")
            page.click("#inviteForm button[type=submit]")
            page.wait_for_selector("#inviteMsg:not(.d-none)")
            invite_msg = page.inner_text("#inviteMsg")
            import re
            match = re.search(r'Token: ([\w\.-]+)', invite_msg)
            if not match:
                print('DEBUG inviteMsg:', invite_msg)
                print('DEBUG page content:', page.content())
            assert match, f"Invite token not found in message: {invite_msg}"
            token = match.group(1)
            # Simulate member accepting invite and signing up
            page.goto(f"http://localhost:5000/invite/accept?token={token}")
            page.wait_for_url(f"http://localhost:5000/invite/accept?token={token}")
            page.wait_for_selector("#signupForm", state="visible")
            page.fill("#signupEmail", "member2@example.com")
            page.fill("#signupPassword", "pw1234")
            page.fill("#signupInvite", token)
            page.click("#signupForm button[type=submit]")
            page.wait_for_url("**/family")
            # Logout as member
            page.wait_for_selector("text=Logout")
            page.click("text=Logout")
            page.wait_for_url("**/auth")
            # Login as admin
            page.fill("#loginEmail", "admin2@example.com")
            page.fill("#loginPassword", "pw1234")
            page.click("#loginForm button[type=submit]")
            page.wait_for_url("**/family")
            # Promote member to admin
            page.wait_for_selector(".promote-btn")
            page.click(".promote-btn")
            page.wait_for_timeout(1000)
            assert "Admin" in page.content() or "admin" in page.content()
            # Demote member back to member
            page.wait_for_selector(".demote-btn")
            page.click(".demote-btn")
            page.wait_for_timeout(1000)
            assert "Member" in page.content() or "member" in page.content()
        finally:
            browser.close()
