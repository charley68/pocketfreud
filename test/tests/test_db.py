from datetime import datetime
import pytest
from modules.db import (
    create_user,
    get_user_profile,
    create_new_session,
    get_current_session,
    save_chat_message,
    get_chat_thread
)

def test_create_user(test_db):
    """Test user creation and retrieval"""
    print("\nStarting test_create_user...")  # Debug output
    
    # Create test user
    username = "test_user"
    email = "test@example.com"
    password_hash = "hashed_password"
    email_token = "test_token"
    
    print("Creating user...")  # Debug output
    user_id = create_user(username, email, password_hash, email_token)
    print(f"User created with ID: {user_id}")  # Debug output
    assert user_id is not None
    
    print("Fetching user profile...")  # Debug output
    # Verify user was created
    profile = get_user_profile(email)
    print(f"Profile retrieved: {profile}")  # Debug output
    assert profile is not None
    assert profile['username'] == username
    # Note: email field might not be returned in profile based on the SQL query
    print("Test completed successfully.")  # Debug output

from modules.db import (
    create_user, create_new_session, get_current_session,
    save_chat_message, get_chat_thread, clear_chat_history,
    delete_session, delete_user_data
)

def test_chat_session(test_db):
    """Test chat session creation, message handling, and cleanup"""
    print("\nStarting test_chat_session...")  # Debug output
    
    user_id = None
    session_name = None
    session_name_2 = None
    
    try:
        # Create test user
        user_id = create_user("chat_test_user", "chat@example.com", "hash", "token")
        assert user_id is not None, "Failed to create test user"
        
        # Test session creation
        session_name = "test_session"
        persona = "CBT"
        create_new_session(user_id, session_name, persona)
        print("Created new session:", session_name)  # Debug output
        
        # Verify session was created 
        current = get_current_session(user_id)
        assert current is not None, "Session was not created"
        assert current['session_name'] == session_name, f"Session name mismatch: {current['session_name']} != {session_name}"
        assert current['persona'] == persona, f"Persona mismatch: {current['persona']} != {persona}"
        
        # Test message handling with timestamps
        print("Testing message handling...")  # Debug output
        save_chat_message(user_id, "user", "Hello", session_name)
        save_chat_message(user_id, "assistant", "Hi there!", session_name)
        
        # Verify messages were saved with correct order and timestamps
        messages = get_chat_thread(user_id, session_name)
        assert len(messages) == 2, f"Expected 2 messages, got {len(messages)}"
        assert messages[0]['role'] == "user"
        assert messages[0]['message'] == "Hello"
        assert messages[1]['role'] == "assistant"
        assert messages[1]['message'] == "Hi there!"
        
        # Verify timestamps are in order
        assert 'timestamp' in messages[0], "Message timestamp missing"
        assert 'timestamp' in messages[1], "Message timestamp missing"
        assert messages[0]['timestamp'] <= messages[1]['timestamp'], "Message timestamps out of order"
        
        # Test session isolation - create another session
        print("Testing session isolation...")  # Debug output
        session_name_2 = "test_session_2"
        create_new_session(user_id, session_name_2, persona)
        
        # Verify messages are isolated between sessions
        messages_2 = get_chat_thread(user_id, session_name_2)
        assert len(messages_2) == 0, f"New session should be empty, got {len(messages_2)} messages"
        
        # Verify original session still has its messages
        messages_1 = get_chat_thread(user_id, session_name)
        assert len(messages_1) == 2, f"Original session lost messages, now has {len(messages_1)}"
        
        print("Test completed successfully.")  # Debug output
        
    except Exception as e:
        print(f"Error in test_chat_session: {e}")
        raise
        
    finally:
        # Cleanup - remove test data
        print("Cleaning up test data...")  # Debug output
        try:
            if user_id:
                clear_chat_history(user_id)
                if session_name:
                    delete_session(user_id, session_name)
                if session_name_2:
                    delete_session(user_id, session_name_2)
                delete_user_data(user_id)
        except Exception as e:
            print(f"Error during cleanup: {e}")
            raise
