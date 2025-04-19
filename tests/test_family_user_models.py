import pytest
from datetime import datetime
from app import db, MasterItem  # import your db instance
from flask import Flask
from sqlalchemy.exc import IntegrityError
from app import User, Family, FamilyMember, Invitation

@pytest.fixture(scope="module")
def test_app():
    # Minimal Flask app for SQLAlchemy
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()

@pytest.fixture(scope="function")
def session(test_app):
    with test_app.app_context():
        yield db.session
        db.session.rollback()

# --- Tests ---
def test_user_model(session):
    user = User(email="test@example.com", password_hash="hash", is_active=True, is_verified=False)
    session.add(user)
    session.commit()
    assert user.id is not None
    assert user.email == "test@example.com"
    assert user.is_active is True
    assert user.is_verified is False

def test_family_model(session):
    user = User(email="admin@example.com", password_hash="hash", is_active=True, is_verified=True)
    session.add(user)
    session.commit()
    family = Family(name="Smith Family", created_by_user_id=user.id)
    session.add(family)
    session.commit()
    assert family.id is not None
    assert family.name == "Smith Family"
    assert family.created_by_user_id == user.id

def test_family_member_model(session):
    user = User(email="member@example.com", password_hash="hash", is_active=True, is_verified=True)
    session.add(user)
    session.commit()
    family = Family(name="Jones Family", created_by_user_id=user.id)
    session.add(family)
    session.commit()
    member = FamilyMember(user_id=user.id, family_id=family.id, role="admin", joined_at=datetime.utcnow())
    session.add(member)
    session.commit()
    assert member.id is not None
    assert member.role == "admin"
    assert member.user_id == user.id
    assert member.family_id == family.id

def test_invitation_model(session):
    user = User(email="inviter@example.com", password_hash="hash", is_active=True, is_verified=True)
    session.add(user)
    session.commit()
    family = Family(name="Invite Family", created_by_user_id=user.id)
    session.add(family)
    session.commit()
    invitation = Invitation(email="invitee@example.com", token="tok123", family_id=family.id, invited_by_user_id=user.id, status="pending", created_at=datetime.utcnow(), expires_at=datetime.utcnow())
    session.add(invitation)
    session.commit()
    assert invitation.id is not None
    assert invitation.email == "invitee@example.com"
    assert invitation.family_id == family.id
    assert invitation.invited_by_user_id == user.id
    assert invitation.status == "pending"
