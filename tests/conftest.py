import re

import pytest
from flask.testing import FlaskClient
from sqlalchemy import select

from homeinv import create_app
from homeinv.extensions import db
from homeinv.models import User

PASSWORD = "correct-horse-1"


class FreshContextClient(FlaskClient):
    """Gives every request its own app context, as in production.

    Tests hold an app context open so they can query the database. Without this,
    requests would reuse it and share `flask.g`, where Flask-Login caches the
    signed-in user, so two "browsers" would see each other's logins.
    """

    def open(self, *args, **kwargs):
        with self.application.app_context():
            response = super().open(*args, **kwargs)
        db.session.expire_all()  # see what the request wrote
        return response


@pytest.fixture
def app():
    app = create_app({"APP_ENV": "testing", "WTF_CSRF_ENABLED": False})
    app.test_client_class = FreshContextClient
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def new_client(app):
    """Another browser: a separate cookie jar for a second user."""
    return app.test_client


@pytest.fixture
def outbox(app):
    return app.extensions["email_backend"].outbox


def signup(client, email, password=PASSWORD, name="", family_name="", invite=None):
    data = {"email": email, "password": password, "confirm": password, "name": name,
            "family_name": family_name}
    url = "/signup"
    if invite:
        data["invite"] = invite
        url += f"?invite={invite}"
    return client.post(url, data=data, follow_redirects=True)


def login(client, email, password=PASSWORD, next_url=None):
    url = "/login" + (f"?next={next_url}" if next_url else "")
    return client.post(url, data={"email": email, "password": password}, follow_redirects=True)


def logout(client):
    return client.post("/logout", follow_redirects=True)


def user(email):
    return db.session.scalar(select(User).filter_by(email=email))


def link_path(message):
    """The path of the first app link in an email (the test base URL is stripped)."""
    match = re.search(r"http://testserver\.local(/\S+)", message.text)
    assert match, f"no link in email: {message.text}"
    return match.group(1)


def invite(client, email):
    return client.post("/family/invite", data={"email": email}, follow_redirects=True)
