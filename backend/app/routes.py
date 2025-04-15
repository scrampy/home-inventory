from flask import Blueprint, request, jsonify
from .models import db, Location, Store, Aisle, Item, Inventory

api = Blueprint('api', __name__)

# --- Location Endpoints ---
@api.route('/locations', methods=['GET', 'POST'])
def locations():
    if request.method == 'POST':
        data = request.json
        loc = Location(name=data['name'])
        db.session.add(loc)
        db.session.commit()
        return jsonify({'id': loc.id, 'name': loc.name}), 201
    locations = Location.query.all()
    return jsonify([{'id': l.id, 'name': l.name} for l in locations])

@api.route('/locations/<int:loc_id>', methods=['PUT', 'PATCH'])
def update_location(loc_id):
    loc = Location.query.get_or_404(loc_id)
    data = request.json
    if 'name' in data:
        loc.name = data['name']
    db.session.commit()
    return jsonify({'id': loc.id, 'name': loc.name})

@api.route('/locations/<int:loc_id>', methods=['DELETE'])
def delete_location(loc_id):
    loc = Location.query.get_or_404(loc_id)
    db.session.delete(loc)
    db.session.commit()
    return '', 204

# --- Store Endpoints ---
@api.route('/stores', methods=['GET', 'POST'])
def stores():
    if request.method == 'POST':
        data = request.json
        store = Store(name=data['name'])
        db.session.add(store)
        db.session.commit()
        return jsonify({'id': store.id, 'name': store.name}), 201
    stores = Store.query.all()
    return jsonify([{'id': s.id, 'name': s.name} for s in stores])

# --- Aisle Endpoints ---
@api.route('/aisles', methods=['GET', 'POST'])
def aisles():
    if request.method == 'POST':
        data = request.json
        aisle = Aisle(name=data['name'], store_id=data['store_id'])
        db.session.add(aisle)
        db.session.commit()
        return jsonify({'id': aisle.id, 'name': aisle.name, 'store_id': aisle.store_id}), 201
    aisles = Aisle.query.all()
    return jsonify([
        {'id': a.id, 'name': a.name, 'store_id': a.store_id} for a in aisles
    ])

# --- Item Endpoints ---
@api.route('/items', methods=['GET', 'POST'])
def items():
    if request.method == 'POST':
        data = request.json
        item = Item(
            name=data['name'],
            category=data.get('category'),
            default_unit=data.get('default_unit'),
            notes=data.get('notes'),
            photo_url=data.get('photo_url'),
            aisle_id=data.get('aisle_id')
        )
        db.session.add(item)
        db.session.commit()
        return jsonify({'id': item.id, 'name': item.name}), 201
    items = Item.query.all()
    return jsonify([
        {
            'id': i.id,
            'name': i.name,
            'category': i.category,
            'default_unit': i.default_unit,
            'notes': i.notes,
            'photo_url': i.photo_url,
            'aisle_id': i.aisle_id
        } for i in items
    ])

# --- Inventory Endpoints ---
@api.route('/inventory', methods=['GET', 'POST'])
def inventory():
    if request.method == 'POST':
        data = request.json
        inv = Inventory(
            item_id=data['item_id'],
            location_id=data.get('location_id'),
            quantity=data['quantity']
        )
        db.session.add(inv)
        db.session.commit()
        return jsonify({'id': inv.id, 'item_id': inv.item_id, 'location_id': inv.location_id, 'quantity': inv.quantity}), 201
    inventory = Inventory.query.all()
    return jsonify([
        {
            'id': inv.id,
            'item_id': inv.item_id,
            'location_id': inv.location_id,
            'quantity': inv.quantity
        } for inv in inventory
    ])

# --- Update Inventory Quantity ---
@api.route('/inventory/<int:inv_id>', methods=['PATCH'])
def update_inventory(inv_id):
    inv = Inventory.query.get_or_404(inv_id)
    data = request.json
    if 'quantity' in data:
        inv.quantity = data['quantity']
    db.session.commit()
    return jsonify({'id': inv.id, 'quantity': inv.quantity})
