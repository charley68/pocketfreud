"""
Additional tests for forgot password security features
"""
import pytest
from unittest.mock import patch
import time

# Test user data
TEST_USER = {
    'username': 'testuser',
    'email': 'test@example.com',
    'password': 'testpass123',
    'plan': 'basic'
}

@pytest.fixture
def test_user(client, clean_test_db):
    """Create and verify a test user"""
    # Create user
    response = client.post('/signup_with_plan', data={
        'username': TEST_USER['username'],
        'email': TEST_USER['email'],
        'password': TEST_USER['password'],
        'plan': TEST_USER['plan'],
        'g-recaptcha-response': 'test'
    }, follow_redirects=True)
    
    # Get verification token
    cursor = clean_test_db.cursor()
    cursor.execute("SELECT email_token FROM users WHERE email = %s", (TEST_USER['email'],))
    user = cursor.fetchone()
    token = user['email_token']
    clean_test_db.commit()
    cursor.close()
    
    # Verify email
    client.get(f'/verify_email?token={token}')
    
    return TEST_USER

def test_forgot_password_honeypot_detection(client, test_user, clean_test_db):
    """Test that honeypot field detects bots"""
    response = client.post('/forgot_password', data={
        'email': test_user['email'],
        'nickname': 'bot_value'  # This should trigger bot detection
    }, follow_redirects=True)
    
    assert response.status_code == 200
    assert b'Invalid form submission' in response.data
    
    # Verify no reset token was saved
    cursor = clean_test_db.cursor()
    cursor.execute(
        "SELECT reset_token FROM users WHERE email = %s",
        (test_user['email'],)
    )
    result = cursor.fetchone()
    cursor.close()
    
    # Token should still be None since bot was detected
    assert result is None or result['reset_token'] is None

def test_forgot_password_invalid_email_format(client, clean_test_db):
    """Test invalid email format handling"""
    response = client.post('/forgot_password', data={
        'email': 'invalid-email-format'
    }, follow_redirects=True)
    
    assert response.status_code == 200
    assert b'Please enter a valid email address' in response.data

def test_forgot_password_nonexistent_user(client, clean_test_db):
    """Test password reset for non-existent user"""
    response = client.post('/forgot_password', data={
        'email': 'nonexistent@example.com'
    }, follow_redirects=True)
    
    assert response.status_code == 200
    # Should still show success message for security
    assert b'If your email is registered, a reset link has been sent' in response.data
    
    # Verify no reset token was saved anywhere
    cursor = clean_test_db.cursor()
    cursor.execute(
        "SELECT COUNT(*) as count FROM users WHERE email = %s AND reset_token IS NOT NULL",
        ('nonexistent@example.com',)
    )
    result = cursor.fetchone()
    cursor.close()
    
    assert result['count'] == 0

@patch('modules.rate_limiter.password_reset_limiter.is_allowed')
def test_forgot_password_rate_limiting(mock_is_allowed, client, test_user, clean_test_db):
    """Test rate limiting functionality"""
    # First call should be allowed
    mock_is_allowed.return_value = True
    response = client.post('/forgot_password', data={
        'email': test_user['email']
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b'If your email is registered, a reset link has been sent' in response.data
    
    # Second call should be rate limited
    mock_is_allowed.return_value = False
    with patch('modules.rate_limiter.password_reset_limiter.get_remaining_time', return_value=900):  # 15 minutes
        response = client.post('/forgot_password', data={
            'email': test_user['email']
        }, follow_redirects=True)
        assert response.status_code == 200
        assert b'Too many reset attempts' in response.data

def test_reset_token_expiration(client, test_user, clean_test_db):
    """Test that expired reset tokens are rejected"""
    from modules.db import save_user_reset_token
    from datetime import datetime, timedelta
    
    # Manually create an expired token
    token = "expired_test_token"
    
    # Simulate saving a token that's already expired
    conn = clean_test_db
    cursor = conn.cursor()
    expired_time = datetime.utcnow() - timedelta(hours=2)  # 2 hours ago
    cursor.execute(
        "UPDATE users SET reset_token = %s, reset_token_expires = %s WHERE email = %s",
        (token, expired_time, test_user['email'])
    )
    conn.commit()
    cursor.close()
    
    # Try to use the expired token
    response = client.post('/reset_password', data={
        'password': 'newpassword123'
    }, query_string={'token': token}, follow_redirects=True)
    
    assert response.status_code == 200
    assert b'Invalid or expired reset token' in response.data
