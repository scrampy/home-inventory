import pytest
from app import app, db, User, Family, FamilyMember
from flask_login import login_user

def setup_module(module):
    from app import app
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['TESTING'] = True
    with app.app_context():
        db.drop_all()
        db.create_all()

def teardown_module(module):
    with app.app_context():
        db.drop_all()

@pytest.fixture
def client():
    with app.test_client() as client:
        yield client

def create_family_with_members():
    admin = User(email='admin@example.com', password_hash='hash')
    member = User(email='member@example.com', password_hash='hash')
    db.session.add_all([admin, member])
    db.session.flush()
    admin_id = admin.id
    member_id = member.id
    family = Family(name='RoleFam', created_by_user_id=admin_id)
    db.session.add(family)
    db.session.flush()
    family_id = family.id
    fam_admin = FamilyMember(user_id=admin_id, family_id=family_id, role='admin')
    fam_member = FamilyMember(user_id=member_id, family_id=family_id, role='member')
    db.session.add_all([fam_admin, fam_member])
    db.session.commit()
    return admin_id, member_id, family_id

def test_admin_can_promote_member(client):
    with app.app_context():
        db.drop_all(); db.create_all()
        admin_id, member_id, family_id = create_family_with_members()
    # Login as admin
    with client.session_transaction() as sess:
        sess['_user_id'] = str(admin_id)
    rv = client.post(f'/family/{family_id}/role', json={
        'user_id': member_id, 'role': 'admin'
    })
    assert rv.status_code == 200
    with app.app_context():
        fam_member = FamilyMember.query.filter_by(user_id=member_id, family_id=family_id).first()
        assert fam_member.role == 'admin'

def test_admin_can_demote_other_admin(client):
    with app.app_context():
        db.drop_all(); db.create_all()
        admin_id, member_id, family_id = create_family_with_members()
        # Promote member to admin
        fam_member = FamilyMember.query.filter_by(user_id=member_id, family_id=family_id).first()
        fam_member.role = 'admin'
        db.session.commit()
    # Login as admin
    with client.session_transaction() as sess:
        sess['_user_id'] = str(admin_id)
    rv = client.post(f'/family/{family_id}/role', json={
        'user_id': member_id, 'role': 'member'
    })
    assert rv.status_code == 200
    with app.app_context():
        fam_member = FamilyMember.query.filter_by(user_id=member_id, family_id=family_id).first()
        assert fam_member.role == 'member'

def test_admin_cannot_demote_self_if_last_admin(client):
    with app.app_context():
        db.drop_all(); db.create_all()
        admin_id, member_id, family_id = create_family_with_members()
    # Login as admin
    with client.session_transaction() as sess:
        sess['_user_id'] = str(admin_id)
    rv = client.post(f'/family/{family_id}/role', json={
        'user_id': admin_id, 'role': 'member'
    })
    assert rv.status_code == 400
    assert 'at least one admin' in rv.get_json()['error']

def test_member_cannot_change_roles(client):
    with app.app_context():
        db.drop_all(); db.create_all()
        admin_id, member_id, family_id = create_family_with_members()
    # Login as member
    with client.session_transaction() as sess:
        sess['_user_id'] = str(member_id)
    rv = client.post(f'/family/{family_id}/role', json={
        'user_id': admin_id, 'role': 'member'
    })
    assert rv.status_code == 403
    assert 'Only family admin' in rv.get_json()['error']
