from flask import Blueprint, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import Location, ShoppingListItem

bp = Blueprint('api', __name__)

@bp.route('/api/locations')
@login_required
def get_locations():
    """Get all locations with item counts for the current user's family."""
    locations = db.session.query(
        Location
    ).filter(
        Location.family_id == current_user.family_id
    ).order_by(
        Location.name
    ).all()
    
    result = []
    for loc in locations:
        # Get item count for this location
        item_count = db.session.query(
            db.func.count(Location.id)
        ).filter(
            Location.id == loc.id
        ).scalar() or 0
        
        result.append({
            'id': loc.id,
            'name': loc.name,
            'item_count': item_count
        })
    
    return jsonify(result)

@bp.route('/api/shopping-list/count')
@login_required
def get_shopping_list_count():
    """Get the count of items in the shopping list."""
    count = db.session.query(ShoppingListItem).filter(
        ShoppingListItem.family_id == current_user.family_id,
        ShoppingListItem.checked == False
    ).count()
    
    return jsonify({'count': count})
