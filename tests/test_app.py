"""App-wide behaviour: CSRF, headers, production settings, migrations."""

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from flask_migrate import upgrade

from homeinv import create_app
from homeinv.config import ConfigError
from homeinv.extensions import db

from helpers import PASSWORD


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


def test_old_coolify_variable_names_still_work(monkeypatch):
    """Coolify already has FLASK_SECRET_KEY and MAILJET_SENDER_* from the first version of the app."""
    for name, value in {
        "APP_ENV": "production", "FLASK_SECRET_KEY": "s" * 40, "APP_BASE_URL": "https://inventory.example",
        "MAILJET_API_KEY": "key", "MAILJET_SECRET_KEY": "secret",
        "MAILJET_SENDER_EMAIL": "home@inventory.example", "MAILJET_SENDER_NAME": "Our House",
    }.items():
        monkeypatch.setenv(name, value)
    for name in ("SECRET_KEY", "MAIL_FROM_EMAIL", "MAIL_FROM_NAME"):
        monkeypatch.delenv(name, raising=False)
    app = create_app()
    assert app.config["SECRET_KEY"] == "s" * 40
    assert app.config["MAIL_FROM_EMAIL"] == "home@inventory.example"
    assert app.config["MAIL_FROM_NAME"] == "Our House"


def test_migrations_keep_existing_rows(tmp_path):
    """Changing a table on SQLite rebuilds it; that must never cascade-delete rows elsewhere.

    (It did once: rebuilding the location table deleted every stock row.)
    """
    from flask_migrate import upgrade as upgrade_to

    app = create_app({"APP_ENV": "testing", "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'm.db'}"})
    with app.app_context():
        upgrade_to(revision="43c8a00985f7")  # before nested places
        with db.engine.begin() as conn:
            for sql in (
                "INSERT INTO family (id, name, created_at) VALUES (1, 'F', '2026-01-01')",
                "INSERT INTO location (id, family_id, name, name_key, created_at) VALUES (1, 1, 'Pantry', 'pantry', '2026-01-01')",
                "INSERT INTO item (id, family_id, name, name_key, created_at) VALUES (1, 1, 'Rice', 'rice', '2026-01-01')",
                "INSERT INTO stock (id, family_id, item_id, location_id, quantity, updated_at) VALUES (1, 1, 1, 1, 2.5, '2026-01-01')",
            ):
                conn.exec_driver_sql(sql)
        upgrade_to()
        with db.engine.connect() as conn:
            assert conn.exec_driver_sql("SELECT quantity FROM stock").fetchall() == [(2.5,)]
            assert conn.exec_driver_sql("SELECT name, parent_id FROM location").fetchall() == [("Pantry", None)]
            assert conn.exec_driver_sql("PRAGMA foreign_keys").fetchone() == (1,)
        db.engine.dispose()
