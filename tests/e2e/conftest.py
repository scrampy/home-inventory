"""Browser tests run against a real server on a free port."""

import threading

import pytest
from werkzeug.serving import make_server

from homeinv import create_app
from homeinv.extensions import db


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
