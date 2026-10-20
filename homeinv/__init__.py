import logging
import os

from flask import Flask, render_template
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
    from .main import bp as main_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(family_bp)
    app.register_blueprint(catalog_bp)

    from .security import current_membership

    app.jinja_env.globals["current_membership"] = current_membership

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
