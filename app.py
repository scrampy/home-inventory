from flask import Flask, request, jsonify, render_template, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import IntegrityError
from marshmallow import ValidationError, Schema, fields
from datetime import datetime
import random

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///homeinventory.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Models
class Location(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), unique=True, nullable=False)

class MasterItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), unique=True, nullable=False)
    default_unit = db.Column(db.String(64), nullable=True)
    aisle = db.Column(db.String(40))
    notes = db.Column(db.String(200))
    stores = db.relationship('Store', secondary='item_stores', back_populates='items')

class Store(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    items = db.relationship('MasterItem', secondary='item_stores', back_populates='stores')

item_stores = db.Table('item_stores',
    db.Column('item_id', db.Integer, db.ForeignKey('master_item.id'), primary_key=True),
    db.Column('store_id', db.Integer, db.ForeignKey('store.id'), primary_key=True)
)

class Inventory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    location_id = db.Column(db.Integer, db.ForeignKey('location.id'), nullable=False)
    master_item_id = db.Column(db.Integer, db.ForeignKey('master_item.id'), nullable=False)
    quantity = db.Column(db.Float, nullable=False, default=0)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow)

    location = db.relationship('Location')
    master_item = db.relationship('MasterItem')

    __table_args__ = (
        db.UniqueConstraint('location_id', 'master_item_id', name='_location_item_uc'),
    )

# Schemas (plain Marshmallow)
class LocationSchema(Schema):
    id = fields.Int(dump_only=True)
    name = fields.Str(required=True)

class MasterItemSchema(Schema):
    id = fields.Int(dump_only=True)
    name = fields.Str(required=True)
    default_unit = fields.Str(allow_none=True)
    aisle = fields.Str(allow_none=True)
    notes = fields.Str(allow_none=True)
    stores = fields.Nested('StoreSchema', many=True, dump_only=True)

class StoreSchema(Schema):
    id = fields.Int(dump_only=True)
    name = fields.Str(required=True)

class InventorySchema(Schema):
    id = fields.Int(dump_only=True)
    location_id = fields.Int(required=True)
    master_item_id = fields.Int(required=True)
    quantity = fields.Float(required=True)
    last_updated = fields.DateTime(dump_only=True)
    # Nested relationships for web display
    location = fields.Nested(LocationSchema, dump_only=True)
    master_item = fields.Nested(MasterItemSchema, dump_only=True)

location_schema = LocationSchema()
locations_schema = LocationSchema(many=True)
master_item_schema = MasterItemSchema()
master_items_schema = MasterItemSchema(many=True)
store_schema = StoreSchema()
stores_schema = StoreSchema(many=True)
inventory_schema = InventorySchema()
inventories_schema = InventorySchema(many=True)

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
def get_locations():
    locs = Location.query.all()
    return jsonify(locations_schema.dump(locs))

@app.route('/locations', methods=['POST'])
def create_location():
    json_data = request.get_json()
    try:
        loc = location_schema.load(json_data, session=db.session)
    except ValidationError as err:
        return jsonify(err.messages), 400
    db.session.add(loc)
    db.session.commit()
    return jsonify(location_schema.dump(loc)), 201

# MasterItem endpoints
@app.route('/master-items', methods=['GET'])
def get_master_items():
    items = MasterItem.query.all()
    return jsonify(master_items_schema.dump(items))

@app.route('/master-items', methods=['POST'])
def create_master_item():
    json_data = request.get_json()
    try:
        item = master_item_schema.load(json_data, session=db.session)
    except ValidationError as err:
        return jsonify(err.messages), 400
    db.session.add(item)
    db.session.commit()
    return jsonify(master_item_schema.dump(item)), 201

# Store endpoints
@app.route('/stores', methods=['GET'])
def get_stores():
    stores = Store.query.all()
    return jsonify(stores_schema.dump(stores))

@app.route('/stores', methods=['POST'])
def create_store():
    json_data = request.get_json()
    try:
        store = store_schema.load(json_data, session=db.session)
    except ValidationError as err:
        return jsonify(err.messages), 400
    db.session.add(store)
    db.session.commit()
    return jsonify(store_schema.dump(store)), 201

# Inventory endpoints
@app.route('/inventory', methods=['GET'])
def get_inventory():
    invs = Inventory.query.all()
    return jsonify(inventories_schema.dump(invs))

@app.route('/inventory', methods=['POST'])
def create_inventory():
    json_data = request.get_json()
    try:
        inv = inventory_schema.load(json_data, session=db.session)
    except ValidationError as err:
        return jsonify(err.messages), 400
    db.session.add(inv)
    db.session.commit()
    return jsonify(inventory_schema.dump(inv)), 201

@app.route('/inventory/<int:inv_id>', methods=['PATCH'])
def update_inventory(inv_id):
    inv = Inventory.query.get_or_404(inv_id)
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

# SEED DATA ROUTE
@app.route('/seed')
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
    return 'Database seeded!', 201

# Seed stores
@app.route('/seed_stores')
def seed_stores():
    stores = [Store(name=s) for s in ['Walmart', 'Costco', 'No Frills']]
    db.session.add_all(stores)
    db.session.commit()
    return 'Stores seeded.'

# Web interface routes
@app.route('/', methods=['GET'])
def index():
    return redirect(url_for('web_locations'))

@app.route('/web/locations', methods=['GET', 'POST'])
def web_locations():
    error = None
    confirmation = None
    if request.method == 'POST':
        name = request.form.get('name')
        if name:
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
    confirmation = request.args.get('confirmation')
    locations = Location.query.order_by(Location.name).all()
    # Attach number of items for each location
    for loc in locations:
        loc.num_items = Inventory.query.filter_by(location_id=loc.id).count()
    return render_template('locations.html', locations=locations, error=error, confirmation=confirmation)

@app.route('/web/locations/delete/<int:loc_id>', methods=['POST'])
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
    error = None
    if request.method == 'POST':
        name = request.form.get('name')
        aisle = request.form.get('aisle')
        notes = request.form.get('notes')
        if name:
            norm_name = name.strip().title()
            item = MasterItem(name=norm_name, aisle=aisle, notes=notes)
            db.session.add(item)
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                error = f"Item '{norm_name}' already exists."
        return redirect(url_for('web_master_items', error=error) if not error else url_for('web_master_items', error=error))
    error = request.args.get('error')
    items = MasterItem.query.order_by(MasterItem.name).all()
    return render_template('master_items.html', items=items, error=error)

@app.route('/web/master-items/edit/<int:item_id>', methods=['GET', 'POST'])
def web_edit_master_item(item_id):
    item = MasterItem.query.get_or_404(item_id)
    locations = Location.query.order_by(Location.name).all()
    stores = Store.query.order_by(Store.name).all()
    confirmation = None
    error = None
    if request.method == 'POST':
        name = request.form.get('name', '').strip().title()
        aisle = request.form.get('aisle', '').strip()
        notes = request.form.get('notes', '').strip()
        add_store_id = request.form.get('add_store_id')
        # Update fields
        item.name = name
        item.aisle = aisle
        item.notes = notes
        # Add store association
        if add_store_id:
            store = Store.query.get(int(add_store_id))
            if store and store not in item.stores:
                item.stores.append(store)
        # Remove store association (if implemented via JS in future)
        # ...
        try:
            db.session.commit()
            confirmation = "Changes saved."
        except IntegrityError:
            db.session.rollback()
            error = f"Item '{name}' already exists."
        return redirect(url_for('web_edit_master_item', item_id=item.id, confirmation=confirmation, error=error))
    confirmation = request.args.get('confirmation')
    error = request.args.get('error')
    return render_template('edit_master_item.html', item=item, locations=locations, stores=stores, confirmation=confirmation, error=error)

@app.route('/web/inventory', methods=['GET', 'POST'])
def web_inventory():
    locations = Location.query.all()
    selected_location = None
    inventory = []
    confirmation = None
    error = None
    loc_param = request.args.get('location_id', type=int)

    if request.method == 'POST':
        loc_id = request.form.get('location_id')
        item_id = request.form.get('master_item_id')
        qty = request.form.get('quantity')
        try:
            quantity = int(qty)
            if quantity < 0:
                raise ValueError
        except:
            # Invalid quantity, stay on same page
            return redirect(url_for('web_inventory', location_id=loc_id))
        if loc_id and item_id:
            existing = Inventory.query.filter_by(location_id=loc_id, master_item_id=item_id).first()
            item_obj = MasterItem.query.get(item_id)
            loc_obj = Location.query.get(loc_id)
            try:
                if existing:
                    existing.quantity += quantity
                    existing.last_updated = datetime.utcnow()
                    confirmation = f"Added {quantity:g} to {item_obj.name} in {loc_obj.name}. New quantity: {existing.quantity:g}."
                else:
                    inv = Inventory(location_id=loc_id, master_item_id=item_id, quantity=quantity)
                    db.session.add(inv)
                    confirmation = f"Added {quantity:g} of {item_obj.name} to {loc_obj.name}."
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                error = f"Item '{item_obj.name}' already exists in {loc_obj.name}."
                return redirect(url_for('web_inventory', location_id=loc_id, error=error))
            # Stay on same location after POST
            return redirect(url_for('web_inventory', location_id=loc_id, confirmation=confirmation))
        else:
            # If missing info, stay on same page
            return redirect(url_for('web_inventory', location_id=loc_id))

    # GET
    confirmation = request.args.get('confirmation')
    error = request.args.get('error')
    if loc_param:
        selected_location = Location.query.get(loc_param)
        inventory = Inventory.query.filter_by(location_id=loc_param).all()
    # Only show items not already in inventory for this location
    if selected_location:
        inventory_item_ids = {inv.master_item_id for inv in Inventory.query.filter_by(location_id=selected_location.id).all()}
        items = MasterItem.query.filter(~MasterItem.id.in_(inventory_item_ids)).all()
    else:
        items = MasterItem.query.all()
    return render_template('inventory.html', locations=locations, items=items, selected_location=selected_location, inventory=inventory, selected_location_id=loc_param, confirmation=confirmation, error=error)

@app.route('/web/inventory/update/<int:inv_id>', methods=['POST'])
def web_update_inventory(inv_id):
    inv = Inventory.query.get_or_404(inv_id)
    qty = request.form.get('quantity')
    try:
        quantity = float(qty)
        if quantity < 0:
            raise ValueError
    except:
        quantity = inv.quantity
    inv.quantity = quantity
    inv.last_updated = datetime.utcnow()
    db.session.commit()
    return redirect(url_for('web_inventory', location_id=inv.location_id))

@app.route('/web/inventory/delete/<int:inv_id>', methods=['POST'])
def web_delete_inventory(inv_id):
    inv = Inventory.query.get_or_404(inv_id)
    loc_id = inv.location_id
    item_name = inv.master_item.name
    db.session.delete(inv)
    db.session.commit()
    confirmation = f"Removed {item_name} from this location."
    return redirect(url_for('web_inventory', location_id=loc_id, confirmation=confirmation))

@app.route('/web/stores', methods=['GET', 'POST'])
def web_stores():
    error = None
    confirmation = None
    if request.method == 'POST':
        name = request.form.get('name')
        if name:
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
def web_delete_store(store_id):
    store = Store.query.get_or_404(store_id)
    if len(store.items) > 0:
        error = f"Cannot delete '{store.name}' because it is still associated with items. Remove all associations first."
        return redirect(url_for('web_stores', error=error))
    db.session.delete(store)
    db.session.commit()
    confirmation = f"Store '{store.name}' deleted."
    return redirect(url_for('web_stores', confirmation=confirmation))

if __name__ == '__main__':
    app.run(debug=True)
