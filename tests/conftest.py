import pytest
from flask.testing import FlaskClient

from homeinv import create_app
from homeinv.extensions import db


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
