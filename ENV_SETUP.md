# Environment Variables Setup Guide

This guide explains how to set up environment variables for the Home Inventory application.

## Local Development Setup

1. Copy the sample environment file to create your local configuration:
   ```bash
   cp .env.sample .env
   ```

2. Edit the `.env` file with your actual values:
   ```bash
   # Replace these with real values
   FLASK_SECRET_KEY=your_secret_key_here
   SECURITY_PASSWORD_SALT=your_password_salt_here
   
   # For password reset functionality
   MAILJET_API_KEY=your_mailjet_api_key
   MAILJET_SECRET_KEY=your_mailjet_secret_key
   ```

3. For development, you can generate a secure random key with Python:
   ```python
   import secrets
   print(secrets.token_hex(16))  # For SECRET_KEY
   print(secrets.token_hex(16))  # For PASSWORD_SALT
   ```

## Production Deployment

In production environments, you should set environment variables directly on your hosting platform:

### Heroku
```bash
heroku config:set FLASK_SECRET_KEY=your_secret_key_here
heroku config:set SECURITY_PASSWORD_SALT=your_password_salt_here
heroku config:set MAILJET_API_KEY=your_mailjet_api_key
heroku config:set MAILJET_SECRET_KEY=your_mailjet_secret_key
```

### Docker
```bash
docker run -e FLASK_SECRET_KEY=your_secret_key_here \
           -e SECURITY_PASSWORD_SALT=your_password_salt_here \
           -e MAILJET_API_KEY=your_mailjet_api_key \
           -e MAILJET_SECRET_KEY=your_mailjet_secret_key \
           your-image-name
```

## Required Variables

The following variables are required in production:

| Variable | Description | Required in Production |
|----------|-------------|:----------------------:|
| FLASK_SECRET_KEY | Secret key for Flask sessions | Yes |
| SECURITY_PASSWORD_SALT | Salt for password hashing | Yes |
| MAILJET_API_KEY | Mailjet API Key for sending emails | Yes |
| MAILJET_SECRET_KEY | Mailjet Secret Key for sending emails | Yes |

## Optional Variables

| Variable | Description | Default |
|----------|-------------|---------|
| MAILJET_SENDER_EMAIL | Email address used as sender | noreply@homeinventory.app |
| MAILJET_SENDER_NAME | Name displayed as sender | Home Inventory App |
| NOT_BEHIND_PROXY | Set to 1 to disable ProxyFix | 0 |

## Security Notes

- Never commit your `.env` file to version control
- Use different secret keys for development and production
- Regularly rotate your production keys for enhanced security
