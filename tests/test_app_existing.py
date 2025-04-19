import pytest
from app import app, db, Location, Aisle, Store, MasterItem, Inventory, ShoppingListItem

def setup_module(module):
    # Use a test DB file so as not to interfere with dev DB
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['TESTING'] = True
    with app.app_context():
        db.create_all()

def teardown_module(module):
    with app.app_context():
        db.drop_all()

@pytest.fixture
def client():
    with app.test_client() as client:
        yield client

# --- Location CRUD ---
def test_create_location(client):
    with app.app_context():
        loc = Location(name='Test Pantry')
        db.session.add(loc)
        db.session.commit()
        assert loc.id is not None
        assert Location.query.filter_by(name='Test Pantry').first() is not None

def test_location_api(client):
    # POST
    rv = client.post('/locations', json={'name': 'API Pantry'})
    assert rv.status_code == 201
    # GET
    rv = client.get('/locations')
    assert rv.status_code == 200
    assert any(l['name'] == 'API Pantry' for l in rv.get_json())

# --- Aisle CRUD ---
def test_create_aisle(client):
    with app.app_context():
        aisle = Aisle(name='Test Aisle')
        db.session.add(aisle)
        db.session.commit()
        assert aisle.id is not None
        assert Aisle.query.filter_by(name='Test Aisle').first() is not None

def test_aisle_api(client):
    rv = client.post('/aisles', json={'name': 'API Aisle'})
    assert rv.status_code == 201
    rv = client.get('/aisles')
    assert rv.status_code == 200
    assert any(a['name'] == 'API Aisle' for a in rv.get_json())

# --- Store CRUD ---
def test_create_store(client):
    with app.app_context():
        store = Store(name='Test Store')
        db.session.add(store)
        db.session.commit()
        assert store.id is not None
        assert Store.query.filter_by(name='Test Store').first() is not None

def test_store_api(client):
    rv = client.post('/stores', json={'name': 'API Store'})
    assert rv.status_code == 201
    rv = client.get('/stores')
    assert rv.status_code == 200
    assert any(s['name'] == 'API Store' for s in rv.get_json())

# --- MasterItem CRUD ---
def test_create_master_item(client):
    with app.app_context():
        item = MasterItem(name='Test Item')
        db.session.add(item)
        db.session.commit()
        assert item.id is not None
        assert MasterItem.query.filter_by(name='Test Item').first() is not None

def test_master_item_api(client):
    rv = client.post('/master-items', json={'name': 'API Item'})
    assert rv.status_code == 201
    rv = client.get('/master-items')
    assert rv.status_code == 200
    assert any(i['name'] == 'API Item' for i in rv.get_json())

# --- Inventory CRUD ---
def test_create_inventory(client):
    with app.app_context():
        item = MasterItem(name='Inv Item')
        loc = Location(name='Inv Loc')
        db.session.add_all([item, loc])
        db.session.commit()
        inv = Inventory(master_item_id=item.id, location_id=loc.id, quantity=2)
        db.session.add(inv)
        db.session.commit()
        assert inv.id is not None
        assert Inventory.query.filter_by(master_item_id=item.id, location_id=loc.id).first() is not None

def test_inventory_api(client):
    with app.app_context():
        item = MasterItem(name='API Inv Item')
        loc = Location(name='API Inv Loc')
        db.session.add_all([item, loc])
        db.session.commit()
        inv = Inventory(master_item_id=item.id, location_id=loc.id, quantity=5)
        db.session.add(inv)
        db.session.commit()
    rv = client.get('/inventory')
    assert rv.status_code == 200
    assert any(i['quantity'] == 5 for i in rv.get_json())
