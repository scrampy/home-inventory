import pytest
from playwright.sync_api import sync_playwright
import os
import socket
import sqlite3
from urllib.parse import urljoin
from .screenshot_utils import save_screenshot_with_timestamp

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

def print_db_path():
    db_path = os.path.abspath('test.db')
    print(f"DEBUG: test_ui_playwright_roles.py using DB path: {db_path}")
    return db_path

def test_role_management_ui(flask_server):
    debug_port_5000_state("Test start")
    import requests
    import sqlite3
    db_path = print_db_path()
    def debug_list_users(phase):
        try:
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            cur.execute("SELECT id, email FROM user")
            users = cur.fetchall()
            print(f"DEBUG: Users in DB ({phase}):", users, flush=True)
            conn.close()
        except Exception as e:
            print(f"DEBUG: Exception in debug_list_users: {e}", flush=True)

    # List users before signup UI
    debug_list_users("before signup UI")
    base_url = flask_server
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        try:
            debug_port_5000_state("Before admin signup")
            # List users before admin signup via UI
            debug_list_users("before admin signup UI")
            # Admin signup
            page.goto(urljoin(base_url, "/auth"))
            page.wait_for_selector("#signup-tab", state="visible")
            page.click("#signup-tab")
            page.wait_for_selector("#signup", state="visible")
            page.wait_for_selector("#signupForm", state="visible")
            # Print signup tab visibility and display style
            signup_tab_visible = page.is_visible("#signup")
            print('DEBUG: #signup tab is_visible:', signup_tab_visible, flush=True)
            signup_tab_display = page.evaluate("window.getComputedStyle(document.querySelector('#signup')).display")
            print('DEBUG: #signup tab display style:', signup_tab_display, flush=True)
            print('DEBUG: FULL PAGE HTML before field interaction:', page.content(), flush=True)
            # Ensure fields are editable BEFORE filling
            page.wait_for_selector("#signupEmail:enabled")
            page.wait_for_selector("#signupPassword:enabled")
            page.wait_for_selector("#signupFamilyName:enabled")
            signup_email_editable = page.is_editable("#signupEmail")
            signup_password_editable = page.is_editable("#signupPassword")
            signup_family_editable = page.is_editable("#signupFamilyName")
            print('DEBUG: signupEmail editable:', signup_email_editable, flush=True)
            print('DEBUG: signupPassword editable:', signup_password_editable, flush=True)
            print('DEBUG: signupFamily editable:', signup_family_editable, flush=True)
            assert signup_email_editable, 'signupEmail field is not editable!'
            assert signup_password_editable, 'signupPassword field is not editable!'
            assert signup_family_editable, 'signupFamily field is not editable!'
            debug_list_users("before admin signup form submit")
            save_screenshot_with_timestamp(page, "/app/debug_signup_before_fill.png")
            # Immediately fill fields after editability check, using force=True
            page.fill("#signupEmail", "admin2@example.com", force=True)
            page.fill("#signupPassword", "pw1234", force=True)
            page.fill("#signupFamilyName", "RoleFamUI", force=True)
            # Collect browser console logs before submit
            logs = page.evaluate("window._collectedLogs || []")
            print('DEBUG: browser console logs before submit:', logs, flush=True)
            page.click("#signupForm button[type=submit]")
            # Wait for navigation or error
            try:
                page.wait_for_url(urljoin(base_url, "**/family"), timeout=5000)
            except Exception:
                print('DEBUG signup page content:', page.content(), flush=True)
                print('DEBUG signup error text:', page.inner_text("#signupError"), flush=True)
                import sqlite3
                import os as _os
                db_path = _os.path.join(_os.path.dirname(__file__), '../instance/test.db')
                if _os.path.exists(db_path):
                    with sqlite3.connect(db_path) as conn:
                        cur = conn.cursor()
                        cur.execute("SELECT email FROM user WHERE email=?", ("admin2@example.com",))
                        rows = cur.fetchall()
                        print('DEBUG: admin2@example.com in DB after failed signup:', rows, flush=True)
                else:
                    print("DEBUG: test.db does not exist after signup", flush=True)
                raise
            page.wait_for_selector("#inviteForm", state="visible")
            save_screenshot_with_timestamp(page, "tests/evidence/role_ui_admin_signup_success.png")
            page.fill("#inviteEmail", "member2@example.com", force=True)
            page.click("#inviteForm button[type=submit]")
            page.wait_for_selector("#inviteMsg:not(.d-none)")
            invite_msg = page.inner_text("#inviteMsg")
            save_screenshot_with_timestamp(page, "tests/evidence/role_ui_invite_token_displayed.png")
            import re
            match = re.search(r'Token: ([\w\.-]+)', invite_msg)
            if not match:
                print('DEBUG page content:', page.content())
            assert match, f"Invite token not found in message: {invite_msg}"
            token = match.group(1)
            debug_port_5000_state("After invite token")
            # Simulate member accepting invite and signing up
            page.goto(urljoin(base_url, f"/invite/accept?token={token}"))
            page.wait_for_url(urljoin(base_url, f"/invite/accept?token={token}"))
            page.wait_for_selector("#signup-tab", state="visible")
            page.click("#signup-tab")
            page.wait_for_selector("#signup", state="visible")
            page.wait_for_selector("#signupForm", state="visible")
            page.wait_for_selector("#signupEmail:enabled")
            page.wait_for_selector("#signupPassword:enabled")
            page.wait_for_selector("#signupInvite:enabled")
            page.fill("#signupEmail", "member2@example.com", force=True)
            page.fill("#signupPassword", "pw1234", force=True)
            page.fill("#signupInvite", token, force=True)
            page.click("#signupForm button[type=submit]")
            page.wait_for_url(urljoin(base_url, "**/family"), timeout=5000)
            save_screenshot_with_timestamp(page, "tests/evidence/role_ui_member_signup_success.png")
            debug_port_5000_state("After member signup")
            page.wait_for_selector("text=Logout", state="visible")
            page.click("text=Logout")
            page.wait_for_url(urljoin(base_url, "**/auth"), timeout=5000)
            # Login as admin
            page.wait_for_selector("#loginEmail:enabled")
            page.fill("#loginEmail", "admin2@example.com", force=True)
            page.wait_for_selector("#loginPassword:enabled")
            page.fill("#loginPassword", "pw1234", force=True)
            page.click("#loginForm button[type=submit]")
            page.wait_for_url(urljoin(base_url, "**/family"), timeout=5000)
            save_screenshot_with_timestamp(page, "tests/evidence/role_ui_admin_relogin_success.png")
            debug_port_5000_state("After admin re-login")
            page.wait_for_selector(".promote-btn", state="visible")
            page.click(".promote-btn")
            assert "Admin" in page.content() or "admin" in page.content()
            save_screenshot_with_timestamp(page, "tests/evidence/role_ui_member_promoted_to_admin.png")
            page.wait_for_selector(".demote-btn", state="visible")
            page.click(".demote-btn")
            assert "Member" in page.content() or "member" in page.content()
            save_screenshot_with_timestamp(page, "tests/evidence/role_ui_member_demoted_to_member.png")
        finally:
            browser.close()
            debug_port_5000_state("Test end")
