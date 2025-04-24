import os
if os.environ.get('FLASK_TESTING') == '1':
    testing_mode = True
else:
    testing_mode = False

from flask import Flask, request, jsonify, render_template, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import IntegrityError
from marshmallow import ValidationError, Schema, fields
from datetime import datetime
import random
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
from flask_mail import Mail, Message
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import URLSafeTimedSerializer

app = Flask(__name__)
if testing_mode:
    app.config['TESTING'] = True
print('FLASK APP STARTED: TESTING =', app.config.get('TESTING'), 'ENV =', dict(os.environ))
app.config['SECRET_KEY'] = 'secret_key_here'
# Use persistent DB for normal app, special test DB for E2E, in-memory for unit tests
if os.environ.get('E2E_TEST') == '1':
    db_path = os.environ.get('TEST_DB_PATH', os.path.abspath('test.db'))
    print(f"[DEBUG] E2E_TEST db_path: {db_path}")
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
    print(f"[DEBUG] E2E_TEST SQLALCHEMY_DATABASE_URI: {app.config['SQLALCHEMY_DATABASE_URI']}")
    app.config['TESTING'] = True
else:
    db_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'instance', 'homeinventory.db')
    print(f"[DEBUG] PROD db_path: {db_path}")
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
    print(f"[DEBUG] PROD SQLALCHEMY_DATABASE_URI: {app.config['SQLALCHEMY_DATABASE_URI']}")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECURITY_PASSWORD_SALT'] = 'change_this_salt'

# --- Flask-Mail Setup ---
app.config['MAIL_SERVER'] = 'localhost'  # Change to real SMTP for production
app.config['MAIL_PORT'] = 8025           # Dummy port for local dev
app.config['MAIL_DEFAULT_SENDER'] = 'noreply@localhost'
app.config['MAIL_SUPPRESS_SEND'] = True  # Suppress sending in tests

db = SQLAlchemy(app)
mail = Mail(app)

# Token serializer for invitations
serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])

# --- Flask-Login Setup ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Models
class Location(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    family_id = db.Column(db.Integer, db.ForeignKey('family.id'), nullable=False)
    family = db.relationship('Family', back_populates='locations')
    inventory = db.relationship('Inventory', back_populates='location', cascade='all, delete-orphan')

class Aisle(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    family_id = db.Column(db.Integer, db.ForeignKey('family.id'), nullable=False)
    family = db.relationship('Family', back_populates='aisles')
    items = db.relationship('MasterItem', back_populates='aisle')

class Store(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    family_id = db.Column(db.Integer, db.ForeignKey('family.id'), nullable=False)
    family = db.relationship('Family', back_populates='stores')
    items = db.relationship('MasterItem', secondary='item_stores', back_populates='stores')

class MasterItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    aisle_id = db.Column(db.Integer, db.ForeignKey('aisle.id'))
    default_unit = db.Column(db.String(32))
    notes = db.Column(db.String(256))
    family_id = db.Column(db.Integer, db.ForeignKey('family.id'), nullable=False)
    family = db.relationship('Family', back_populates='master_items')
    aisle = db.relationship('Aisle', back_populates='items')
    stores = db.relationship('Store', secondary='item_stores', back_populates='items')
    inventory = db.relationship('Inventory', back_populates='master_item', cascade='all, delete-orphan')
    shopping_list_items = db.relationship('ShoppingListItem', back_populates='item', cascade='all, delete-orphan')

class Inventory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    location_id = db.Column(db.Integer, db.ForeignKey('location.id'), nullable=False)
    master_item_id = db.Column(db.Integer, db.ForeignKey('master_item.id'), nullable=False)
    quantity = db.Column(db.Float, nullable=False, default=0)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow)
    family_id = db.Column(db.Integer, db.ForeignKey('family.id'), nullable=False)
    family = db.relationship('Family', back_populates='inventory')
    location = db.relationship('Location', back_populates='inventory')
    master_item = db.relationship('MasterItem', back_populates='inventory')
    __table_args__ = (
        db.UniqueConstraint('location_id', 'master_item_id', 'family_id', name='_location_item_family_uc'),
    )

class ShoppingListItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey('master_item.id'), nullable=False)
    checked = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.now())
    item = db.relationship('MasterItem', back_populates='shopping_list_items')
    __table_args__ = (db.UniqueConstraint('item_id', name='_item_uc'),)

item_stores = db.Table('item_stores',
    db.Column('item_id', db.Integer, db.ForeignKey('master_item.id'), primary_key=True),
    db.Column('store_id', db.Integer, db.ForeignKey('store.id'), primary_key=True)
)

class User(UserMixin, db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(128), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=True)
    created_at = db.Column(db.DateTime, default=db.func.now())
    is_active = db.Column(db.Boolean, default=True)
    is_verified = db.Column(db.Boolean, default=False)
    families_created = db.relationship('Family', back_populates='creator', foreign_keys='Family.created_by_user_id')
    memberships = db.relationship('FamilyMember', back_populates='user')
    invitations_sent = db.relationship('Invitation', back_populates='inviter', foreign_keys='Invitation.invited_by_user_id')

    def get_id(self):
        return str(self.id)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class Family(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=db.func.now())
    creator = db.relationship('User', back_populates='families_created', foreign_keys=[created_by_user_id])
    members = db.relationship('FamilyMember', back_populates='family')
    invitations = db.relationship('Invitation', back_populates='family')
    locations = db.relationship('Location', back_populates='family', cascade='all, delete-orphan')
    aisles = db.relationship('Aisle', back_populates='family', cascade='all, delete-orphan')
    stores = db.relationship('Store', back_populates='family', cascade='all, delete-orphan')
    master_items = db.relationship('MasterItem', back_populates='family', cascade='all, delete-orphan')
    inventory = db.relationship('Inventory', back_populates='family', cascade='all, delete-orphan')

class FamilyMember(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    family_id = db.Column(db.Integer, db.ForeignKey('family.id'))
    role = db.Column(db.String(16), default='member')
    joined_at = db.Column(db.DateTime, default=db.func.now())
    user = db.relationship('User', back_populates='memberships')
    family = db.relationship('Family', back_populates='members')

class Invitation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(128), nullable=False)
    token = db.Column(db.String(256), nullable=False)
    family_id = db.Column(db.Integer, db.ForeignKey('family.id'))
    invited_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    status = db.Column(db.String(16), default='pending')
    created_at = db.Column(db.DateTime, default=db.func.now())
    expires_at = db.Column(db.DateTime)
    family = db.relationship('Family', back_populates='invitations')
    inviter = db.relationship('User', back_populates='invitations_sent', foreign_keys=[invited_by_user_id])

# Schemas (plain Marshmallow)
class LocationSchema(Schema):
    id = fields.Int(dump_only=True)
    name = fields.Str(required=True)
    family_id = fields.Int(dump_only=True)

class AisleSchema(Schema):
    id = fields.Int(dump_only=True)
    name = fields.Str(required=True)
    family_id = fields.Int(dump_only=True)

class StoreSchema(Schema):
    id = fields.Int(dump_only=True)
    name = fields.Str(required=True)
    family_id = fields.Int(dump_only=True)

class MasterItemSchema(Schema):
    id = fields.Int(dump_only=True)
    name = fields.Str(required=True)
    family_id = fields.Int(dump_only=True)
    aisle_id = fields.Int()
    default_unit = fields.Str()
    notes = fields.Str()

class InventorySchema(Schema):
    id = fields.Int(dump_only=True)
    location_id = fields.Int(required=True)
    master_item_id = fields.Int(required=True)
    quantity = fields.Float(required=True)
    last_updated = fields.DateTime(dump_only=True)
    family_id = fields.Int(dump_only=True)
    location = fields.Nested(LocationSchema, dump_only=True)
    master_item = fields.Nested(MasterItemSchema, dump_only=True)

class ShoppingListItemSchema(Schema):
    id = fields.Int(dump_only=True)
    item = fields.Nested('MasterItemSchema', dump_only=True)
    checked = fields.Bool()
    created_at = fields.DateTime()

location_schema = LocationSchema()
locations_schema = LocationSchema(many=True)
aisle_schema = AisleSchema()
aisles_schema = AisleSchema(many=True)
store_schema = StoreSchema()
stores_schema = StoreSchema(many=True)
master_item_schema = MasterItemSchema()
master_items_schema = MasterItemSchema(many=True)
inventory_schema = InventorySchema()
inventories_schema = InventorySchema(many=True)
shopping_list_item_schema = ShoppingListItemSchema()
shopping_list_items_schema = ShoppingListItemSchema(many=True)

# --- Helper: get current user's family_id ---
def get_current_family_id():
    fam_member = FamilyMember.query.filter_by(user_id=current_user.id).first()
    if not fam_member:
        return None
    return fam_member.family_id

# Ensure tables exist before first request
tables_created = False
@app.before_request
def ensure_tables():
    global tables_created
    if not tables_created:
        db.create_all()
        tables_created = True

# Location endpoints
@app.route('/locations', methods=['GET'])
@login_required
def get_locations():
    family_id = get_current_family_id()
    locs = Location.query.filter_by(family_id=family_id).all()
    return jsonify(locations_schema.dump(locs))

@app.route('/locations', methods=['POST'])
@login_required
def create_location():
    family_id = get_current_family_id()
    json_data = request.get_json()
    try:
        loc = Location(family_id=family_id, **json_data)
    except TypeError as err:
        return jsonify({'error': 'Invalid JSON'}), 400
    db.session.add(loc)
    db.session.commit()
    return jsonify(location_schema.dump(loc)), 201

@app.route('/locations/<int:loc_id>', methods=['PUT', 'DELETE'])
@login_required
def update_or_delete_location(loc_id):
    family_id = get_current_family_id()
    loc = Location.query.filter_by(id=loc_id, family_id=family_id).first_or_404()
    if request.method == 'PUT':
        json_data = request.get_json()
        try:
            loc.name = json_data['name']
        except (TypeError, KeyError):
            return jsonify({'error': 'Invalid JSON'}), 400
        db.session.commit()
        return jsonify(location_schema.dump(loc))
    elif request.method == 'DELETE':
        db.session.delete(loc)
        db.session.commit()
        return jsonify({'success': True})

# Aisle endpoints
@app.route('/aisles', methods=['GET'])
@login_required
def get_aisles():
    family_id = get_current_family_id()
    aisles = Aisle.query.filter_by(family_id=family_id).all()
    return jsonify(aisles_schema.dump(aisles))

@app.route('/aisles', methods=['POST'])
@login_required
def create_aisle():
    family_id = get_current_family_id()
    json_data = request.get_json()
    try:
        aisle = Aisle(family_id=family_id, **json_data)
    except TypeError as err:
        return jsonify({'error': 'Invalid JSON'}), 400
    db.session.add(aisle)
    db.session.commit()
    return jsonify(aisle_schema.dump(aisle)), 201

@app.route('/aisles/<int:aisle_id>', methods=['PUT', 'DELETE'])
@login_required
def update_or_delete_aisle(aisle_id):
    family_id = get_current_family_id()
    aisle = Aisle.query.filter_by(id=aisle_id, family_id=family_id).first_or_404()
    if request.method == 'PUT':
        json_data = request.get_json()
        try:
            aisle.name = json_data['name']
        except (TypeError, KeyError):
            return jsonify({'error': 'Invalid JSON'}), 400
        db.session.commit()
        return jsonify(aisle_schema.dump(aisle))
    elif request.method == 'DELETE':
        db.session.delete(aisle)
        db.session.commit()
        return jsonify({'success': True})

# MasterItem endpoints
@app.route('/master-items', methods=['GET'])
@login_required
def get_master_items():
    family_id = get_current_family_id()
    items = MasterItem.query.filter_by(family_id=family_id).all()
    return jsonify(master_items_schema.dump(items))

@app.route('/master-items', methods=['POST'])
@login_required
def create_master_item():
    family_id = get_current_family_id()
    json_data = request.get_json()
    name = json_data.get('name') if json_data else None
    if not name or not name.strip():
        return jsonify({'error': 'Item name cannot be blank.'}), 400
    try:
        item = MasterItem(family_id=family_id, **json_data)
    except TypeError as err:
        return jsonify({'error': 'Invalid JSON'}), 400
    db.session.add(item)
    db.session.commit()
    return jsonify(master_item_schema.dump(item)), 201

@app.route('/master-items/<int:item_id>', methods=['PUT', 'DELETE'])
@login_required
def update_or_delete_master_item(item_id):
    family_id = get_current_family_id()
    item = MasterItem.query.filter_by(id=item_id, family_id=family_id).first_or_404()
    if request.method == 'PUT':
        json_data = request.get_json()
        try:
            item.name = json_data['name']
            item.default_unit = json_data.get('default_unit')
            item.aisle_id = json_data.get('aisle_id')
            item.notes = json_data.get('notes')
        except (TypeError, KeyError):
            return jsonify({'error': 'Invalid JSON'}), 400
        db.session.commit()
        return jsonify(master_item_schema.dump(item))
    elif request.method == 'DELETE':
        db.session.delete(item)
        db.session.commit()
        return jsonify({'success': True})

# Store endpoints
@app.route('/stores', methods=['GET'])
@login_required
def get_stores():
    family_id = get_current_family_id()
    stores = Store.query.filter_by(family_id=family_id).all()
    return jsonify(stores_schema.dump(stores))

@app.route('/stores', methods=['POST'])
@login_required
def create_store():
    family_id = get_current_family_id()
    json_data = request.get_json()
    try:
        store = Store(family_id=family_id, **json_data)
    except TypeError as err:
        return jsonify({'error': 'Invalid JSON'}), 400
    db.session.add(store)
    db.session.commit()
    return jsonify(store_schema.dump(store)), 201

@app.route('/stores/<int:store_id>', methods=['PUT', 'DELETE'])
@login_required
def update_or_delete_store(store_id):
    family_id = get_current_family_id()
    store = Store.query.filter_by(id=store_id, family_id=family_id).first_or_404()
    if request.method == 'PUT':
        json_data = request.get_json()
        try:
            store.name = json_data['name']
        except (TypeError, KeyError):
            return jsonify({'error': 'Invalid JSON'}), 400
        db.session.commit()
        return jsonify(store_schema.dump(store))
    elif request.method == 'DELETE':
        db.session.delete(store)
        db.session.commit()
        return jsonify({'success': True})

# Inventory endpoints
@app.route('/inventory', methods=['GET'])
@login_required
def get_inventory():
    family_id = get_current_family_id()
    invs = Inventory.query.filter_by(family_id=family_id).all()
    return jsonify(inventories_schema.dump(invs))

@app.route('/inventory', methods=['POST'])
@login_required
def create_inventory():
    family_id = get_current_family_id()
    json_data = request.get_json()
    try:
        inv = Inventory(family_id=family_id, **json_data)
    except TypeError as err:
        return jsonify({'error': 'Invalid JSON'}), 400
    db.session.add(inv)
    db.session.commit()
    return jsonify(inventory_schema.dump(inv)), 201

@app.route('/inventory/<int:inv_id>', methods=['PATCH'])
@login_required
def update_inventory(inv_id):
    family_id = get_current_family_id()
    inv = Inventory.query.filter_by(id=inv_id, family_id=family_id).first_or_404()
    json_data = request.get_json()
    if 'quantity' in json_data:
        try:
            qty = float(json_data['quantity'])
            if qty < 0:
                raise ValueError
        except (ValueError, TypeError):
            return jsonify({'error': 'Quantity must be non-negative'}), 400
        inv.quantity = qty
        inv.last_updated = datetime.utcnow()
    db.session.commit()
    return jsonify(inventory_schema.dump(inv))

@app.route('/inventory/<int:inv_id>', methods=['DELETE'])
@login_required
def delete_inventory(inv_id):
    family_id = get_current_family_id()
    inv = Inventory.query.filter_by(id=inv_id, family_id=family_id).first_or_404()
    db.session.delete(inv)
    db.session.commit()
    return jsonify({'success': True})

# Inventory by ID (for family isolation test)
@app.route('/inventory/<int:inventory_id>', methods=['GET'])
@login_required
def get_inventory_by_id(inventory_id):
    family_id = get_current_family_id()
    inv = Inventory.query.filter_by(id=inventory_id, family_id=family_id).first()
    if not inv:
        return {'error': 'Not found'}, 404
    return {
        'id': inv.id,
        'master_item_id': inv.master_item_id,
        'location_id': inv.location_id,
        'quantity': inv.quantity,
        'last_updated': inv.last_updated.isoformat() if inv.last_updated else None
    }, 200

# Shopping List endpoints
@app.route('/shopping-list', methods=['GET'])
@login_required
def get_shopping_list():
    family_id = get_current_family_id()
    items = ShoppingListItem.query.all()
    return jsonify(shopping_list_items_schema.dump(items))

@app.route('/shopping-list', methods=['POST'])
@login_required
def create_shopping_list_item():
    family_id = get_current_family_id()
    json_data = request.get_json()
    try:
        item = ShoppingListItem(**json_data)
    except TypeError as err:
        return jsonify({'error': 'Invalid JSON'}), 400
    db.session.add(item)
    db.session.commit()
    return jsonify(shopping_list_item_schema.dump(item)), 201

# SEED DATA ROUTE
@app.route('/seed')
@login_required
def seed():
    # Only seed if tables are empty
    if Location.query.first() or MasterItem.query.first() or Inventory.query.first():
        return 'Already seeded.', 200

    locations = [
        Location(name='Pantry'),
        Location(name='Refrigerator'),
        Location(name='Freezer')
    ]
    db.session.add_all(locations)
    db.session.commit()

    aisles = [
        Aisle(name='Bakery'),
        Aisle(name='Canned Goods'),
        Aisle(name='Dairy'),
        Aisle(name='Meat'),
        Aisle(name='Produce'),
        Aisle(name='Spices')
    ]
    db.session.add_all(aisles)
    db.session.commit()

    grocery_items = [
        'Milk', 'Eggs', 'Butter', 'Cheddar Cheese', 'Yogurt', 'Orange Juice', 'Apples', 'Bananas', 'Grapes', 'Strawberries',
        'Chicken Breast', 'Ground Beef', 'Pork Chops', 'Bacon', 'Ham', 'Salmon', 'Tilapia', 'Shrimp', 'Broccoli', 'Carrots',
        'Potatoes', 'Onions', 'Tomatoes', 'Lettuce', 'Spinach', 'Cucumber', 'Bell Peppers', 'Mushrooms', 'Zucchini', 'Corn',
        'Rice', 'Pasta', 'Bread', 'Tortillas', 'Cereal', 'Oatmeal', 'Peanut Butter', 'Jelly', 'Canned Beans', 'Canned Corn',
        'Soup', 'Crackers', 'Chips', 'Cookies', 'Ice Cream', 'Frozen Pizza', 'Frozen Vegetables', 'Ketchup', 'Mustard', 'Mayonnaise'
    ]
    items = [MasterItem(name=name.title()) for name in grocery_items]
    db.session.add_all(items)
    db.session.commit()

    # Assign each item to a random location with a random quantity (0-5)
    all_locations = Location.query.all()
    all_items = MasterItem.query.all()
    for item in all_items:
        loc = random.choice(all_locations)
        qty = random.randint(0, 5)
        db.session.add(Inventory(location_id=loc.id, master_item_id=item.id, quantity=qty))
    db.session.commit()

    # Seed demo shopping list items
    milk = MasterItem.query.filter_by(name='Milk').first()
    bread = MasterItem.query.filter_by(name='Bread').first()
    store = Store.query.filter_by(name='Kroger').first()
    if milk and not ShoppingListItem.query.filter_by(item_id=milk.id).first():
        sli = ShoppingListItem(item_id=milk.id, checked=False)
        db.session.add(sli)
    if bread and not ShoppingListItem.query.filter_by(item_id=bread.id).first():
        sli2 = ShoppingListItem(item_id=bread.id, checked=True)
        db.session.add(sli2)
    db.session.commit()
    return 'Database seeded!', 201

# Seed stores
@app.route('/seed_stores')
@login_required
def seed_stores():
    stores = [Store(name=s) for s in ['Walmart', 'Costco', 'No Frills']]
    db.session.add_all(stores)
    db.session.commit()
    return 'Stores seeded.'

# User endpoints
@app.route('/signup', methods=['POST'])
def signup():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    family_name = data.get('family_name')
    invite_token = data.get('invite_token')
    if not email or not password:
        return jsonify({'error': 'Email and password required'}), 400
    if User.query.filter_by(email=email).first():
        return jsonify({'error': 'Email already registered'}), 400
    pw_hash = generate_password_hash(password)
    user = User(email=email, password_hash=pw_hash)
    db.session.add(user)
    db.session.flush()  # to get user.id
    # Handle family creation or invitation acceptance
    if invite_token:
        try:
            print(f"[DEBUG] /signup received invite_token: {invite_token}")
            invite_data = serializer.loads(invite_token, max_age=86400, salt='invite')
            invitation = Invitation.query.filter_by(token=invite_token, status='pending').first()
            print(f"[DEBUG] /signup invitation: {invitation}")
            if invitation:
                print(f"[DEBUG] /signup invitation status: {invitation.status}, email: {invitation.email}, family_id: {invitation.family_id}")
            if not invitation:
                print(f"[DEBUG] /signup: No pending invitation found for token {invite_token}")
                return jsonify({'error': 'Invalid or expired invitation.'}), 400
            if invitation.email != email:
                print(f"[DEBUG] /signup: Invitation email {invitation.email} does not match submitted email {email}")
                return jsonify({'error': 'Invitation email does not match.'}), 400
            # Accept invitation: add user to family
            fam_member = FamilyMember(user_id=user.id, family_id=invitation.family_id, role='member')
            invitation.status = 'accepted'
            db.session.add(fam_member)
        except Exception as e:
            print(f"[DEBUG] /signup exception: {e}")
            return jsonify({'error': 'Invalid or expired invitation.'}), 400
    elif family_name:
        # Create new family, make user admin
        family = Family(name=family_name, created_by_user_id=user.id)
        db.session.add(family)
        db.session.flush()
        fam_member = FamilyMember(user_id=user.id, family_id=family.id, role='admin')
        db.session.add(fam_member)
    db.session.commit()
    login_user(user)
    return jsonify({'success': True, 'user_id': user.id})

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return redirect(url_for('auth_page'))
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    user = User.query.filter_by(email=email).first()
    if not user or not check_password_hash(user.password_hash, password):
        return jsonify({'error': 'Invalid credentials'}), 401
    login_user(user)
    return jsonify({'success': True, 'user_id': user.id})

@app.route('/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    return jsonify({'success': True})

@app.route('/invite', methods=['POST'])
@login_required
def invite():
    fam_member = FamilyMember.query.filter_by(user_id=current_user.id).first()
    if not fam_member or fam_member.role != 'admin':
        return jsonify({'error': 'Only admins can invite.'}), 403
    data = request.get_json()
    email = data.get('email')
    family_id = data.get('family_id', fam_member.family_id)
    if not email:
        return jsonify({'error': 'Email required.'}), 400
    # Generate token
    token = serializer.dumps(email, salt='invite')
    # Store invitation
    inv = Invitation(email=email, family_id=family_id, token=token)
    db.session.add(inv)
    db.session.commit()
    # Send email or display token for E2E
    resp = {'invite_token': token, 'msg': 'Invitation sent!'}
    resp['token'] = token
    return jsonify(resp)

@app.route('/invite/accept', methods=['GET'])
def invite_accept():
    token = request.args.get('token')
    print(f"[DEBUG] /invite/accept received token: {token}")
    try:
        invite_data = serializer.loads(token, max_age=86400, salt='invite')
        invitation = Invitation.query.filter_by(token=token, status='pending').first()
        print(f"[DEBUG] /invite/accept invitation: {invitation}")
        if invitation:
            print(f"[DEBUG] /invite/accept invitation status: {invitation.status}, email: {invitation.email}, family_id: {invitation.family_id}")
        if not invitation:
            print(f"[DEBUG] /invite/accept: No pending invitation found for token {token}")
            return render_template('auth.html', invite_error='Invalid or expired invitation.', invite_token=token)
        family = Family.query.get(invitation.family_id)
        family_name = family.name if family else None
        # Render signup form with prefilled email, family name, and invite_token
        return render_template(
            'auth.html',
            invite_email=invitation.email,
            invite_token=token,
            invite_family_id=invitation.family_id,
            invite_family_name=family_name
        )
    except Exception as e:
        print(f"[DEBUG] /invite/accept exception: {e}")
        return render_template('auth.html', invite_error='Invalid or expired invitation.', invite_token=token)

@app.route('/family/<int:family_id>/role', methods=['POST'])
@login_required
def change_family_role(family_id):
    fam_member = FamilyMember.query.filter_by(user_id=current_user.id, family_id=family_id).first()
    if not fam_member or fam_member.role != 'admin':
        return jsonify({'error': 'Only family admin can change roles.'}), 403
    data = request.get_json()
    user_id = data.get('user_id')
    new_role = data.get('role')
    if user_id is None or new_role not in ('admin', 'member'):
        return jsonify({'error': 'Invalid input.'}), 400
    target_member = FamilyMember.query.filter_by(user_id=user_id, family_id=family_id).first()
    if not target_member:
        return jsonify({'error': 'User not in family.'}), 404
    # Prevent last admin demotion
    if target_member.user_id == current_user.id and fam_member.role == 'admin' and new_role == 'member':
        admin_count = FamilyMember.query.filter_by(family_id=family_id, role='admin').count()
        if admin_count <= 1:
            return jsonify({'error': 'There must be at least one admin in the family.'}), 400
    target_member.role = new_role
    db.session.commit()
    return jsonify({'success': True, 'user_id': user_id, 'role': new_role})

# Web interface routes
@app.route('/')
def index():
    return redirect(url_for('web_locations'))

@app.route('/web/locations', methods=['GET', 'POST'])
def web_locations():
    if not current_user.is_authenticated:
        return redirect(url_for('auth_page'))
    error = None
    confirmation = None
    if request.method == 'POST':
        name = request.form.get('name')
        if not name or not name.strip():
            error = "Location name cannot be blank."
        else:
            norm_name = name.strip().title()
            loc = Location(name=norm_name)
            db.session.add(loc)
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                error = f"Location '{norm_name}' already exists."
        return redirect(url_for('web_locations', error=error) if not error else url_for('web_locations', error=error))
    error = request.args.get('error')
    locations = Location.query.order_by(Location.name).all()
    # Attach number of items for each location
    for loc in locations:
        loc.num_items = Inventory.query.filter_by(location_id=loc.id).count()
    return render_template('locations.html', locations=locations, error=error, confirmation=confirmation)

@app.route('/web/locations/delete/<int:loc_id>', methods=['POST'])
@login_required
def web_delete_location(loc_id):
    loc = Location.query.get_or_404(loc_id)
    if Inventory.query.filter_by(location_id=loc_id).count() > 0:
        error = f"Cannot delete '{loc.name}' because it still contains inventory. Remove all items first."
        return redirect(url_for('web_locations', error=error))
    db.session.delete(loc)
    db.session.commit()
    confirmation = f"Location '{loc.name}' deleted."
    return redirect(url_for('web_locations', confirmation=confirmation))

@app.route('/web/master-items', methods=['GET', 'POST'])
def web_master_items():
    if not current_user.is_authenticated:
        return redirect(url_for('auth_page'))
    error = None
    if request.method == 'POST':
        name = request.form.get('name')
        aisle_id = request.form.get('aisle_id')
        notes = request.form.get('notes')
        if not name or not name.strip():
            error = "Item name cannot be blank."
        else:
            norm_name = name.strip().title()
            item = MasterItem(name=norm_name, aisle_id=aisle_id, notes=notes)
            db.session.add(item)
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                error = f"Item '{norm_name}' already exists."
        return redirect(url_for('web_master_items', error=error) if not error else url_for('web_master_items', error=error))
    error = request.args.get('error')
    items = MasterItem.query.order_by(MasterItem.name).all()
    aisles = Aisle.query.order_by(Aisle.name).all()
    return render_template('master_items.html', items=items, aisles=aisles, error=error)

@app.route('/web/master-items/edit/<int:item_id>', methods=['GET', 'POST'])
@login_required
def web_edit_master_item(item_id):
    item = MasterItem.query.get_or_404(item_id)
    stores = Store.query.order_by(Store.name).all()
    aisles = Aisle.query.order_by(Aisle.name).all()
    confirmation = None
    error = None
    if request.method == 'POST':
        # Handle delete item
        if request.form.get('delete_item') == '1':
            item_name = item.name
            db.session.delete(item)
            db.session.commit()
            confirmation = f"Item '{item_name}' deleted."
            return redirect(url_for('web_master_items', confirmation=confirmation))
        # Add store only (from store add form)
        add_store_id = request.form.get('add_store_id')
        if add_store_id and not request.form.get('name'):
            # Only add store, don't touch name/aisle/notes
            store = Store.query.get(int(add_store_id))
            if store and store not in item.stores:
                item.stores.append(store)
                db.session.commit()
                confirmation = f"Added store '{store.name}' to item."
            return redirect(url_for('web_edit_master_item', item_id=item.id, confirmation=confirmation))
        # Main edit form
        name = request.form.get('name')
        if not name or not name.strip():
            error = "Item name cannot be blank."
            return redirect(url_for('web_edit_master_item', item_id=item.id, error=error))
        name = name.strip().title()
        aisle_id = request.form.get('aisle_id')
        notes = request.form.get('notes', '').strip()
        # Update fields
        item.name = name
        item.aisle_id = int(aisle_id) if aisle_id else None
        item.notes = notes
        try:
            db.session.commit()
            confirmation = "Changes saved."
        except IntegrityError:
            db.session.rollback()
            error = f"Item '{name}' already exists."
        return redirect(url_for('web_edit_master_item', item_id=item.id, confirmation=confirmation, error=error))
    confirmation = request.args.get('confirmation')
    error = request.args.get('error')
    return render_template('edit_master_item.html', item=item, stores=stores, aisles=aisles, confirmation=confirmation, error=error)

@app.route('/web/master-items/delete/<int:item_id>', methods=['POST'])
@login_required
def web_delete_master_item(item_id):
    item = MasterItem.query.get_or_404(item_id)
    item_name = item.name
    db.session.delete(item)
    db.session.commit()
    confirmation = f"Item '{item_name}' deleted."
    return redirect(url_for('web_master_items', confirmation=confirmation))

@app.route('/web/master-items/remove-store/<int:item_id>/<int:store_id>', methods=['POST'])
@login_required
def web_remove_store_from_item(item_id, store_id):
    item = MasterItem.query.get_or_404(item_id)
    store = Store.query.get_or_404(store_id)
    item_name = item.name
    store_name = store.name
    if store in item.stores:
        item.stores.remove(store)
        db.session.commit()
    # Re-fetch item to ensure UI reflects change
    confirmation = f"Removed '{item_name}' from store '{store_name}'."
    return redirect(url_for('web_edit_master_item', item_id=item.id, confirmation=confirmation))

@app.route('/web/inventory', methods=['GET', 'POST'])
def web_inventory():
    if not current_user.is_authenticated:
        return redirect(url_for('auth_page'))
    locations = Location.query.order_by(Location.name).all()
    location_id = request.args.get('location_id', type=int) or request.form.get('location_id', type=int)
    # Sorting
    sort_col = request.args.get('sort_col') or request.form.get('sort_col')
    sort_dir = request.args.get('sort_dir') or request.form.get('sort_dir')
    confirmation = request.args.get('confirmation')
    error = request.args.get('error')
    if request.method == 'POST':
        master_item_id = request.form.get('master_item_id', type=int)
        quantity = request.form.get('quantity', type=float)
        if not (location_id and master_item_id and quantity is not None):
            error = 'Please select an item and specify a quantity.'
        else:
            inv = Inventory.query.filter_by(location_id=location_id, master_item_id=master_item_id).first()
            if inv:
                inv.quantity = quantity
                inv.last_updated = datetime.utcnow()
                confirmation = f"Updated {inv.master_item.name} in inventory."
            else:
                new_inv = Inventory(location_id=location_id, master_item_id=master_item_id, quantity=quantity, last_updated=datetime.utcnow())
                db.session.add(new_inv)
                confirmation = "Item added to inventory."
            db.session.commit()
        # Redirect to avoid form re-submission
        return redirect(url_for('web_inventory', location_id=location_id, confirmation=confirmation, error=error, sort_col=sort_col, sort_dir=sort_dir))
    # GET logic
    selected_location = None
    inventory = []
    items = []
    if location_id:
        selected_location = Location.query.get(location_id)
        inventory_query = Inventory.query.filter_by(location_id=location_id)
        # Sorting logic
        if sort_col == '1':  # quantity
            if sort_dir == 'desc':
                inventory_query = inventory_query.order_by(Inventory.quantity.desc())
            else:
                inventory_query = inventory_query.order_by(Inventory.quantity)
        elif sort_col == '2':  # last_updated
            if sort_dir == 'desc':
                inventory_query = inventory_query.order_by(Inventory.last_updated.desc())
            else:
                inventory_query = inventory_query.order_by(Inventory.last_updated)
        else:  # item name (default)
            if sort_dir == 'desc':
                inventory_query = inventory_query.join(MasterItem).order_by(MasterItem.name.desc())
            else:
                inventory_query = inventory_query.join(MasterItem).order_by(MasterItem.name)
        inventory = inventory_query.all()
        inventory_item_ids = {inv.master_item_id for inv in inventory}
        items = MasterItem.query.filter(~MasterItem.id.in_(inventory_item_ids)).order_by(MasterItem.name).all()
    else:
        items = MasterItem.query.order_by(MasterItem.name).all()
    return render_template('inventory.html', locations=locations, inventory=inventory, selected_location=selected_location, selected_location_id=location_id, items=items, confirmation=confirmation, error=error, sort_col=sort_col, sort_dir=sort_dir)

@app.route('/web/inventory/update/<int:inv_id>', methods=['POST'])
@login_required
def web_update_inventory(inv_id):
    inv = Inventory.query.get_or_404(inv_id)
    qty = request.form.get('quantity')
    sort_col = request.form.get('sort_col')
    sort_dir = request.form.get('sort_dir')
    try:
        quantity = float(qty)
        if quantity < 0:
            raise ValueError
    except:
        quantity = inv.quantity
    inv.quantity = quantity
    inv.last_updated = datetime.utcnow()
    db.session.commit()
    return redirect(url_for('web_inventory', location_id=inv.location_id, sort_col=sort_col, sort_dir=sort_dir))

@app.route('/web/inventory/delete/<int:inv_id>', methods=['POST'])
@login_required
def web_delete_inventory(inv_id):
    inv = Inventory.query.get_or_404(inv_id)
    loc_id = inv.location_id
    item_name = inv.master_item.name
    db.session.delete(inv)
    db.session.commit()
    confirmation = f"Removed {item_name} from this location."
    return redirect(url_for('web_inventory', location_id=loc_id, confirmation=confirmation))

@app.route('/web/shopping-list/remove/<int:item_id>', methods=['POST'])
@login_required
def web_remove_from_shopping_list(item_id):
    sli = ShoppingListItem.query.filter_by(item_id=item_id).first()
    if sli:
        db.session.delete(sli)
        db.session.commit()
    return ('', 204)

@app.route('/web/stores', methods=['GET', 'POST'])
def web_stores():
    if not current_user.is_authenticated:
        return redirect(url_for('auth_page'))
    error = None
    confirmation = None
    if request.method == 'POST':
        name = request.form.get('name')
        if not name or not name.strip():
            error = "Store name cannot be blank."
        else:
            norm_name = name.strip().title()
            store = Store(name=norm_name)
            db.session.add(store)
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                error = f"Store '{norm_name}' already exists."
        return redirect(url_for('web_stores', error=error) if not error else url_for('web_stores', error=error))
    error = request.args.get('error')
    confirmation = request.args.get('confirmation')
    stores = Store.query.order_by(Store.name).all()
    for store in stores:
        store.num_items = len(store.items)
    return render_template('stores.html', stores=stores, error=error, confirmation=confirmation)

@app.route('/web/stores/delete/<int:store_id>', methods=['POST'])
@login_required
def web_delete_store(store_id):
    store = Store.query.get_or_404(store_id)
    if len(store.items) > 0:
        error = f"Cannot delete '{store.name}' because it is still associated with items. Remove all associations first."
        return redirect(url_for('web_stores', error=error))
    db.session.delete(store)
    db.session.commit()
    confirmation = f"Store '{store.name}' deleted."
    return redirect(url_for('web_stores', confirmation=confirmation))

@app.route('/web/aisles', methods=['GET', 'POST'])
def web_aisles():
    if not current_user.is_authenticated:
        return redirect(url_for('auth_page'))
    error = None
    if request.method == 'POST':
        name = request.form.get('name')
        delete_id = request.form.get('delete_id')
        if name:
            norm_name = name.strip().title()
            if not norm_name:
                error = 'Aisle name cannot be empty.'
            elif Aisle.query.filter_by(name=norm_name).first():
                error = f'Aisle "{norm_name}" already exists.'
            else:
                aisle = Aisle(name=norm_name)
                db.session.add(aisle)
                db.session.commit()
        elif delete_id:
            aisle = Aisle.query.get(delete_id)
            if aisle:
                if aisle.items:
                    error = f'Cannot delete aisle "{aisle.name}" because it is in use.'
                else:
                    db.session.delete(aisle)
                    db.session.commit()
    aisles = Aisle.query.order_by(Aisle.name).all()
    return render_template('aisles.html', aisles=aisles, error=error)

@app.route('/web/shopping-list', methods=['GET'])
def web_shopping_list():
    if not current_user.is_authenticated:
        return redirect(url_for('auth_page'))
    store_id = request.args.get('store_id', type=int)
    stores = Store.query.order_by(Store.name).all()
    all_sli = ShoppingListItem.query.order_by(ShoppingListItem.created_at).all()
    filtered_sli = []
    for sli in all_sli:
        item_stores = sli.item.stores  # many-to-many relationship
        if store_id:
            if any(s.id == store_id for s in item_stores):
                filtered_sli.append(sli)
        else:
            filtered_sli.append(sli)
    # Compute total inventory for each item
    inventory_totals = {}
    item_store_names = {}
    for sli in filtered_sli:
        total = db.session.query(db.func.sum(Inventory.quantity)).filter(Inventory.master_item_id == sli.item_id).scalar() or 0
        inventory_totals[sli.id] = total
        item_store_names[sli.id] = ', '.join([s.name for s in sli.item.stores]) if sli.item.stores else '—'
    return render_template('shopping_list.html', shopping_list=filtered_sli, stores=stores, inventory_totals=inventory_totals, item_store_names=item_store_names)

@app.route('/web/shopping-list/toggle/<int:sli_id>', methods=['POST'])
@login_required
def web_toggle_shopping_list(sli_id):
    sli = ShoppingListItem.query.get_or_404(sli_id)
    checked = request.form.get('checked') == '1'
    sli.checked = checked
    db.session.commit()
    return redirect(request.referrer or url_for('web_shopping_list'))

@app.route('/web/shopping-list/add/<int:item_id>', methods=['POST'])
@login_required
def web_add_to_shopping_list(item_id):
    # Only add if not already present (no store-specific for now)
    existing = ShoppingListItem.query.filter_by(item_id=item_id).first()
    if not existing:
        sli = ShoppingListItem(item_id=item_id, checked=False)
        db.session.add(sli)
        db.session.commit()
    return redirect(request.referrer or url_for('web_shopping_list'))

@app.route('/web/shopping-list/delete/<int:sli_id>', methods=['POST'])
@login_required
def web_delete_shopping_list_item(sli_id):
    sli = ShoppingListItem.query.get_or_404(sli_id)
    db.session.delete(sli)
    db.session.commit()
    return redirect(request.referrer or url_for('web_shopping_list'))

@app.route('/auth')
def auth_page():
    return render_template('auth.html')

@app.route('/family')
@login_required
def family_dashboard():
    fam_member = FamilyMember.query.filter_by(user_id=current_user.id).first()
    if fam_member:
        family = Family.query.get(fam_member.family_id)
        members = FamilyMember.query.filter_by(family_id=family.id).all()
        for m in members:
            m.user = User.query.get(m.user_id)
        current_user_role = fam_member.role
        admin_count = FamilyMember.query.filter_by(family_id=family.id, role='admin').count()
        return render_template('family.html', family=family, members=members, current_user_role=current_user_role, admin_count=admin_count)
    return render_template('family.html', family=None, members=None, current_user_role=None, admin_count=0)

@app.route('/logout', methods=['GET'])
def logout_redirect():
    # Convenience: GET /logout redirects to /auth after POST logout
    return render_template('auth.html')

@app.route('/user/profile')
@login_required
def user_profile():
    fam_member = FamilyMember.query.filter_by(user_id=current_user.id).first()
    family = fam_member.family if fam_member else None
    return render_template('user_profile.html', user=current_user, family=family)

# --- TEST-ONLY ENDPOINT: Setup User & Family for UI tests ---
@app.route('/test/setup-user', methods=['POST'])
def test_setup_user():
    print('TEST_SETUP_USER: TESTING =', app.config.get('TESTING'), 'ENV =', dict(os.environ))
    import sys
    try:
        if not app.config.get('TESTING'):
            return '', 404
        data = request.json
        email = data['email']
        password = data['password']
        family_name = data['family']
        from werkzeug.security import generate_password_hash
        # Remove existing user and related family/family_member if present
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            # Remove family memberships
            FamilyMember.query.filter_by(user_id=existing_user.id).delete()
            # Remove families created by this user
            Family.query.filter_by(created_by_user_id=existing_user.id).delete()
            db.session.delete(existing_user)
            db.session.commit()
        # Remove any family with the same name (cleanup from prior runs)
        existing_family = Family.query.filter_by(name=family_name).first()
        if existing_family:
            FamilyMember.query.filter_by(family_id=existing_family.id).delete()
            db.session.delete(existing_family)
            db.session.commit()
        user = User(email=email, password_hash=generate_password_hash(password))
        db.session.add(user)
        db.session.flush()  # to get user.id
        family = Family(name=family_name, created_by_user_id=user.id)
        db.session.add(family)
        db.session.flush()
        fam_member = FamilyMember(user_id=user.id, family_id=family.id, role='admin')
        db.session.add(fam_member)
        db.session.commit()
        # Optionally log in the user for this test session
        login_user(user)
        return jsonify({'user_id': user.id, 'family_id': family.id})
    except Exception as e:
        print('[ERROR] Exception in /test/setup-user:', e, file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    import sys
    port = int(os.environ.get('PORT', 5000))
    if '--port' in sys.argv:
        idx = sys.argv.index('--port')
        if idx + 1 < len(sys.argv):
            port = int(sys.argv[idx + 1])
    app.run(debug=True, use_reloader=False, host='0.0.0.0', port=port)
