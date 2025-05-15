import os
import traceback
from flask import jsonify, current_app

def create_debug_routes(app, mailjet, generate_password_reset_token, User):
    """
    Create debug routes for troubleshooting password reset functionality.
    These routes are only accessible in development mode.
    """
    
    @app.route('/debug/env-check', methods=['GET'])
    def debug_env_check():
        """Check environment variables and configuration"""
        # Only allow in development mode
        if not app.config.get('DEBUG') and os.environ.get('FLASK_ENV') != 'development':
            return "This endpoint is only available in development mode", 403
        
        # Check environment variables (safely)
        env_info = {
            'MAILJET_API_KEY': bool(app.config.get('MAILJET_API_KEY')),
            'MAILJET_SECRET_KEY': bool(app.config.get('MAILJET_SECRET_KEY')),
            'MAILJET_SENDER_EMAIL': app.config.get('MAILJET_SENDER_EMAIL'),
            'MAILJET_SENDER_NAME': app.config.get('MAILJET_SENDER_NAME'),
            'FLASK_ENV': os.environ.get('FLASK_ENV'),
            'DEBUG': app.config.get('DEBUG'),
            'TESTING': app.config.get('TESTING')
        }
        
        return jsonify({
            'environment': env_info,
            'app_config': {k: str(v) for k, v in app.config.items() 
                          if k not in ['SECRET_KEY', 'SECURITY_PASSWORD_SALT', 'MAILJET_API_KEY', 'MAILJET_SECRET_KEY']}
        })
    
    @app.route('/debug/test-mailjet', methods=['GET'])
    def debug_test_mailjet():
        """Test Mailjet API connection"""
        # Only allow in development mode
        if not app.config.get('DEBUG') and os.environ.get('FLASK_ENV') != 'development':
            return "This endpoint is only available in development mode", 403
        
        # Test email sending to a safe test address
        test_email = "test@example.com"  # This won't actually be sent in our test
        
        # Try sending a test email (dry run)
        try:
            data = {
                'Messages': [
                    {
                        'From': {
                            'Email': app.config['MAILJET_SENDER_EMAIL'],
                            'Name': app.config['MAILJET_SENDER_NAME']
                        },
                        'To': [{'Email': test_email}],
                        'Subject': 'Test Email',
                        'TextPart': 'This is a test email.'
                    }
                ]
            }
            
            # Just validate the data without sending
            validation_result = {
                'data_valid': True,
                'from_email': app.config['MAILJET_SENDER_EMAIL'],
                'from_name': app.config['MAILJET_SENDER_NAME'],
                'api_keys_set': bool(app.config['MAILJET_API_KEY']) and bool(app.config['MAILJET_SECRET_KEY'])
            }
            
            # Only attempt API call if keys are set
            if validation_result['api_keys_set']:
                response = mailjet.send.create(data=data, sandbox=True)  # Use sandbox mode to not actually send
                validation_result['api_response'] = {
                    'status_code': response.status_code,
                    'success': response.status_code == 200
                }
            
        except Exception as e:
            validation_result = {
                'error': str(e),
                'traceback': traceback.format_exc()
            }
        
        return jsonify(validation_result)
    
    @app.route('/debug/user-check/<email>', methods=['GET'])
    def debug_user_check(email):
        """Check if a user exists (only in development)"""
        # Only allow in development mode
        if not app.config.get('DEBUG') and os.environ.get('FLASK_ENV') != 'development':
            return "This endpoint is only available in development mode", 403
        
        # Check if user exists (safely)
        user = User.query.filter_by(email=email).first()
        
        return jsonify({
            'user_exists': user is not None,
            'email_checked': email
        })

    return app
