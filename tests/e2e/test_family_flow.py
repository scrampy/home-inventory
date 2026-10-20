"""Browser test of the main phase-1 flow. Run with: pytest -m e2e --browser-channel msedge"""

import threading

import pytest
from playwright.sync_api import expect
from werkzeug.serving import make_server

from homeinv import create_app
from homeinv.extensions import db

pytestmark = pytest.mark.e2e

PASSWORD = "correct-horse-1"
PHONE = {"width": 375, "height": 812}


@pytest.fixture
def live_app(tmp_path):
    app = create_app({
        "APP_ENV": "testing",
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'e2e.db'}",
    })
    with app.app_context():
        db.create_all()
    server = make_server("127.0.0.1", 0, app, threaded=True)
    app.config["APP_BASE_URL"] = f"http://127.0.0.1:{server.server_port}"
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield app
    server.shutdown()
    with app.app_context():
        db.engine.dispose()


def fill_signup(page, name, email=None, family=None):
    page.get_by_label("Your name").fill(name)
    if email:
        page.get_by_label("Email").fill(email)
    page.get_by_label("Password", exact=True).fill(PASSWORD)
    page.get_by_label("Confirm password").fill(PASSWORD)
    if family:
        page.get_by_label("Family name").fill(family)
    page.get_by_role("button", name="Create account").click()


def assert_fits_phone(page):
    overflow = page.evaluate("document.documentElement.scrollWidth - window.innerWidth")
    assert overflow <= 0, f"{page.url} scrolls sideways by {overflow}px"


def test_invite_join_and_promote(live_app, browser):
    base = live_app.config["APP_BASE_URL"]
    outbox = live_app.extensions["email_backend"].outbox

    ann = browser.new_context(viewport=PHONE).new_page()
    ann.goto(base + "/")
    expect(ann.get_by_role("heading", name="Log in")).to_be_visible()
    assert_fits_phone(ann)
    ann.get_by_role("link", name="Create an account").click()
    assert_fits_phone(ann)
    fill_signup(ann, "Ann Smith", "ann@example.com", "The Smiths")
    expect(ann.get_by_role("heading", name="The Smiths")).to_be_visible()

    ann.get_by_label("Email to invite").fill("bob@example.com")
    ann.get_by_role("button", name="Send invite").click()
    expect(ann.get_by_text("Invitation sent to bob@example.com")).to_be_visible()
    expect(ann.get_by_test_id("pending-invite")).to_have_count(1)
    assert_fits_phone(ann)
    link = ann.locator("#invite-link").input_value()
    assert outbox[-1].to == "bob@example.com" and link in outbox[-1].text

    bob = browser.new_context(viewport=PHONE).new_page()
    bob.goto(link)
    bob.get_by_role("link", name="Create an account to join").click()
    expect(bob.get_by_label("Email")).to_have_value("bob@example.com")
    fill_signup(bob, "Bob Jones")
    expect(bob.get_by_text("You're in The Smiths")).to_be_visible()
    expect(bob.get_by_test_id("member")).to_have_count(2)
    # Members don't see admin controls.
    expect(bob.get_by_role("button", name="Send invite")).to_have_count(0)

    ann.reload()
    expect(ann.get_by_test_id("member")).to_have_count(2)
    expect(ann.get_by_test_id("pending-invite")).to_have_count(0)
    ann.get_by_role("button", name="Make admin").click()
    expect(ann.get_by_text("Bob Jones is now an admin")).to_be_visible()

    bob.reload()
    expect(bob.get_by_role("button", name="Send invite")).to_be_visible()

    # Logging out works from the collapsed phone menu.
    bob.get_by_role("button", name="Menu").click()
    bob.get_by_role("button", name="Log out").click()
    expect(bob.get_by_text("You've logged out.")).to_be_visible()
