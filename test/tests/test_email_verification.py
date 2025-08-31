import pytest
from time import sleep

def test_email_verification_flow(client, clean_test_db):
    """Test email verification flow"""
    conn = None
    cursor = None
    try:
        # First ensure clean database state
        conn = clean_test_db
        cursor = conn.cursor()
        cursor.execute("SELECT DATABASE()")
        db_name = cursor.fetchone()['DATABASE()']
        assert db_name == 'test_pocketfreud', "Wrong database in use"
        
        # Create user
        response = client.post('/signup_with_plan', data={
            'username': 'verifyuser',
            'email': 'verify@example.com',
            'password': 'testpass123',
            'plan': 'basic',
            'g-recaptcha-response': 'test'
        }, follow_redirects=True)
        assert response.status_code == 200
        assert b'confirmation email' in response.data
        
        # Sleep briefly to ensure transaction completes
        sleep(0.1)
        
        # Verify user was created
        cursor.execute("""
            SELECT u.*, s.plan_type, s.is_active 
            FROM users u 
            LEFT JOIN subscriptions s ON u.id = s.user_id AND s.is_active = TRUE
            WHERE u.email = 'verify@example.com'
        """)
        user = cursor.fetchone()
        conn.commit()
        assert user is not None, "User not created in database"
        assert user['username'] == 'verifyuser'
        assert user['verified'] == 0, "User should start unverified"
        assert user['plan_type'] == 'basic', "User should have basic plan"
        assert user['is_active'] == 1, "Subscription should be active"
        
        # Get verification token
        cursor.execute("""
            SELECT email_token 
            FROM users 
            WHERE email = 'verify@example.com'
        """)
        result = cursor.fetchone()
        assert result is not None, "Email token not found"
        token = result['email_token']
        assert token is not None
        
        # Try to sign in before verification should fail
        response = client.post('/signin', data={
            'email': 'verify@example.com',
            'password': 'testpass123'
        }, follow_redirects=True)
        assert b'verify your email' in response.data
        
        # Verify email
        response = client.get(f'/verify_email?token={token}', follow_redirects=True)
        assert response.status_code == 200
        
        # Now signin should work
        response = client.post('/signin', data={
            'email': 'verify@example.com',
            'password': 'testpass123'
        }, follow_redirects=True)
        assert b'Hi verifyuser' in response.data
        
    finally:
        if cursor:
            cursor.close()
