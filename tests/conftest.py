import os
import sys
import pytest
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))
from app import db, app

@pytest.fixture(scope="session", autouse=True)
def ensure_db_created():
    with app.app_context():
        db.create_all()
    yield

@pytest.fixture(scope='session', autouse=True)
def setup_e2e_db():
    # Use persistent test DB for E2E
    os.environ['E2E_TEST'] = '1'
    with app.app_context():
        db.drop_all()
    yield
    # Clean up test DB after session
    try:
        os.remove(os.path.join(os.path.dirname(__file__), '../instance/test.db'))
        print('DEBUG: test.db deleted after session', flush=True)
    except Exception as e:
        print(f'DEBUG: Failed to delete test.db: {e}', flush=True)
