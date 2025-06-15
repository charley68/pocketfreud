import json
import pytest
import os
from time import sleep
from flask import url_for
from unittest.mock import patch, Mock
from openai import OpenAI
from datetime import datetime, date

# Mock response for OpenAI API
MOCK_CHAT_RESPONSE = "Hello, I am a test response!"
MOCK_USAGE = {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}

# Test user credentials
TEST_USER = {
    'username': 'testuser',
    'email': 'test@example.com',
    'password': 'testpass123',
    'plan': 'basic'
}

@pytest.fixture(autouse=True)
def mock_openai_setup():
    # Create mock response
    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content=MOCK_CHAT_RESPONSE))]
    mock_response.usage = Mock(prompt_tokens=10, completion_tokens=20, total_tokens=30)
    
    # Create mock chat completions
    mock_completion = Mock()
    mock_completion.create.return_value = mock_response
    
    # Create mock client
    mock_client = Mock()
    mock_client.chat.completions = mock_completion
    
    # Patch both the OpenAI class and the client instance in helpers
    with patch('openai.OpenAI', return_value=mock_client) as mock_openai, \
         patch('modules.helpers.client', mock_client):
        yield mock_client

@pytest.fixture(autouse=True)
def reset_test_state(client):
    """Reset the test state before each test"""
    # Clear session data and flash messages
    with client.session_transaction() as sess:
        sess.clear()
    # Ensure we're logged out and all state is cleared
    client.get('/logout')
    # Do another session clear to remove any logout flash messages
    with client.session_transaction() as sess:
        sess.clear()

def test_user_settings(auth_client, test_db):
    """Test user settings"""
    settings = {
        'typing_delay': '1000',
        'voice': 'en-US',
        'msg_retention': '50',
        'model': 'gpt-3.5-turbo',
        'theme': 'earthy',
        'summary_count': '100'
    }
    
    # Save settings through form submission
    response = auth_client.post('/settings', data=settings, follow_redirects=True)
    assert response.status_code == 200
    
    # Verify settings were saved in database
    cursor = test_db.cursor()
    cursor.execute("SELECT * FROM user_settings WHERE setting_name IN %s", 
                  (tuple(settings.keys()),))
    saved = {row['setting_name']: row['setting_value'] for row in cursor.fetchall()}
    cursor.close()
    
    # Check each setting was saved
    for key, value in settings.items():
        assert str(saved.get(key)) == str(value), f"Setting {key} mismatch"

@pytest.fixture(autouse=True)
def mock_captcha():
    """Mock CAPTCHA validation to always pass in test environment"""
    with patch('modules.helpers.check_captcha', return_value=None) as mock:
        mock.return_value = None  # Explicitly set return value to None for successful validation
        yield mock

@pytest.fixture(autouse=True)
def mock_email_functions():
    """Mock email sending functions"""
    with patch('modules.routes.send_verification_email') as mock:
        yield mock

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

@pytest.fixture
def auth_client(client, test_user):
    """Create an authenticated client"""
    response = client.post('/signin', data={
        'email': test_user['email'],
        'password': test_user['password']
    }, follow_redirects=True)
    # Verify authentication was successful
    assert response.status_code == 200
    assert bytes(f'Hi {test_user["username"]}', 'utf-8') in response.data
    return client

def test_signup_endpoint(client, clean_test_db):
    """Test the signup API endpoint"""
    # First get the signup form with plan
    response = client.get('/signup_with_plan', query_string={'plan': 'basic'})
    assert response.status_code == 200
    
    # Then submit the signup form and follow the redirect
    response = client.post('/signup_with_plan', data={
        'username': 'testuser',
        'email': 'test@example.com',
        'password': 'testpass123',
        'plan': 'basic',
        'g-recaptcha-response': 'test'  # Mock captcha response for testing
    }, follow_redirects=True)
    
    assert response.status_code == 200
    # Changed assertion to check for successful signup message
    assert b'confirmation email' in response.data  # Check for confirmation message
    
    # Verify user was created in database
    cursor = clean_test_db.cursor()
    cursor.execute("SELECT username, verified FROM users WHERE email = 'test@example.com'")
    user = cursor.fetchone()
    assert user is not None
    assert user['username'] == 'testuser'
    assert user['verified'] == 0  # User should start unverified
    cursor.close()

def test_chat_api(client, test_db):
    """Test the chat API endpoints"""
    # First create test user with clean connection
    cursor = test_db.cursor()
    cursor.execute("SELECT DATABASE()")
    db_name = cursor.fetchone()['DATABASE()']
    assert db_name == 'test_pocketfreud', "Wrong database in use"
    
    response = client.post('/signup_with_plan', data={
        'username': 'chatuser',
        'email': 'chat@example.com',
        'password': 'testpass123',
        'plan': 'basic',
        'g-recaptcha-response': 'test'
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b'confirmation email' in response.data
    test_db.commit()
    
    # Get email verification token
    cursor.execute("""
        SELECT email_token, username, verified 
        FROM users 
        WHERE email = 'chat@example.com'
    """)
    user = cursor.fetchone()
    assert user is not None, "User not created in database"
    assert user['username'] == 'chatuser'
    assert user['verified'] == 0
    token = user['email_token']
    assert token is not None, "Email verification token not generated"
    cursor.close()
    test_db.commit()
    
    # Verify email
    response = client.get(f'/verify_email?token={token}', follow_redirects=True)
    assert response.status_code == 200
    
    # Now sign in with verified account
    response = client.post('/signin', data={
        'email': 'chat@example.com',
        'password': 'testpass123'
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b'Hi chatuser' in response.data  # Verify successful login
    
    # Test sending a chat message
    chat_request = {
        'messages': [{'role': 'user', 'content': 'Hello'}],
        'session_name': 'test_session',
        'session_type': 'CBT'
    }
    response = client.post('/api/chat', json=chat_request)
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert 'responses' in data
    assert MOCK_CHAT_RESPONSE in data['responses']

def test_signin(client, test_user):
    """Test signin functionality"""
    # Test invalid credentials
    response = client.post('/signin', data={
        'email': test_user['email'],
        'password': 'wrongpass'
    }, follow_redirects=True)
    assert b'Invalid credentials' in response.data
    
    # Test successful login
    response = client.post('/signin', data={
        'email': test_user['email'],
        'password': test_user['password']
    }, follow_redirects=True)
    # After successful login, user sees their username in greeting 
    assert bytes(f'Hi {test_user["username"]}', 'utf-8') in response.data


def test_forgot_password(client, test_user, clean_test_db):
    """Test the forgot password workflow"""
    # First clear any existing session/flash messages
    with client.session_transaction() as sess:
        sess.clear()
    
    # Test GET request
    response = client.get('/forgot_password')
    assert response.status_code == 200
    assert b'Forgot Your Password?' in response.data
    
    # Test POST request with redirect following
    response = client.post('/forgot_password', data={
        'email': test_user['email']
    }, follow_redirects=True)
    assert response.status_code == 200  # After following redirect
    assert b'If your email is registered, a reset link has been sent' in response.data
    
    # Verify that a reset token was saved in the database
    cursor = clean_test_db.cursor()
    cursor.execute(
        "SELECT reset_token FROM users WHERE email = %s",
        (test_user['email'],)
    )
    result = cursor.fetchone()
    cursor.close()
    
    assert result is not None
    assert result['reset_token'] is not None



def test_journal(auth_client, clean_test_db):
    """Test journal functionality"""
    # Create journal entry
    entry_text = "Today was a good day!"
    response = auth_client.post('/journal', data={
        'journalText': entry_text,
        'date': date.today().strftime("%Y-%m-%d")
    }, follow_redirects=True)
    assert response.status_code == 200
    
    # Get journal entry
    response = auth_client.get('/journal')
    assert entry_text.encode() in response.data
    
    # Delete journal entry
    response = auth_client.post('/delete_journal', query_string={
        'date': date.today().strftime("%Y-%m-%d")
    })
    assert response.status_code == 200

def test_mood_logging(auth_client):
    """Test mood logging"""
    response = auth_client.post('/log_mood', json={
        'mood': 5  # Scale of 1-5
    })
    assert response.status_code == 204

def test_chat_sessions(auth_client, test_db):
    """Test chat session management"""
    # Create new session
    session_name = "Test Session"
    response = auth_client.post('/api/new_session', json={
        'session_name': session_name,
        'persona': 'CBT'
    })
    assert response.status_code == 200
    
    # Verify session was created in database
    cursor = test_db.cursor()
    cursor.execute("SELECT * FROM sessions WHERE session_name = %s", (session_name,))
    session = cursor.fetchone()
    assert session is not None
    assert session['session_name'] == session_name
    cursor.close()
    
    # Add a message to the session
    response = auth_client.post('/api/chat', json={
        'messages': [{'role': 'user', 'content': 'Hello'}],
        'session_name': session_name,
        'session_type': 'CBT'  # Add session type
    })
    assert response.status_code == 200
    
    # Create a second session to make the first one non-current (so it appears in history)
    second_session_name = "Current Session"
    response = auth_client.post('/api/new_session', json={
        'session_name': second_session_name,
        'persona': 'Life Coach'
    })
    assert response.status_code == 200
    
    # Get chat history - should now show the first session (non-current)
    response = auth_client.get('/api/chat_history')
    assert response.status_code == 200
    history = json.loads(response.data)
    assert len(history) > 0
    assert any(session['session_name'] == session_name for session in history)
    
    # Verify session contents
    response = auth_client.get(f'/api/chat_thread/{session_name}')
    assert response.status_code == 200
    thread = json.loads(response.data)
    assert len(thread) > 0
    assert thread[0]['content'] == 'Hello'
    
    # Delete session
    response = auth_client.post('/api/delete_session', json={
        'session_name': session_name
    })
    assert response.status_code == 200
    
    # Verify session was deleted
    response = auth_client.get('/api/chat_history')
    history = json.loads(response.data)
    assert not any(session['name'] == session_name for session in history)

def test_profile(auth_client):
    """Test profile updates"""
    new_profile = {
        'username': 'updateduser',
        'age': '30',
        'sex': 'Male',  # Updated to match the select options in the template
        'occupation': 'Developer',
        'bio': 'Test bio'
    }
    
    response = auth_client.post('/profile', data=new_profile, follow_redirects=True)
    assert response.status_code == 200
    
    # Verify profile page shows the updated values
    response = auth_client.get('/profile')
    assert response.status_code == 200
    data = response.data.decode()
    
    # Check for select option being selected
    assert 'value="Male" selected' in data
    # Check text/number inputs
    for key in ['username', 'age', 'occupation']:
        assert f'value="{new_profile[key]}"' in data
    # Check textarea content
    assert f'<textarea name="bio">{new_profile["bio"]}</textarea>' in data

def test_user_settings(auth_client):
    """Test user settings"""
    settings = {
        'typing_delay': 1000,
        'voice': 'default',
        'msg_retention': 50,
        'model': 'gpt-3.5-turbo'
    }
    
    # Save settings
    response = auth_client.post('/settings', data=settings, follow_redirects=True)
    assert response.status_code == 200
    
    # Verify settings were saved
    response = auth_client.get('/api/user_settings')
    assert response.status_code == 200
    saved_settings = json.loads(response.data)
    for key, value in settings.items():
        assert str(saved_settings[key]) == str(value), f"Setting {key} mismatch"
    
    # Verify settings are shown in the settings page
    response = auth_client.get('/settings')
    assert response.status_code == 200
    page_content = response.data.decode()
    assert str(settings['typing_delay']) in page_content
    assert settings['voice'] in page_content
    assert str(settings['msg_retention']) in page_content
    assert settings['model'] in page_content

def test_email_verification(client, clean_test_db):
    """Test email verification flow"""
    try:
        # First ensure clean database state
        cursor = clean_test_db.cursor()
        cursor.execute("SELECT DATABASE()")
        db_name = cursor.fetchone()['DATABASE()']
        assert db_name == 'test_pocketfreud', "Wrong database in use"
        
        # Create an unverified user
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
        clean_test_db.commit()  # Ensure any pending transactions are committed
        
        # Verify user was created properly
        cursor.execute("""
            SELECT u.*, s.plan_type, s.is_active 
            FROM users u 
            LEFT JOIN subscriptions s ON u.id = s.user_id AND s.is_active = TRUE
            WHERE u.email = 'verify@example.com'
        """)
        user = cursor.fetchone()
        assert user is not None, "User not created in database"
        assert user['username'] == 'verifyuser'
        assert user['verified'] == 0, "User should start unverified"
        assert user['plan_type'] == 'basic', "User should have basic plan"
        assert user['is_active'] == 1, "Subscription should be active"
        
        # Try to sign in before verification should fail
        response = client.post('/signin', data={
            'email': 'verify@example.com',
            'password': 'testpass123'
        }, follow_redirects=True)
        assert b'verify your email' in response.data
        
        # Get verification token
        cursor.execute("SELECT email_token FROM users WHERE email = 'verify@example.com'")
        result = cursor.fetchone()
        assert result is not None, "User not found in database"
        token = result['email_token']
        assert token is not None, "Email token not found"
        clean_test_db.commit()
        
        # Verify email
        response = client.get(f'/verify_email?token={token}', follow_redirects=True)
        assert response.status_code == 200
        
        # Now signin should work
        response = client.post('/signin', data={
            'email': 'verify@example.com',
            'password': 'testpass123'
        }, follow_redirects=True)
        # Success should redirect to home page showing username
        assert b'Hi verifyuser' in response.data
        
    finally:
        if cursor:
            cursor.close()

def test_resend_verification(client, clean_test_db):
    """Test resending verification email"""
    try:
        # Create unverified user
        response = client.post('/signup_with_plan', data={
            'username': 'resenduser', 
            'email': 'resend@example.com',
            'password': 'testpass123',
            'plan': 'basic',
            'g-recaptcha-response': 'test'
        }, follow_redirects=True)
        assert response.status_code == 200
        assert b'confirmation email' in response.data
        
        # Sleep briefly to ensure transaction completes
        sleep(0.1)
        clean_test_db.commit()
        
        # Get the initial token and verify it exists
        cursor = clean_test_db.cursor()
        cursor.execute("""
            SELECT email_token, verified 
            FROM users 
            WHERE email = 'resend@example.com'
        """)
        user = cursor.fetchone()
        assert user is not None, "User not created in database"
        assert user['verified'] == 0, "User should be unverified"
        initial_token = user['email_token']
        assert initial_token is not None, "Initial email token not generated"
        clean_test_db.commit()
        
        # Request new verification email
        response = client.get('/resend_verification', query_string={
            'email': 'resend@example.com'
        }, follow_redirects=True)
        assert response.status_code == 200
        assert b'verification email has been sent' in response.data
        
        # Verify new token was generated
        cursor.execute("""
            SELECT email_token, verified 
            FROM users 
            WHERE email = 'resend@example.com'
        """)
        user = cursor.fetchone()
        assert user['email_token'] != initial_token, "Token should be regenerated"
        assert user['verified'] == 0, "User should still be unverified"
        clean_test_db.commit()
        
        # Verify old token is invalidated and new token is created
        cursor.execute(
            "SELECT email_token, verified FROM users WHERE email = 'resend@example.com'"
        )
        user = cursor.fetchone()
        clean_test_db.commit()
        
        assert user['email_token'] is not None
        assert user['email_token'] != initial_token  # Token should be different
        assert user['verified'] == 0  # Still unverified
        
    finally:
        if cursor:
            cursor.close()

def test_subscription_management(auth_client):
    """Test subscription management functionality"""
    # Test viewing subscription options
    response = auth_client.get('/subscribe')
    assert response.status_code == 200
    
    # Test changing subscription page shows current plan indicator
    response = auth_client.get('/change_subscription')
    assert response.status_code == 200
    assert b'Current Plan' in response.data
    
    # Verify basic plan is marked as current
    assert b'class="btn disabled"' in response.data
    assert b'\xe2\x9c\x85 Current Plan' in response.data  # ✅ Current Plan
    
    # Test updating to professional plan
    response = auth_client.get('/update_user_subscription/professional', follow_redirects=True)
    assert response.status_code == 200
    # Verify the professional plan is now current
    response = auth_client.get('/change_subscription')
    assert b'class="plan professional"' in response.data
    
    # Test invalid plan
    response = auth_client.get('/update_user_subscription/invalid', follow_redirects=True)
    assert response.status_code == 400  # Should return bad request for invalid plan

def test_api_routes(auth_client):
    """Test various API endpoints"""
    # Test casual chat API
    chat_request = {
        'messages': [{'role': 'user', 'content': 'Hello'}]
    }
    response = auth_client.post('/api/casual_chat', json=chat_request)
    assert response.status_code == 200
    data = json.loads(response.data)
    assert 'responses' in data
    
    # Test insights summary API
    response = auth_client.get('/api/insights_summary', query_string={'days': 7})
    assert response.status_code == 200
    data = json.loads(response.data)
    assert 'summary' in data
    assert 'themes' in data
    
    # Test mood data API
    response = auth_client.get('/api/mood_data', query_string={'days': 7})
    assert response.status_code == 200
    data = json.loads(response.data)
    assert isinstance(data, list)
    
    # Test current session API
    response = auth_client.get('/api/current_session')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert 'session_name' in data
    
    # Test token usage API
    response = auth_client.get('/api/token_usage')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert 'month_tokens' in data

def test_static_routes(client):
    """Test static and informational routes"""
    # Test home page
    response = client.get('/')
    assert response.status_code == 200
    assert b'PocketFreud' in response.data
    
    # Test about page
    response = client.get('/about')
    assert response.status_code == 200
    assert b'Learn More About PocketFreud' in response.data
    
    # Test terms page
    response = client.get('/terms')
    assert response.status_code == 200
    assert b'Terms of Use' in response.data
    
    # Test privacy page
    response = client.get('/privacy')
    assert response.status_code == 200
    assert b'Privacy Policy' in response.data
    
    # Test debug route
    response = client.get('/debug')
    assert response.status_code == 200
    assert b'DEBUG ROUTE OK' in response.data
    
    # Test logout
    response = client.get('/logout', follow_redirects=True)
    assert response.status_code == 200
    # After logout, should see the main page with sign in/sign up buttons
    # Note: The actual text might be "Sign up" (lowercase) or "Sign Up" (uppercase)
    # depending on which template is shown
    page_content = response.data.decode()
    assert 'Sign In' in page_content or 'sign in' in page_content.lower()
    assert 'sign up' in page_content.lower()  # Check for either case

def test_error_handling(client, auth_client):
    """Test error handling in various routes"""
    # Note: Don't clear sessions here as auth_client needs its session intact
    
    # Test accessing protected route without auth (use fresh client)
    fresh_client = client.application.test_client()
    response = fresh_client.get('/profile', follow_redirects=False)
    assert response.status_code == 302  # Should redirect to signin
    assert '/signin' in response.headers['Location']  # Verify redirect target
    
    # Test invalid verification token (use fresh client)
    response = fresh_client.get('/verify_email?token=invalid', follow_redirects=True)
    assert b'Verification failed or already completed' in response.data
    
    # Test invalid password reset token (use fresh client)
    response = fresh_client.post('/reset_password?token=invalid', data={
        'password': 'newpass123'
    }, follow_redirects=True)
    assert b'Invalid or expired reset token' in response.data
    
    # Test malformed chat request
    response = auth_client.post('/api/chat', json={})
    assert response.status_code == 400  # Missing required fields should return 400
    
    # Test creating journal entry with invalid date
    response = auth_client.post('/journal', data={
        'journalText': 'Test entry',
        'date': 'invalid-date'
    })
    assert response.status_code != 200  # Should fail with invalid date
    
    # Test deleting non-existent chat session
    response = auth_client.post('/api/delete_session', json={
        'session_name': 'nonexistent-session'
    })
    assert response.status_code == 200  # Should succeed but do nothing
    
    # Test invalid session type
    response = auth_client.post('/api/new_session', json={
        'session_name': 'Test Session',
        'persona': 'InvalidType'
    })
    assert response.status_code == 400  # Should fail with invalid persona type

def test_restore_chat_functionality(auth_client, test_db):
    """Test the restore chat session functionality"""
    try:
        cursor = test_db.cursor()
        
        # Create multiple test sessions
        session1_name = "Test Session 1"
        session2_name = "Test Session 2"
        
        # Create first session
        response = auth_client.post('/api/new_session', json={
            'session_name': session1_name,
            'persona': 'CBT'
        })
        assert response.status_code == 200
        
        # Add messages to first session
        response = auth_client.post('/api/chat', json={
            'messages': [{'role': 'user', 'content': 'Hello from session 1'}],
            'session_name': session1_name,
            'session_type': 'CBT'
        })
        assert response.status_code == 200
        
        # Create second session (this should make it the current session)
        response = auth_client.post('/api/new_session', json={
            'session_name': session2_name,
            'persona': 'Life Coach'
        })
        assert response.status_code == 200
        
        # Add messages to second session
        response = auth_client.post('/api/chat', json={
            'messages': [{'role': 'user', 'content': 'Hello from session 2'}],
            'session_name': session2_name,
            'session_type': 'Life Coach'
        })
        assert response.status_code == 200
        
        # Verify session 2 is currently active
        cursor.execute("""
            SELECT session_name, current FROM sessions 
            WHERE session_name IN (%s, %s)
            ORDER BY session_name
        """, (session1_name, session2_name))
        sessions = cursor.fetchall()
        assert len(sessions) == 2
        
        # Find which session is current
        current_sessions = {s['session_name']: s['current'] for s in sessions}
        assert current_sessions[session1_name] == 0, "Session 1 should not be current"
        assert current_sessions[session2_name] == 1, "Session 2 should be current"
        
        # Test restoring session 1
        response = auth_client.post('/api/restore_chat', json={
            'restore': session1_name
        })
        assert response.status_code == 204
        
        # Close the test cursor and create a fresh connection to see committed changes
        cursor.close()
        
        # Import the same database connection function used by the app
        from modules.db import get_db_connection
        fresh_conn = get_db_connection()
        fresh_cursor = fresh_conn.cursor()
        
        try:
            # Debug: Let's see what's in the database after restore using fresh connection
            fresh_cursor.execute("""
                SELECT session_name, current, user_id FROM sessions 
                WHERE session_name IN (%s, %s)
                ORDER BY session_name
            """, (session1_name, session2_name))
            sessions = fresh_cursor.fetchall()
            print(f"After restore, sessions: {sessions}")
            
            # Verify session 1 is now current and session 2 is not
            current_sessions = {s['session_name']: s['current'] for s in sessions}
            assert current_sessions[session1_name] == 1, f"Session 1 should now be current. Current sessions: {current_sessions}"
            assert current_sessions[session2_name] == 0, "Session 2 should no longer be current"
        finally:
            fresh_cursor.close()
            fresh_conn.close()
            # Recreate the original cursor for cleanup
            cursor = test_db.cursor()
        
        # Test restoring non-existent session
        response = auth_client.post('/api/restore_chat', json={
            'restore': 'Non-existent Session'
        })
        # This should return 404 for non-existent session
        assert response.status_code == 404
        
        # Verify the current session is still session 1 (unchanged)
        fresh_conn2 = get_db_connection()
        fresh_cursor2 = fresh_conn2.cursor()
        
        try:
            fresh_cursor2.execute("""
                SELECT session_name, current FROM sessions 
                WHERE session_name IN (%s, %s)
                ORDER BY session_name
            """, (session1_name, session2_name))
            sessions = fresh_cursor2.fetchall()
            current_sessions = {s['session_name']: s['current'] for s in sessions}
            assert current_sessions[session1_name] == 1, "Session 1 should still be current"
            assert current_sessions[session2_name] == 0, "Session 2 should still not be current"
        finally:
            fresh_cursor2.close()
            fresh_conn2.close()
        
        # Test missing restore parameter
        response = auth_client.post('/api/restore_chat', json={})
        # This should return 400 for missing parameter
        assert response.status_code == 400
        
        # Test with null restore parameter
        response = auth_client.post('/api/restore_chat', json={
            'restore': None
        })
        assert response.status_code == 400
        
        # Test with empty string restore parameter
        response = auth_client.post('/api/restore_chat', json={
            'restore': ''
        })
        assert response.status_code == 400
        
    finally:
        # Cleanup test sessions
        if cursor:
            cursor.execute("DELETE FROM conversations WHERE session IN (%s, %s)", 
                         (session1_name, session2_name))
            cursor.execute("DELETE FROM sessions WHERE session_name IN (%s, %s)", 
                         (session1_name, session2_name))
            test_db.commit()
            cursor.close()

def test_get_chat_history_functionality(auth_client, test_db):
    """Test the get_chat_history function returns all sessions correctly"""
    try:
        cursor = test_db.cursor()
        
        # Create multiple test sessions
        session1_name = "History Test Session 1"
        session2_name = "History Test Session 2"
        
        # Create first session
        response = auth_client.post('/api/new_session', json={
            'session_name': session1_name,
            'persona': 'CBT'
        })
        assert response.status_code == 200
        
        # Add messages to first session
        response = auth_client.post('/api/chat', json={
            'messages': [{'role': 'user', 'content': 'Hello from session 1'}],
            'session_name': session1_name,
            'session_type': 'CBT'
        })
        assert response.status_code == 200
        
        # Create second session (this should make it the current session)
        response = auth_client.post('/api/new_session', json={
            'session_name': session2_name,
            'persona': 'Life Coach'
        })
        assert response.status_code == 200
        
        # Add messages to second session
        response = auth_client.post('/api/chat', json={
            'messages': [{'role': 'user', 'content': 'Hello from session 2'}],
            'session_name': session2_name,
            'session_type': 'Life Coach'
        })
        assert response.status_code == 200
        
        # Now test get_chat_history API endpoint
        response = auth_client.get('/api/chat_history')
        assert response.status_code == 200
        
        history = json.loads(response.data)
        assert isinstance(history, list), "Chat history should return a list"
        
        # Should only have 1 session in history (session1), not session2 which is current
        assert len(history) == 1, f"Should have 1 non-current session in history, got {len(history)}"
        
        # Verify only non-current sessions are present
        session_names = {session['session_name'] for session in history}
        expected_names = {session1_name}  # session2 should NOT be included as it's current
        assert session_names == expected_names, f"Expected non-current sessions: {expected_names}, Got: {session_names}"
        
        # Verify each session has the expected fields
        for session in history:
            assert 'session_name' in session, "Session should have 'session_name' field"
            assert 'type' in session, "Session should have 'type' field"
            assert 'message_count' in session, "Session should have 'message_count' field"
            assert session['message_count'] >= 2, f"Each session should have at least 2 messages (user + assistant), got {session['message_count']}"
        
        # Verify session types are correct
        session_types = {session['session_name']: session['type'] for session in history}
        assert session_types[session1_name] == 'CBT'
        
        # Verify that the current session (session2) is NOT in history
        assert session2_name not in session_names, "Current session should not appear in chat history"
        
        # Test that non-current sessions are included, current sessions are excluded
        # First, verify only session2 is current
        cursor.execute("""
            SELECT session_name, current FROM sessions 
            WHERE session_name IN (%s, %s)
            ORDER BY session_name
        """, (session1_name, session2_name))
        sessions = cursor.fetchall()
        
        current_sessions = {s['session_name']: s['current'] for s in sessions}
        assert current_sessions[session1_name] == 0, "Session 1 should not be current"
        assert current_sessions[session2_name] == 1, "Session 2 should be current"
        
        # Only non-current sessions should appear in history (session1 but not session2)
        # This verifies the correct logic: "WHERE s.current = 0"
        assert len(history) == 1, "Only non-current sessions should be in history"
        
        print("✅ get_chat_history test passed - all sessions returned correctly")
        
    finally:
        # Cleanup test sessions
        if cursor:
            cursor.execute("DELETE FROM conversations WHERE session IN (%s, %s)", 
                         (session1_name, session2_name))
            cursor.execute("DELETE FROM sessions WHERE session_name IN (%s, %s)", 
                         (session1_name, session2_name))
            test_db.commit()
            cursor.close()
