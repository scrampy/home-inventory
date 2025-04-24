import pytest
from playwright.sync_api import sync_playwright
import threading
import time
import requests
import subprocess
import os
import socket

class FlaskServerThread(threading.Thread):
    def __init__(self):
        super().__init__()
        self.proc = None
    def run(self):
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        env = os.environ.copy()
        env['FLASK_TESTING'] = '1'
        self.proc = subprocess.Popen(["python", "app.py"], cwd=project_root, env=env)
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

def debug_port_5000_state(phase):
    print(f"[DEBUG] {phase}: Checking port 5000...")
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", 5000))
        print(f"[DEBUG] {phase}: Port 5000 is FREE.")
        s.close()
    except OSError as e:
        print(f"[DEBUG] {phase}: Port 5000 is IN USE: {e}")
    finally:
        s.close()

@pytest.fixture(scope="session", autouse=True)
def flask_server():
    debug_port_5000_state("Before server start")
    server = FlaskServerThread()
    server.start()
    debug_port_5000_state("After server start")
    assert wait_for_server("http://localhost:5000/auth"), "Flask app did not start"
    yield
    server.stop()
    debug_port_5000_state("After server stop")

def test_role_management_ui(flask_server):
    debug_port_5000_state("Test start")
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        try:
            debug_port_5000_state("Before admin signup")
            # DEBUG: Check if user already exists before signup
            import sqlite3
            import os as _os
            db_path = _os.path.join(_os.path.dirname(__file__), '../instance/test.db')
            if _os.path.exists(db_path):
                with sqlite3.connect(db_path) as conn:
                    cur = conn.cursor()
                    cur.execute("SELECT email FROM user WHERE email=?", ("admin2@example.com",))
                    rows = cur.fetchall()
                    print("DEBUG: Users with email admin2@example.com before signup:", rows)
            else:
                print("DEBUG: test.db does not exist before signup")
            # Admin signup
            page.goto("http://localhost:5000/auth")
            page.wait_for_timeout(2000)
            page.click("#signup-tab")
            page.wait_for_timeout(2000)
            page.wait_for_selector("#signup", state="visible")
            page.wait_for_timeout(2000)
            page.wait_for_selector("#signupForm", state="visible")
            page.wait_for_timeout(2000)
            # Print signup tab visibility and display style
            signup_tab_visible = page.is_visible("#signup")
            print('DEBUG: #signup tab is_visible:', signup_tab_visible, flush=True)
            signup_tab_display = page.evaluate("window.getComputedStyle(document.querySelector('#signup')).display")
            print('DEBUG: #signup tab display style:', signup_tab_display, flush=True)
            # Print full page content before interacting with fields
            print('DEBUG: FULL PAGE HTML before field interaction:', page.content(), flush=True)
            page.wait_for_timeout(2000)
            # Wait for any tab transitions/animations to finish
            page.wait_for_timeout(2000)
            # Ensure fields are editable BEFORE filling
            signup_email_editable = page.is_editable("#signupEmail")
            signup_password_editable = page.is_editable("#signupPassword")
            signup_family_editable = page.is_editable("#signupFamily")
            print('DEBUG: signupEmail editable:', signup_email_editable, flush=True)
            print('DEBUG: signupPassword editable:', signup_password_editable, flush=True)
            print('DEBUG: signupFamily editable:', signup_family_editable, flush=True)
            assert signup_email_editable, 'signupEmail field is not editable!'
            assert signup_password_editable, 'signupPassword field is not editable!'
            assert signup_family_editable, 'signupFamily field is not editable!'
            page.wait_for_timeout(2000)
            # Take screenshot before fill
            page.screenshot(path="/app/debug_signup_before_fill.png")
            page.wait_for_timeout(2000)
            # Immediately fill fields after editability check, using force=True
            page.fill("#signupEmail", "admin2@example.com", force=True)
            page.wait_for_timeout(2000)
            page.fill("#signupPassword", "pw1234", force=True)
            page.wait_for_timeout(2000)
            page.fill("#signupFamily", "RoleFamUI", force=True)
            page.wait_for_timeout(2000)
            # Collect browser console logs before submit
            logs = page.evaluate("window._collectedLogs || []")
            print('DEBUG: browser console logs before submit:', logs, flush=True)
            page.click("#signupForm button[type=submit]")
            page.wait_for_timeout(2000)
            # Collect browser console logs after submit
            logs = page.evaluate("window._collectedLogs || []")
            print('DEBUG: browser console logs after submit:', logs, flush=True)
            try:
                page.wait_for_url("**/family", timeout=15000)
            except Exception:
                print('DEBUG signup page content:', page.content(), flush=True)
                print('DEBUG signup error text:', page.inner_text("#signupError"), flush=True)
                # DEBUG: Check if user now exists after failed signup
                import sqlite3
                import os as _os
                db_path = _os.path.join(_os.path.dirname(__file__), '../instance/test.db')
                if _os.path.exists(db_path):
                    with sqlite3.connect(db_path) as conn:
                        cur = conn.cursor()
                        cur.execute("SELECT email FROM user WHERE email=?", ("admin2@example.com",))
                        rows = cur.fetchall()
                        print("DEBUG: Users with email admin2@example.com after signup:", rows, flush=True)
                else:
                    print("DEBUG: test.db does not exist after signup", flush=True)
                raise
            page.wait_for_timeout(2000)
            debug_port_5000_state("After admin signup")
            page.wait_for_timeout(2000)
            # Invite a member via UI only
            page.wait_for_selector("#inviteForm", state="visible")
            page.wait_for_timeout(2000)
            page.fill("#inviteEmail", "member2@example.com", force=True)
            page.wait_for_timeout(2000)
            page.click("#inviteForm button[type=submit]")
            page.wait_for_timeout(2000)
            page.wait_for_selector("#inviteMsg:not(.d-none)")
            page.wait_for_timeout(2000)
            invite_msg = page.inner_text("#inviteMsg")
            import re
            match = re.search(r'Token: ([\w\.-]+)', invite_msg)
            if not match:
                print('DEBUG inviteMsg:', invite_msg)
                print('DEBUG page content:', page.content())
            assert match, f"Invite token not found in message: {invite_msg}"
            token = match.group(1)
            page.wait_for_timeout(2000)
            debug_port_5000_state("After invite token")
            page.wait_for_timeout(2000)
            # Simulate member accepting invite and signing up
            page.goto(f"http://localhost:5000/invite/accept?token={token}")
            page.wait_for_timeout(2000)
            page.wait_for_url(f"http://localhost:5000/invite/accept?token={token}")
            page.wait_for_timeout(2000)
            page.click("#signup-tab")
            page.wait_for_timeout(2000)
            page.wait_for_selector("#signup", state="visible")
            page.wait_for_timeout(2000)
            page.wait_for_selector("#signupForm", state="visible")
            page.wait_for_timeout(2000)
            page.fill("#signupEmail", "member2@example.com", force=True)
            page.wait_for_timeout(2000)
            page.fill("#signupPassword", "pw1234", force=True)
            page.wait_for_timeout(2000)
            page.fill("#signupInvite", token, force=True)
            page.wait_for_timeout(2000)
            page.click("#signupForm button[type=submit]")
            page.wait_for_timeout(2000)
            page.wait_for_url("**/family")
            page.wait_for_timeout(2000)
            debug_port_5000_state("After member signup")
            page.wait_for_timeout(2000)
            page.click("text=Logout")
            page.wait_for_timeout(2000)
            page.wait_for_url("**/auth")
            page.wait_for_timeout(2000)
            # Login as admin
            page.fill("#loginEmail", "admin2@example.com", force=True)
            page.wait_for_timeout(2000)
            page.fill("#loginPassword", "pw1234", force=True)
            page.wait_for_timeout(2000)
            page.click("#loginForm button[type=submit]")
            page.wait_for_timeout(2000)
            page.wait_for_url("**/family")
            page.wait_for_timeout(2000)
            debug_port_5000_state("After admin re-login")
            page.wait_for_timeout(2000)
            # Promote member to admin
            page.wait_for_selector(".promote-btn")
            page.wait_for_timeout(2000)
            page.click(".promote-btn")
            page.wait_for_timeout(2000)
            assert "Admin" in page.content() or "admin" in page.content()
            page.wait_for_timeout(2000)
            # Demote member back to member
            page.wait_for_selector(".demote-btn")
            page.wait_for_timeout(2000)
            page.click(".demote-btn")
            page.wait_for_timeout(2000)
            assert "Member" in page.content() or "member" in page.content()
            page.wait_for_timeout(2000)
        finally:
            browser.close()
            debug_port_5000_state("Test end")
