import pytest

from helpers import FreshContextClient
from homeinv import create_app
from homeinv.extensions import db


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
