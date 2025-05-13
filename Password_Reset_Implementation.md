# Password Reset Implementation Plan with Mailjet

## Current State Analysis

**Already in place:**
- Flask-Mail configuration
- `itsdangerous` is already imported and used for invitations
- `URLSafeTimedSerializer` is already configured
- User model with password hashing functionality
- Email sending patterns (for invitations)

**Missing components:**
- Mailjet integration
- Password reset routes
- Password reset templates
- Password reset token generation/verification

## Implementation Plan

### 1. Dependencies
- Add `mailjet-rest` to `requirements.txt`
- `itsdangerous` is already installed

### 2. Configuration Updates
```python
# Add to app.py configuration section
app.config['MAILJET_API_KEY'] = os.environ.get('MAILJET_API_KEY')
app.config['MAILJET_SECRET_KEY'] = os.environ.get('MAILJET_SECRET_KEY')
app.config['MAILJET_SENDER_EMAIL'] = os.environ.get('MAILJET_SENDER_EMAIL', 'noreply@yourdomain.com')
app.config['MAILJET_SENDER_NAME'] = os.environ.get('MAILJET_SENDER_NAME', 'Home Inventory App')
```

### 3. Mailjet Client Setup
```python
# Add after Flask-Mail setup
from mailjet_rest import Client
mailjet = Client(auth=(app.config['MAILJET_API_KEY'], app.config['MAILJET_SECRET_KEY']), version='v3.1')
```

### 4. Token Functions
```python
def generate_password_reset_token(email):
    """Generate a timed token for password reset"""
    return serializer.dumps(email, salt='password-reset-salt')

def verify_password_reset_token(token, expiration=3600):
    """Verify the password reset token"""
    try:
        email = serializer.loads(token, salt='password-reset-salt', max_age=expiration)
        return email
    except:
        return None
```

### 5. Email Sending Function
```python
def send_password_reset_email(user_email, reset_url):
    """Send password reset email using Mailjet"""
    data = {
        'Messages': [
            {
                'From': {
                    'Email': app.config['MAILJET_SENDER_EMAIL'],
                    'Name': app.config['MAILJET_SENDER_NAME']
                },
                'To': [{'Email': user_email}],
                'Subject': 'Reset Your Password',
                'HTMLPart': render_template('email/reset_password.html', reset_url=reset_url),
                'TextPart': render_template('email/reset_password.txt', reset_url=reset_url)
            }
        ]
    }
    return mailjet.send.create(data=data)
```

### 6. New Routes
```python
@app.route('/reset-password-request', methods=['GET', 'POST'])
def reset_password_request():
    if current_user.is_authenticated:
        return redirect(url_for('web_family'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        user = User.query.filter_by(email=email).first()
        if user:
            token = generate_password_reset_token(user.email)
            reset_url = url_for('reset_password', token=token, _external=True)
            send_password_reset_email(user.email, reset_url)
            return render_template('reset_password_request.html', submitted=True)
    
    return render_template('reset_password_request.html')

@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('web_family'))
    
    email = verify_password_reset_token(token)
    if not email:
        return redirect(url_for('auth_page'))
    
    user = User.query.filter_by(email=email).first()
    if not user:
        return redirect(url_for('auth_page'))
    
    if request.method == 'POST':
        password = request.form.get('password')
        if password:
            user.password_hash = generate_password_hash(password)
            db.session.commit()
            return redirect(url_for('auth_page', reset_success=True))
    
    return render_template('reset_password.html', token=token)
```

### 7. Templates Needed
- `reset_password_request.html` - Form to request password reset
- `reset_password.html` - Form to set new password
- `email/reset_password.html` - HTML email template
- `email/reset_password.txt` - Plain text email template

### 8. Update Auth Page
- Add "Forgot Password?" link to login form in `auth.html`

## Potential Risks and Mitigations

1. **Risk**: Existing invitation system uses the same serializer
   - **Mitigation**: Use different salt values for different token types

2. **Risk**: Email sending failures
   - **Mitigation**: Add error handling and logging for Mailjet API calls

3. **Risk**: Security concerns with token expiration
   - **Mitigation**: Set appropriate expiration time (default 1 hour)

4. **Risk**: Rate limiting/abuse prevention
   - **Mitigation**: Consider adding rate limiting for password reset requests

## Testing Requirements

1. **Unit Tests**:
   - Test token generation and verification
   - Test user lookup by email
   - Test password update functionality

2. **Integration Tests**:
   - Test the password reset request route
   - Test the password reset form submission
   - Test invalid token handling

3. **E2E Tests**:
   - Full password reset flow with Playwright
   - Verify email content (mock Mailjet in tests)

## Implementation Steps

1. Update `requirements.txt` with `mailjet-rest`
2. Add configuration settings
3. Implement token and email functions
4. Create routes for password reset
5. Create HTML templates
6. Update auth page with password reset link
7. Add tests for new functionality
8. Test manually in development environment
