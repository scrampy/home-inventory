import pytest
from app import app, db, User, Family, FamilyMember, Invitation
from flask_login import login_user

def setup_module(module):
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

def create_admin_and_family():
    admin = User(email='admin@example.com', password_hash='hash')
    db.session.add(admin)
    db.session.flush()
    admin_id = admin.id
    family = Family(name='TestFam', created_by_user_id=admin_id)
    db.session.add(family)
    db.session.flush()
    family_id = family.id
    fam_member = FamilyMember(user_id=admin_id, family_id=family_id, role='admin')
    db.session.add(fam_member)
    db.session.commit()
    return admin_id, family_id

def test_signup_with_family(client):
    with app.app_context():
        db.drop_all()
        db.create_all()
    rv = client.post('/signup', json={
        'email': 'famadmin@example.com', 'password': 'pw', 'family_name': 'Fam1'
    })
    assert rv.status_code == 200
    data = rv.get_json()
    assert data['success']
    with app.app_context():
        user = User.query.filter_by(email='famadmin@example.com').first()
        fam_member = FamilyMember.query.filter_by(user_id=user.id, role='admin').first()
        assert fam_member is not None
        family = Family.query.get(fam_member.family_id)
        assert family.name == 'Fam1'

def test_invite_flow(client):
    with app.app_context():
        db.drop_all()
        db.create_all()
        admin_id, family_id = create_admin_and_family()
    # Login as admin
    with client.session_transaction() as sess:
        sess['_user_id'] = str(admin_id)
    # Send invite
    rv = client.post('/invite', json={'email': 'invitee@example.com', 'family_id': family_id})
    assert rv.status_code == 200
    token = rv.get_json()['invite_token']
    # Accept invite (simulate visiting link)
    rv = client.get(f'/invite/accept?token={token}')
    assert rv.status_code == 200
    invite_data = rv.get_json()
    assert invite_data['email'] == 'invitee@example.com'
    # Signup with invite
    rv = client.post('/signup', json={
        'email': 'invitee@example.com', 'password': 'pw', 'invite_token': token
    })
    assert rv.status_code == 200
    with app.app_context():
        user = User.query.filter_by(email='invitee@example.com').first()
        fam_member = FamilyMember.query.filter_by(user_id=user.id, family_id=family_id).first()
        assert fam_member is not None
        invitation = Invitation.query.filter_by(token=token).first()
        assert invitation.status == 'accepted'

def test_invite_requires_admin(client):
    with app.app_context():
        db.drop_all()
        db.create_all()
        admin_id, family_id = create_admin_and_family()
        user = User(email='member@example.com', password_hash='hash')
        db.session.add(user)
        db.session.flush()
        user_id = user.id
        fam_member = FamilyMember(user_id=user_id, family_id=family_id, role='member')
        db.session.add(fam_member)
        db.session.commit()
    # Login as non-admin
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user_id)
    rv = client.post('/invite', json={'email': 'fail@example.com', 'family_id': family_id})
    assert rv.status_code == 403
    assert 'Only family admin' in rv.get_json()['error']
