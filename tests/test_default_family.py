import pytest
from app import app, db, User, Family, FamilyMember
from werkzeug.security import generate_password_hash

def setup_module(module):
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['TESTING'] = True
    with app.app_context():
        db.drop_all()
        db.create_all()

def teardown_module(module):
    with app.app_context():
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client():
    # Create a test client without the app context
    # The app context will be managed by the test functions
    return app.test_client()

def test_new_user_gets_default_family(client):
    """Test that a new user gets a default family if none is provided."""
    # Use the application context for the test
    with app.app_context():
        # Setup test data
        test_email = 'testuser@example.com'
        test_password = 'testpass123'
        
        # Make sure no user with this email exists
        if User.query.filter_by(email=test_email).first():
            db.session.delete(User.query.filter_by(email=test_email).first())
            db.session.commit()
        
        # Sign up a new user without providing a family name
        response = client.post('/signup', 
            json={
                'email': test_email,
                'password': test_password
                # No family_name or invite_token provided
            },
            content_type='application/json',
            follow_redirects=True
        )
        
        # Check that the signup was successful
        assert response.status_code == 200, f"Expected status code 200, got {response.status_code}"
        
        # Get the user from the database
        user = User.query.filter_by(email=test_email).first()
        assert user is not None, "User was not created"
        
        # Check that the user is a member of exactly one family
        memberships = FamilyMember.query.filter_by(user_id=user.id).all()
        assert len(memberships) == 1, f"Expected 1 family membership, got {len(memberships)}"
        
        # Get the family
        family = db.session.get(Family, memberships[0].family_id)
        assert family is not None, "Family was not created"
        
        # Check that the family name is based on the user's email
        expected_family_name = f"{test_email.split('@')[0]}'s Family"
        assert family.name == expected_family_name, f"Expected family name {expected_family_name}, got {family.name}"

def test_new_user_with_family_name(client):
    """Test that a new user can provide a custom family name."""
    # Use the application context for the test
    with app.app_context():
        # Test data
        test_email = 'testuser2@example.com'
        test_password = 'testpass123'
        test_family_name = 'Test Family'
        
        # Make sure no user with this email exists
        if User.query.filter_by(email=test_email).first():
            db.session.delete(User.query.filter_by(email=test_email).first())
            db.session.commit()
        
        # Sign up a new user with a family name
        response = client.post('/signup', 
            json={
                'email': test_email,
                'password': test_password,
                'family_name': test_family_name
            },
            content_type='application/json',
            follow_redirects=True
        )
        
        # Check that the signup was successful
        assert response.status_code == 200, f"Expected status code 200, got {response.status_code}"
        
        # Get the user from the database
        user = User.query.filter_by(email=test_email).first()
        assert user is not None, "User was not created"
        
        # Check that the user is a member of exactly one family
        memberships = FamilyMember.query.filter_by(user_id=user.id).all()
        assert len(memberships) == 1, f"Expected 1 family membership, got {len(memberships)}"
        
        # Get the family
        family = db.session.get(Family, memberships[0].family_id)
        assert family is not None, "Family was not created"
        
        # Check that the family name matches what was provided
        assert family.name == test_family_name, f"Expected family name {test_family_name}, got {family.name}"
