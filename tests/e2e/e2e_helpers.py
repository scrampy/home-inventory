PASSWORD = "correct-horse-1"
PHONE = {"width": 375, "height": 812}


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


def open_menu(page, link_name):
    """Use the collapsed phone menu to reach a page."""
    page.get_by_role("button", name="Menu").click()
    page.get_by_role("link", name=link_name, exact=True).click()
