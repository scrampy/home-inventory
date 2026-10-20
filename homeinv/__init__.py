import logging
import os

from flask import Flask, render_template, request
from flask_wtf.csrf import CSRFError
from sqlalchemy import event
from sqlalchemy.engine import Engine
from werkzeug.middleware.proxy_fix import ProxyFix

from .config import load_config
from .email import init_email
from .extensions import csrf, db, limiter, login_manager, migrate


@event.listens_for(Engine, "connect")
def _sqlite_pragmas(dbapi_connection, connection_record):
    # SQLite ignores foreign keys unless asked; WAL lets reads continue during writes.
    if type(dbapi_connection).__module__.startswith("sqlite3"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()


def _active_tab(endpoint):
    """Which bottom tab a page belongs to."""
    area = endpoint.split(".")[0]
    if area in ("find",) or endpoint in ("catalog.item",):
        return "find"
    if area in ("places", "inventory"):
        return "places"
    if area == "shopping":
        return "list"
    return "more"


def create_app(overrides=None):
    app = Flask(__name__, instance_relative_config=True)
    os.makedirs(app.instance_path, exist_ok=True)
    app.config.from_mapping(load_config(app.instance_path, overrides))

    if app.config["APP_ENV"] != "testing":
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    # Trust X-Forwarded-For only, to rate-limit by the visitor's real IP. Host and
    # scheme aren't needed: email links come from APP_BASE_URL and redirects are relative.
    hops = app.config["PROXY_HOPS"]
    if hops:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=hops, x_proto=0, x_host=0)

    db.init_app(app)
    migrations_dir = os.path.join(os.path.dirname(app.root_path), "migrations")
    migrate.init_app(app, db, directory=migrations_dir, render_as_batch=True)
    csrf.init_app(app)
    limiter.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please log in to continue."
    login_manager.login_message_category = "info"
    init_email(app)

    from .models import User

    @login_manager.user_loader
    def load_user(session_id):
        return User.from_session_id(session_id)

    from .auth import bp as auth_bp
    from .catalog import bp as catalog_bp
    from .family import bp as family_bp
    from .find import bp as find_bp
    from .inventory import bp as inventory_bp
    from .main import bp as main_bp
    from .places import bp as places_bp
    from .shopping import bp as shopping_bp

    for blueprint in (main_bp, auth_bp, family_bp, find_bp, places_bp, catalog_bp, inventory_bp, shopping_bp):
        app.register_blueprint(blueprint)

    from . import cli
    from .security import current_membership

    cli.register(app)
    app.jinja_env.globals["current_membership"] = current_membership

    @app.context_processor
    def list_badge():
        # Number of things still to get, for the List tab. Only when someone is in a family.
        def count():
            from .shopping import open_count
            return open_count() if current_membership() else 0
        return {"list_badge": count, "active_tab": _active_tab(request.endpoint or "")}

    @app.after_request
    def security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        return response

    def error_page(status, title, message):
        return render_template("error.html", title=title, message=message), status

    @app.errorhandler(CSRFError)
    def csrf_error(e):
        return error_page(400, "Form expired", "The form was open too long or came from another site. Go back, refresh, and try again.")

    @app.errorhandler(403)
    def forbidden(e):
        return error_page(403, "Not allowed", "You don't have permission to do that.")

    @app.errorhandler(404)
    def not_found(e):
        return error_page(404, "Not found", "That page doesn't exist.")

    @app.errorhandler(429)
    def too_many(e):
        return error_page(429, "Slow down", "Too many attempts. Wait a few minutes and try again.")

    return app
