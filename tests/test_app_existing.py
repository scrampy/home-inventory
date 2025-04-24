import pytest
from app import app, db, Location, Aisle, Store, MasterItem, Inventory, ShoppingListItem, Family

def setup_module(module):
    # Use an in-memory DB for all unit/integration tests
    from app import app
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
        fam = Family(name='TestFam')
        db.session.add(fam)
        db.session.flush()
        loc = Location(name='Test Pantry', family_id=fam.id)
        db.session.add(loc)
        db.session.commit()
        assert loc.id is not None
        assert Location.query.filter_by(name='Test Pantry').first() is not None

def test_location_api(client):
    # Signup and login as a user (ensures family context)
    email = 'testloc@example.com'
    password = 'pw123'
    rv = client.post('/signup', json={'email': email, 'password': password, 'family_name': 'APIFam'})
    assert rv.status_code == 200
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
        fam = Family(name='TestFam')
        db.session.add(fam)
        db.session.flush()
        aisle = Aisle(name='Test Aisle', family_id=fam.id)
        db.session.add(aisle)
        db.session.commit()
        assert aisle.id is not None
        assert Aisle.query.filter_by(name='Test Aisle').first() is not None

def test_aisle_api(client):
    # Signup and login as a user (ensures family context)
    email = 'testaisle@example.com'
    password = 'pw123'
    rv = client.post('/signup', json={'email': email, 'password': password, 'family_name': 'APIFam2'})
    assert rv.status_code == 200
    # POST
    rv = client.post('/aisles', json={'name': 'API Aisle'})
    assert rv.status_code == 201
    # GET
    rv = client.get('/aisles')
    assert rv.status_code == 200
    assert any(a['name'] == 'API Aisle' for a in rv.get_json())

# --- Store CRUD ---
def test_create_store(client):
    with app.app_context():
        fam = Family(name='TestFam')
        db.session.add(fam)
        db.session.flush()
        store = Store(name='Test Store', family_id=fam.id)
        db.session.add(store)
        db.session.commit()
        assert store.id is not None
        assert Store.query.filter_by(name='Test Store').first() is not None

def test_store_api(client):
    email = 'teststore@example.com'
    password = 'pw123'
    rv = client.post('/signup', json={'email': email, 'password': password, 'family_name': 'APIFam3'})
    assert rv.status_code == 200
    rv = client.post('/stores', json={'name': 'API Store'})
    assert rv.status_code == 201
    rv = client.get('/stores')
    assert rv.status_code == 200
    assert any(s['name'] == 'API Store' for s in rv.get_json())

# --- MasterItem CRUD ---
def test_create_master_item(client):
    with app.app_context():
        fam = Family(name='TestFam')
        db.session.add(fam)
        db.session.flush()
        aisle = Aisle(name='Aisle1', family_id=fam.id)
        db.session.add(aisle)
        db.session.flush()
        item = MasterItem(name='Test Item', family_id=fam.id, aisle_id=aisle.id)
        db.session.add(item)
        db.session.commit()
        assert item.id is not None
        assert MasterItem.query.filter_by(name='Test Item').first() is not None

def test_master_item_api(client):
    email = 'testitem@example.com'
    password = 'pw123'
    rv = client.post('/signup', json={'email': email, 'password': password, 'family_name': 'APIFam4'})
    assert rv.status_code == 200
    # Create an aisle for the item
    rv = client.post('/aisles', json={'name': 'API Aisle 4'})
    assert rv.status_code == 201
    aisle_id = rv.get_json()['id']
    rv = client.post('/master-items', json={'name': 'API Item', 'aisle_id': aisle_id})
    assert rv.status_code == 201
    rv = client.get('/master-items')
    assert rv.status_code == 200
    assert any(i['name'] == 'API Item' for i in rv.get_json())

# --- Inventory CRUD ---
def test_create_inventory(client):
    with app.app_context():
        fam = Family(name='TestFam')
        db.session.add(fam)
        db.session.flush()
        aisle = Aisle(name='Aisle1', family_id=fam.id)
        db.session.add(aisle)
        db.session.flush()
        item = MasterItem(name='Inv Item', family_id=fam.id, aisle_id=aisle.id)
        loc = Location(name='Inv Loc', family_id=fam.id)
        db.session.add_all([item, loc])
        db.session.flush()
        inv = Inventory(master_item_id=item.id, location_id=loc.id, quantity=2, family_id=fam.id)
        db.session.add(inv)
        db.session.commit()
        assert inv.id is not None
        assert Inventory.query.filter_by(master_item_id=item.id, location_id=loc.id).first() is not None

def test_inventory_api(client):
    email = 'testinv@example.com'
    password = 'pw123'
    rv = client.post('/signup', json={'email': email, 'password': password, 'family_name': 'APIFam5'})
    assert rv.status_code == 200
    # Create an aisle, item, and location for the inventory
    rv = client.post('/aisles', json={'name': 'API Aisle 5'})
    assert rv.status_code == 201
    aisle_id = rv.get_json()['id']
    rv = client.post('/master-items', json={'name': 'API Inv Item', 'aisle_id': aisle_id})
    assert rv.status_code == 201
    item_id = rv.get_json()['id']
    rv = client.post('/locations', json={'name': 'API Inv Loc'})
    assert rv.status_code == 201
    loc_id = rv.get_json()['id']
    rv = client.post('/inventory', json={'master_item_id': item_id, 'location_id': loc_id, 'quantity': 5})
    assert rv.status_code == 201
    rv = client.get('/inventory')
    assert rv.status_code == 200
    assert any(inv['master_item_id'] == item_id and inv['location_id'] == loc_id for inv in rv.get_json())

def test_inventory_requires_auth(client):
    # Log out if needed (simulate not logged in)
    client.get('/logout')
    # All inventory routes should require auth
    protected_routes = [
        ('GET', '/inventory'),
        ('POST', '/inventory'),
        ('PATCH', '/inventory/1'),  
        ('DELETE', '/inventory/1'),
        ('GET', '/locations'),
        ('POST', '/locations'),
        ('PUT', '/locations/1'),
        ('DELETE', '/locations/1'),
        ('GET', '/aisles'),
        ('POST', '/aisles'),
        ('PUT', '/aisles/1'),
        ('DELETE', '/aisles/1'),
        ('GET', '/stores'),
        ('POST', '/stores'),
        ('PUT', '/stores/1'),
        ('DELETE', '/stores/1'),
        ('GET', '/master-items'),
        ('POST', '/master-items'),
        ('PUT', '/master-items/1'),
        ('DELETE', '/master-items/1'),
    ]
    for method, route in protected_routes:
        if method == 'GET':
            rv = client.get(route)
        elif method == 'POST':
            rv = client.post(route)
        elif method == 'PUT':
            rv = client.put(route)
        elif method == 'PATCH':
            rv = client.patch(route)
        elif method == 'DELETE':
            rv = client.delete(route)
        assert rv.status_code in (302, 401, 403), f"{route} did not require auth"

def create_user_and_family(client, email, password, family_name):
    # Register user and create a family
    resp = client.post('/signup', json={
        'email': email,
        'password': password,
        'family_name': family_name
    })
    assert resp.status_code == 200
    return resp.get_json()['user_id']

def login(client, email, password):
    resp = client.post('/login', json={'email': email, 'password': password})
    assert resp.status_code == 200

def logout(client):
    client.get('/logout')

def test_family_inventory_isolation(client):
    # Setup: create two users/families
    user1 = create_user_and_family(client, 'alice@example.com', 'pw1', 'FamilyA')
    logout(client)
    user2 = create_user_and_family(client, 'bob@example.com', 'pw2', 'FamilyB')
    logout(client)

    # User 1 logs in, creates inventory data
    login(client, 'alice@example.com', 'pw1')
    loc1 = client.post('/locations', json={'name': 'PantryA'}).get_json()
    aisle1 = client.post('/aisles', json={'name': 'AisleA'}).get_json()
    store1 = client.post('/stores', json={'name': 'StoreA'}).get_json()
    item1 = client.post('/master-items', json={'name': 'ItemA'}).get_json()
    inv1 = client.post('/inventory', json={'master_item_id': item1['id'], 'location_id': loc1['id'], 'quantity': 5}).get_json()
    # User 1 sees only their data
    assert any(l['name'] == 'PantryA' for l in client.get('/locations').get_json())
    assert any(i['name'] == 'ItemA' for i in client.get('/master-items').get_json())
    logout(client)

    # User 2 logs in, creates different inventory data
    login(client, 'bob@example.com', 'pw2')
    loc2 = client.post('/locations', json={'name': 'PantryB'}).get_json()
    item2 = client.post('/master-items', json={'name': 'ItemB'}).get_json()
    inv2 = client.post('/inventory', json={'master_item_id': item2['id'], 'location_id': loc2['id'], 'quantity': 3}).get_json()
    # User 2 sees only their data
    locs2 = client.get('/locations').get_json()
    items2 = client.get('/master-items').get_json()
    assert any(l['name'] == 'PantryB' for l in locs2)
    assert not any(l['name'] == 'PantryA' for l in locs2)
    assert any(i['name'] == 'ItemB' for i in items2)
    assert not any(i['name'] == 'ItemA' for i in items2)
    # User 2 cannot access user 1's inventory by ID
    rv = client.get(f"/inventory/{inv1['id']}")
    assert rv.status_code in (403, 404)
    logout(client)

    # User 1 logs in again, should not see user 2's data
    login(client, 'alice@example.com', 'pw1')
    locs1 = client.get('/locations').get_json()
    items1 = client.get('/master-items').get_json()
    assert any(l['name'] == 'PantryA' for l in locs1)
    assert not any(l['name'] == 'PantryB' for l in locs1)
    assert any(i['name'] == 'ItemA' for i in items1)
    assert not any(i['name'] == 'ItemB' for i in items1)
    rv = client.get(f"/inventory/{inv2['id']}")
    assert rv.status_code in (403, 404)
    logout(client)
