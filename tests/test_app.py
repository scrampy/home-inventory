"""App-wide behaviour: CSRF, headers, production settings, migrations."""

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from flask_migrate import upgrade

from homeinv import create_app
from homeinv.config import ConfigError
from homeinv.extensions import db

from conftest import PASSWORD


def test_forms_reject_posts_without_csrf_token():
    app = create_app({"APP_ENV": "testing"})  # CSRF on
    with app.app_context():
        db.create_all()
        client = app.test_client()
        resp = client.post("/signup", data={"email": "a@example.com", "password": PASSWORD, "confirm": PASSWORD})
        assert resp.status_code == 400
        assert b"Form expired" in resp.data

        page = client.get("/signup").data.decode()
        token = page.split('name="csrf_token" type="hidden" value="')[1].split('"')[0]
        resp = client.post("/signup", data={"csrf_token": token, "email": "a@example.com",
                                            "password": PASSWORD, "confirm": PASSWORD})
        assert resp.status_code == 302
        db.drop_all()


def test_security_headers(client):
    resp = client.get("/login")
    assert resp.headers["X-Frame-Options"] == "DENY"
    assert resp.headers["X-Content-Type-Options"] == "nosniff"


def test_healthz(client):
    assert client.get("/healthz").get_json() == {"status": "ok"}


def test_no_test_or_debug_routes(app):
    rules = [r.rule for r in app.url_map.iter_rules()]
    assert not [r for r in rules if r.startswith(("/test", "/debug", "/seed"))]


@pytest.mark.parametrize("missing", ["SECRET_KEY", "APP_BASE_URL", "MAILJET_API_KEY"])
def test_production_refuses_to_start_without_settings(missing):
    settings = {
        "APP_ENV": "production",
        "SECRET_KEY": "x" * 40,
        "APP_BASE_URL": "https://inventory.example",
        "MAILJET_API_KEY": "key",
        "MAILJET_SECRET_KEY": "secret",
        "MAIL_FROM_EMAIL": "home@inventory.example",
    }
    settings[missing] = None
    with pytest.raises(ConfigError, match=missing):
        create_app(settings)


def test_production_cookies_are_secure():
    app = create_app({
        "APP_ENV": "production", "SECRET_KEY": "x" * 40, "APP_BASE_URL": "https://inventory.example",
        "MAILJET_API_KEY": "key", "MAILJET_SECRET_KEY": "secret", "MAIL_FROM_EMAIL": "home@inventory.example",
    })
    assert app.config["SESSION_COOKIE_SECURE"] and app.config["REMEMBER_COOKIE_SECURE"]


def test_migrations_match_models(tmp_path):
    """Running every migration on an empty database gives exactly the schema the models describe."""
    app = create_app({"APP_ENV": "testing", "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'm.db'}"})
    with app.app_context():
        upgrade()
        with db.engine.connect() as conn:
            diff = compare_metadata(MigrationContext.configure(conn), db.metadata)
        assert diff == []
        db.engine.dispose()


def test_rate_limit_on_login():
    app = create_app({"APP_ENV": "testing", "WTF_CSRF_ENABLED": False, "RATELIMIT_ENABLED": True})
    with app.app_context():
        db.create_all()
        client = app.test_client()
        codes = [client.post("/login", data={"email": "a@example.com", "password": "x"}).status_code
                 for _ in range(11)]
        assert codes[:10] == [200] * 10 and codes[10] == 429
        db.drop_all()
