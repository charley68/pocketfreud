import os
import pytest
import pymysql
from app import app as flask_app
from modules.db import init_db, get_db_connection

@pytest.fixture(scope='session', autouse=True)
def setup_test_env(request):
    """Setup test environment and database before any tests run"""
    # Set testing environment variables
    os.environ['FLASK_ENV'] = 'testing'
    os.environ['TEST_MODE'] = '1'
    os.environ['DB_NAME'] = 'test_pocketfreud'
    os.environ['OPENAI_API_KEY'] = 'sk-test-key-not-real'  # Set API key for testing
    
    # Create initial connection without database
    root_conn = pymysql.connect(
        host=os.environ['DB_HOST'],
        user=os.environ['DB_USER'],
        password=os.environ['DB_PASS'],
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )
    
    try:
        with root_conn.cursor() as cursor:
            # Drop test database if it exists and create a new one
            cursor.execute("DROP DATABASE IF EXISTS test_pocketfreud")
            cursor.execute("CREATE DATABASE test_pocketfreud CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
            cursor.execute("USE test_pocketfreud")
            
            # Disable foreign key checks temporarily
            cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
            
        # Initialize schema and default data
        init_db()
        
        # Initialize session types and reset sequences
        conn = get_db_connection()
        with conn.cursor() as cursor:
            # Reset auto-increment counters for all tables
            tables = ['users', 'sessions', 'conversations', 'subscriptions', 
                     'journals', 'user_settings', 'summaries', 'payment_status']
            for table in tables:
                cursor.execute(f"ALTER TABLE {table} AUTO_INCREMENT = 1")
            
            # Clear all tables
            for table in tables:
                cursor.execute(f"DELETE FROM {table}")
            
            # Initialize session types
            cursor.execute("DELETE FROM session_types")
            cursor.executemany('''
                INSERT INTO session_types (persona, prompt) VALUES (%s, %s)
            ''', [
                ("CBT", "You are a compassionate Cognitive Behavioural Therapist..."),
                ("Casual Chat", "You are a friendly, empathetic companion..."),
                ("Life Coach", "You are a confident and encouraging life coach...")
            ])
            
            # Re-enable foreign key checks
            cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
            
            # Verify session types were created
            cursor.execute("SELECT COUNT(*) as count FROM session_types")
            count = cursor.fetchone()['count']
            assert count == 3, f"Expected 3 session types, found {count}"
            
        conn.commit()
        conn.close()
        
        def cleanup():
            """Cleanup after all tests"""
            with root_conn.cursor() as cursor:
                cursor.execute("DROP DATABASE IF EXISTS test_pocketfreud")
            root_conn.close()
        
        # Register cleanup to run after all tests
        request.addfinalizer(cleanup)
        
    except Exception as e:
        print(f"Error setting up test database: {e}")
        if root_conn:
            root_conn.close()
        raise

@pytest.fixture
def app():
    """Create and configure a new app instance for each test."""
    flask_app.config.update({
        'TESTING': True,
        'DATABASE': 'test_pocketfreud',
        'SERVER_NAME': 'test.local',
        'WTF_CSRF_ENABLED': False
    })
    return flask_app

@pytest.fixture
def client(app):
    """Create a test client for the app."""
    return app.test_client()

@pytest.fixture
def runner(app):
    """Create a test runner for the app."""
    return app.test_cli_runner()

@pytest.fixture
def test_db():
    """Get a database connection for tests."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        cursor.execute("SELECT DATABASE()")
        db_name = cursor.fetchone()['DATABASE()']
        assert db_name == 'test_pocketfreud', f"Wrong database in use: {db_name}"
        
        # Verify key tables exist
        tables = [
            'users', 'conversations', 'journals', 'user_tokens',
            'session_types', 'sessions', 'user_settings', 'summaries',
            'subscriptions', 'payment_status'
        ]
        for table in tables:
            cursor.execute(f"SHOW TABLES LIKE '{table}'")
            assert cursor.fetchone() is not None, f"Missing table: {table}"
            
        cursor.close()
        yield conn
    finally:
        conn.close()

@pytest.fixture
def clean_test_db(test_db):
    """Clean up test database before each test"""
    cursor = test_db.cursor()
    # Delete in proper order to handle foreign key constraints
    tables = [
        'summaries',              # No foreign keys
        'conversations',          # References users
        'journals',              # References users
        'user_settings',         # References users
        'user_tokens',           # References users
        'payment_status',        # References subscriptions
        'subscriptions',         # References users
        'sessions',              # References users and session_types
        'users'                  # Referenced by others
    ]
    
    # Temporarily disable foreign key checks for cleanup
    cursor.execute("SET FOREIGN_KEY_CHECKS=0")
    
    for table in tables:
        try:
            cursor.execute(f"DELETE FROM {table}")
        except Exception as e:
            print(f"Warning: Could not clean table {table}: {e}")
    
    # Re-enable foreign key checks
    cursor.execute("SET FOREIGN_KEY_CHECKS=1")
    test_db.commit()
    cursor.close()
    yield test_db

@pytest.fixture
def auth_client(client, test_user):
    """Create an authenticated client"""
    # Sign in the user
    with client.session_transaction() as sess:
        sess['user_id'] = 1
        sess['username'] = test_user['username']
        sess['verified'] = True
        sess['user_subscription'] = {
            'plan_type': 'basic',
            'is_active': True
        }
        sess['user_settings'] = {
            'typing_delay': 1000,
            'voice': 'en-US',
            'msg_retention': 50,
            'model': 'gpt-3.5-turbo',
            'theme': 'default',
            'summary_count': 100
        }
        
    return client
