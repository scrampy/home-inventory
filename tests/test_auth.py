import pytest
from app import app, db, User
from flask_login import logout_user

def setup_module(module):
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    with app.app_context():
        db.create_all()

def teardown_module(module):
    with app.app_context():
        db.drop_all()

@pytest.fixture
def client():
    with app.test_client() as client:
        yield client

# --- Registration ---
def test_signup_success(client):
    rv = client.post('/signup', json={'email': 'test1@example.com', 'password': 'pw123'})
    assert rv.status_code == 200
    data = rv.get_json()
    assert data['success'] is True
    assert 'user_id' in data
    # User exists in DB
    with app.app_context():
        user = User.query.filter_by(email='test1@example.com').first()
        assert user is not None

def test_signup_duplicate(client):
    client.post('/signup', json={'email': 'dup@example.com', 'password': 'pw123'})
    rv = client.post('/signup', json={'email': 'dup@example.com', 'password': 'pw123'})
    assert rv.status_code == 400
    assert 'already registered' in rv.get_json()['error']

def test_signup_missing_fields(client):
    rv = client.post('/signup', json={'email': '', 'password': ''})
    assert rv.status_code == 400
    assert 'required' in rv.get_json()['error']

# --- Login ---
def test_login_success(client):
    client.post('/signup', json={'email': 'login@example.com', 'password': 'pw123'})
    rv = client.post('/login', json={'email': 'login@example.com', 'password': 'pw123'})
    assert rv.status_code == 200
    assert rv.get_json()['success'] is True

def test_login_invalid(client):
    rv = client.post('/login', json={'email': 'bad@example.com', 'password': 'pw123'})
    assert rv.status_code == 401
    assert 'Invalid credentials' in rv.get_json()['error']

# --- Logout ---
def test_logout(client):
    client.post('/signup', json={'email': 'logout@example.com', 'password': 'pw123'})
    rv = client.post('/logout')
    # Should require login, so expect 401 (because login_required)
    assert rv.status_code in (200, 401)
