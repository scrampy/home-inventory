from flask import Flask, render_template, g
import os

app = Flask(__name__)

# Create a mock user class
class MockUser:
    def __init__(self, is_authenticated=True, email="test@example.com"):
        self.is_authenticated = is_authenticated
        self.email = email
        self.family_id = 1

# Set up a context processor to provide current_user to templates
@app.context_processor
def inject_user():
    # Create a mock authenticated user
    return {'current_user': MockUser()}

@app.route('/')
def index():
    return render_template('test_new_navigation.html')

@app.route('/unauthenticated')
def unauthenticated():
    # For testing the unauthenticated state
    return render_template('test_new_navigation.html', current_user=MockUser(is_authenticated=False))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)
