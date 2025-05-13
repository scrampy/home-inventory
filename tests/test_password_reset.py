import os
import sys
import unittest
from unittest.mock import patch, MagicMock

# Add the parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app, generate_password_reset_token, verify_password_reset_token, User, db
from werkzeug.security import generate_password_hash

class PasswordResetTestCase(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.app = app.test_client()
        with app.app_context():
            db.create_all()
            # Create a test user
            test_user = User(email='test@example.com', password_hash=generate_password_hash('password123'))
            db.session.add(test_user)
            db.session.commit()
    
    def tearDown(self):
        with app.app_context():
            db.session.remove()
            db.drop_all()
    
    def test_token_generation_and_verification(self):
        """Test that password reset tokens can be generated and verified"""
        with app.app_context():
            email = 'test@example.com'
            token = generate_password_reset_token(email)
            
            # Token should be a non-empty string
            self.assertTrue(token)
            self.assertIsInstance(token, str)
            
            # Verify the token
            verified_email = verify_password_reset_token(token)
            self.assertEqual(verified_email, email)
            
            # Test invalid token
            self.assertIsNone(verify_password_reset_token('invalid-token'))
            
            # We can't easily test token expiration in a unit test without mocking time
            # or waiting, so we'll skip that test for now
    
    @patch('app.send_password_reset_email')
    def test_reset_password_request_route(self, mock_send_email):
        """Test the reset password request route"""
        mock_send_email.return_value = True
        
        # First, let's check that the form page loads correctly
        response = self.app.get('/reset-password-request')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Reset Password', response.data)
        
        # Test with existing email
        mock_send_email.reset_mock()
        response = self.app.post('/reset-password-request', data={
            'email': 'test@example.com'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        
        # Verify email would have been sent
        self.assertTrue(mock_send_email.called)
        
        # Test with non-existent email (should still show success to prevent email enumeration)
        mock_send_email.reset_mock()
        response = self.app.post('/reset-password-request', data={
            'email': 'nonexistent@example.com'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        
        # Email should not be sent for non-existent user
        self.assertFalse(mock_send_email.called)
    
    def test_reset_password_route(self):
        """Test the reset password route with a valid token"""
        with app.app_context():
            # Generate a valid token
            email = 'test@example.com'
            token = generate_password_reset_token(email)
            
            # Test GET request
            response = self.app.get(f'/reset-password/{token}')
            self.assertEqual(response.status_code, 200)
            self.assertIn(b'Set New Password', response.data)
            
            # Test POST request with valid password
            response = self.app.post(f'/reset-password/{token}', data={
                'password': 'newpassword123',
                'password_confirm': 'newpassword123'
            }, follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            
            # Verify password was changed
            user = User.query.filter_by(email=email).first()
            from werkzeug.security import check_password_hash
            self.assertTrue(check_password_hash(user.password_hash, 'newpassword123'))
            
            # Test with invalid token
            response = self.app.get('/reset-password/invalid-token', follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            self.assertIn(b'Login', response.data)  # Should redirect to login page

if __name__ == '__main__':
    unittest.main()
