import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'devsecretkey')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///home_inventory.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
