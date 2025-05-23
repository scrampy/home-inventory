import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Ensure instance directory exists
instance_dir = os.path.join(os.path.dirname(__file__), '..', 'instance')
os.makedirs(instance_dir, exist_ok=True)

from app import app, db
# Explicitly import all models to ensure tables are registered
from app import User, Family, FamilyMember, Invitation, Location, Aisle, Store, MasterItem, Inventory, ShoppingListItem

with app.app_context():
    db.drop_all()
    db.create_all()
    print('Database dropped and recreated.')
