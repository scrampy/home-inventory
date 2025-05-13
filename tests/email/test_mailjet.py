import os
import sys
from mailjet_rest import Client
from flask import Flask, render_template_string

# Create a simple Flask app for template rendering
app = Flask(__name__)

# Load environment variables
from dotenv import load_dotenv
# Force reload of environment variables
load_dotenv(override=True)

# Set up logging
import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Print environment variables (redacting sensitive info)
env_vars = {
    'MAILJET_API_KEY': os.environ.get('MAILJET_API_KEY', '')[:4] + '...' if os.environ.get('MAILJET_API_KEY') else 'Not set',
    'MAILJET_SECRET_KEY': os.environ.get('MAILJET_SECRET_KEY', '')[:4] + '...' if os.environ.get('MAILJET_SECRET_KEY') else 'Not set',
    'MAILJET_SENDER_EMAIL': os.environ.get('MAILJET_SENDER_EMAIL', 'Not set'),
    'MAILJET_SENDER_NAME': os.environ.get('MAILJET_SENDER_NAME', 'Not set')
}

# Print actual environment variables for debugging
logger.info(f"Actual MAILJET_SENDER_EMAIL: {os.environ.get('MAILJET_SENDER_EMAIL')}")

logger.info("Environment variables:")
for key, value in env_vars.items():
    logger.info(f"{key}: {value}")

# Initialize Mailjet client
try:
    mailjet = Client(
        auth=(os.environ.get('MAILJET_API_KEY'), os.environ.get('MAILJET_SECRET_KEY')),
        version='v3.1'
    )
    logger.info("Mailjet client initialized successfully")
except Exception as e:
    logger.error(f"Error initializing Mailjet client: {e}")
    sys.exit(1)

# Simple HTML template for testing
html_template = """
<!DOCTYPE html>
<html>
<head>
    <title>Password Reset</title>
</head>
<body>
    <h1>Reset Your Password</h1>
    <p>Click the link below to reset your password:</p>
    <p><a href="{{ reset_url }}">Reset Password</a></p>
    <p>If you did not request a password reset, please ignore this email.</p>
</body>
</html>
"""

text_template = """
Reset Your Password

Click the link below to reset your password:
{{ reset_url }}

If you did not request a password reset, please ignore this email.
"""

def send_test_email(recipient_email, reset_url="http://example.com/reset"):
    """Send a test email using Mailjet"""
    logger.info(f"Attempting to send email to {recipient_email}")
    
    # Use Flask application context
    with app.app_context():
        # Render templates
        html_content = render_template_string(html_template, reset_url=reset_url)
        text_content = render_template_string(text_template, reset_url=reset_url)
    
    # Prepare data for Mailjet
    data = {
        'Messages': [
            {
                'From': {
                    'Email': os.environ.get('MAILJET_SENDER_EMAIL'),
                    'Name': os.environ.get('MAILJET_SENDER_NAME')
                },
                'To': [{'Email': recipient_email}],
                'Subject': 'Test: Reset Your Password',
                'HTMLPart': html_content,
                'TextPart': text_content
            }
        ]
    }
    
    logger.debug(f"Email data: {data}")
    
    # Send email
    try:
        logger.info("Sending email via Mailjet API...")
        response = mailjet.send.create(data=data)
        status_code = response.status_code
        json_response = response.json()
        
        logger.info(f"Mailjet API response status code: {status_code}")
        logger.info(f"Mailjet API response: {json_response}")
        
        if status_code == 200:
            logger.info("Email sent successfully!")
            return True, json_response
        else:
            logger.error(f"Failed to send email. Status code: {status_code}")
            return False, json_response
    except Exception as e:
        logger.error(f"Exception while sending email: {str(e)}")
        return False, {"error": str(e)}

if __name__ == "__main__":
    recipient = "scrampy@gmail.com"
    success, response = send_test_email(recipient)
    
    if success:
        print(f"✅ Email sent successfully to {recipient}")
    else:
        print(f"❌ Failed to send email to {recipient}")
        print(f"Error: {response}")
