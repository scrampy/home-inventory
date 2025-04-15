from . import db
from sqlalchemy.orm import relationship
from sqlalchemy import UniqueConstraint

class Family(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    name = db.Column(db.String(120))
    password_hash = db.Column(db.String(128))

class Location(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)

class Store(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)

class Aisle(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False)
    store_id = db.Column(db.Integer, db.ForeignKey('store.id'))
    store = relationship('Store', backref='aisles')
    __table_args__ = (UniqueConstraint('name', 'store_id', name='_aisle_store_uc'),)

class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    category = db.Column(db.String(64))
    default_unit = db.Column(db.String(32))
    notes = db.Column(db.Text)
    photo_url = db.Column(db.String(256))
    aisle_id = db.Column(db.Integer, db.ForeignKey('aisle.id'), nullable=True)
    aisle = relationship('Aisle', backref='items')

class Inventory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey('item.id'), nullable=False)
    location_id = db.Column(db.Integer, db.ForeignKey('location.id'), nullable=True)
    quantity = db.Column(db.Integer, default=0)
    last_updated = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())
    item = relationship('Item', backref='inventories')
    location = relationship('Location', backref='inventories')
