from flask import Flask, request, jsonify, render_template, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
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
    items = [MasterItem(name=name) for name in grocery_items]
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

# Web interface routes
@app.route('/', methods=['GET'])
def index():
    return redirect(url_for('web_locations'))

@app.route('/web/locations', methods=['GET', 'POST'])
def web_locations():
    if request.method == 'POST':
        name = request.form.get('name')
        if name:
            loc = Location(name=name.strip())
            db.session.add(loc)
            db.session.commit()
        return redirect(url_for('web_locations'))
    locations = Location.query.all()
    return render_template('locations.html', locations=locations)

@app.route('/web/master-items', methods=['GET', 'POST'])
def web_master_items():
    if request.method == 'POST':
        name = request.form.get('name')
        if name:
            item = MasterItem(name=name.strip())
            db.session.add(item)
            db.session.commit()
        return redirect(url_for('web_master_items'))
    items = MasterItem.query.all()
    return render_template('master_items.html', items=items)

@app.route('/web/inventory', methods=['GET', 'POST'])
def web_inventory():
    locations = Location.query.all()
    selected_location = None
    inventory = []
    confirmation = None
    loc_param = request.args.get('location_id', type=int)

    if request.method == 'POST':
        loc_id = request.form.get('location_id')
        item_id = request.form.get('master_item_id')
        qty = request.form.get('quantity')
        try:
            quantity = float(qty)
            if quantity < 0:
                raise ValueError
        except:
            # Invalid quantity, stay on same page
            return redirect(url_for('web_inventory', location_id=loc_id))
        if loc_id and item_id:
            existing = Inventory.query.filter_by(location_id=loc_id, master_item_id=item_id).first()
            item_obj = MasterItem.query.get(item_id)
            loc_obj = Location.query.get(loc_id)
            if existing:
                existing.quantity += quantity
                existing.last_updated = datetime.utcnow()
                confirmation = f"Added {quantity:g} to {item_obj.name} in {loc_obj.name}. New quantity: {existing.quantity:g}."
            else:
                inv = Inventory(location_id=loc_id, master_item_id=item_id, quantity=quantity)
                db.session.add(inv)
                confirmation = f"Added {quantity:g} of {item_obj.name} to {loc_obj.name}."
            db.session.commit()
            # Stay on same location after POST
            return redirect(url_for('web_inventory', location_id=loc_id, confirmation=confirmation))
        else:
            # If missing info, stay on same page
            return redirect(url_for('web_inventory', location_id=loc_id))

    # GET
    confirmation = request.args.get('confirmation')
    if loc_param:
        selected_location = Location.query.get(loc_param)
        inventory = Inventory.query.filter_by(location_id=loc_param).all()
    # Only show items not already in inventory for this location
    if selected_location:
        inventory_item_ids = {inv.master_item_id for inv in Inventory.query.filter_by(location_id=selected_location.id).all()}
        items = MasterItem.query.filter(~MasterItem.id.in_(inventory_item_ids)).all()
    else:
        items = MasterItem.query.all()
    return render_template('inventory.html', locations=locations, items=items, selected_location=selected_location, inventory=inventory, selected_location_id=loc_param, confirmation=confirmation)

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

if __name__ == '__main__':
    app.run(debug=True)
