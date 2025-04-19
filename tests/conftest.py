import os
import pytest
from app import db, app

@pytest.fixture(scope='session', autouse=True)
def setup_e2e_db():
    # Use persistent test DB for E2E
    os.environ['E2E_TEST'] = '1'
    with app.app_context():
        db.drop_all()
        db.create_all()
    yield
    # Clean up test DB after session
    try:
        os.remove('test.db')
    except Exception:
        pass
