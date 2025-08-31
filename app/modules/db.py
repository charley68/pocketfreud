def get_user_by_id(user_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, username, email, password FROM users WHERE id = %s", (user_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if row:
        return {
            'id': row['id'],
            'username': row['username'],
            'email': row['email'],
            'password': row['password']
        }
    return None
import os
import pymysql
from flask import session, current_app, jsonify
from dbutils.pooled_db import PooledDB

# Initialize connection pool at module load time
_connection_pool = None

def _init_connection_pool():
    """Initialize the database connection pool."""
    global _connection_pool
    if _connection_pool is None:
        _connection_pool = PooledDB(
            creator=pymysql,  # the database module
            maxconnections=20,  # maximum number of connections allowed
            mincached=2,  # minimum number of idle connections in pool
            maxcached=5,  # maximum number of idle connections in pool
            maxshared=3,  # maximum number of shared connections
            blocking=True,  # block if no connections available
            maxusage=None,  # maximum number of reuses of a single connection
            setsession=[],  # optional list of SQL commands to execute for sessions
            ping=1,  # ping MySQL server to check if connection is still alive
            host=os.environ['DB_HOST'],
            user=os.environ['DB_USER'],
            password=os.environ['DB_PASS'],
            database=os.environ['DB_NAME'],
            cursorclass=pymysql.cursors.DictCursor,
            charset='utf8mb4',  # ensure proper character encoding
            autocommit=False  # explicit transaction control
        )
    return _connection_pool

def get_db_connection():
    """Get a database connection from the connection pool."""
    pool = _init_connection_pool()
    return pool.connection()

def init_db():
    conn = get_db_connection()
    with conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(255) NOT NULL,
                email VARCHAR(255) NOT NULL UNIQUE,
                password VARCHAR(255) NOT NULL,
                verified BOOLEAN DEFAULT FALSE,
                email_token VARCHAR(128),
                reset_token VARCHAR(128),
                reset_token_expires TIMESTAMP NULL,  -- New field for token expiration
                age INT,
                sex VARCHAR(10),
                occupation VARCHAR(100),
                bio TEXT
            );
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS conversations (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                message TEXT NOT NULL,
                role VARCHAR(100) NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                archive BOOLEAN DEFAULT FALSE,
                session VARCHAR(255),   -- Updated from persona to session
                FOREIGN KEY (user_id) REFERENCES users(id)
            );
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS journals (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                entry_date DATE NOT NULL,
                entry TEXT,
                mood VARCHAR(20),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id),
                UNIQUE KEY (user_id, entry_date)
            );
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_tokens (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                token_month VARCHAR(6) NOT NULL,     -- e.g. '0525' for May 2025
                month_tokens INT DEFAULT 0,
                UNIQUE KEY unique_user_month (user_id, token_month)
            );
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS session_types (
                id INT AUTO_INCREMENT PRIMARY KEY,
                persona VARCHAR(100) UNIQUE,
                prompt TEXT
            );
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                session_name VARCHAR(255) NOT NULL,
                start_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                persona VARCHAR(100),
                current BOOLEAN DEFAULT TRUE,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (persona) REFERENCES session_types(persona),
                UNIQUE KEY (user_id, session_name)
            );
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_settings (
                user_id INT NOT NULL,
                setting_key VARCHAR(50) NOT NULL,
                setting_value VARCHAR(255) NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, setting_key )
            );
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS summaries (
                id INT PRIMARY KEY AUTO_INCREMENT,
                user_id INT NOT NULL,
                session VARCHAR(255) NOT NULL,  -- or session_id if you track that
                summary TEXT NOT NULL,
                last_message_id INT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS subscriptions (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                plan_type ENUM('basic', 'professional', 'premium') NOT NULL,
                billing_cycle ENUM('monthly', 'yearly') DEFAULT NULL,
                start_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                end_date DATETIME DEFAULT NULL,
                is_active BOOLEAN DEFAULT TRUE,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS payment_status (
                id INT AUTO_INCREMENT PRIMARY KEY,
                subscription_id INT NOT NULL,
                status ENUM('pending', 'paid', 'failed') NOT NULL,
                payment_method VARCHAR(50),
                last_payment_date DATE,
                next_billing_date DATE,
                FOREIGN KEY (subscription_id) REFERENCES subscriptions(id) ON DELETE CASCADE
            );
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS token_usage (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                month_year VARCHAR(6) NOT NULL,     -- e.g. '0525' for May 2025
                tokens INT DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                UNIQUE KEY (user_id, month_year)
            );
        ''')

        conn.commit()
        populate_personas()

def populate_personas():
    conn = get_db_connection()
    with conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM session_types")
        if cursor.fetchone()['count'] == 0:
            cursor.executemany('''
                INSERT INTO session_types (persona, prompt) VALUES (%s, %s)
            ''', [
                ("CBT", "You are a compassionate Cognitive Behavioural Therapist (CBT). Your role is to help the user understand, challenge, and reframe negative thoughts. Ask open, reflective questions. Use a calm, structured tone. Avoid giving direct advice — guide them to discover insights. Encourage journaling, thought records, and identifying thinking distortions."),
                ("DEMO", "This is DEMO Mode. You have limited messages and a less personal experience however you are still a compassionate Cognitive Behavioural Therapist (CBT). Your role is to help the user understand, challenge, and reframe negative thoughts. Ask open, reflective questions. Use a calm, structured tone. Avoid giving direct advice — guide them to discover insights. Encourage journaling, thought records, and identifying thinking distortions."),
                ("DBT", "You are a Dialectical Behaviour Therapist (DBT). You balance empathy and change. Use language that validates the user's emotions while encouraging healthy coping skills. Help the user manage distress, identify emotional triggers, and practice mindfulness. Be warm, clear, and nonjudgmental."),
                ("Reflective", "You are a calm and present reflective listener. Your job is to echo back what the user says to help them feel heard and gain clarity. Use paraphrasing and gentle questions like “Is that how you’re feeling?” Avoid giving advice or interpretations unless explicitly asked."),
                ("Casual Chat", "You are a friendly, empathetic companion. Your job is to offer emotional support, casual conversation, and a safe space. You can use humour, emojis, or slang if appropriate. Listen attentively and respond like a trusted friend — no therapy or deep guidance needed unless asked for."),
                ("Life Coach", "You are a confident and encouraging life coach. Help the user set goals, explore obstacles, and stay motivated. Use action-oriented language. Ask forward-focused questions like “What’s one small step you can take today?” Validate the user’s strengths. Keep energy upbeat but grounded.")
            ])
            conn.commit()

def save_message_for_user(user_id, role, message, session_name):
    """Deprecated: Use save_chat_message instead"""
    save_chat_message(user_id, role, message, session_name)

def load_prompts_from_db():
    conn = get_db_connection()
    with conn:
        cursor = conn.cursor()
        cursor.execute("SELECT persona, prompt FROM session_types")
        rows = cursor.fetchall()
        return {row['persona']: row['prompt'] for row in rows}
    

def load_user_settings(user_id):
    app_defaults = current_app.config["APP_CONFIG"].copy()

    # Load user-specific overrides
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT setting_key, setting_value FROM user_settings WHERE user_id = %s", user_id)
    rows = cursor.fetchall()


    # Merge user overrides into defaults
    for row in rows:
        app_defaults[row['setting_key']] = row['setting_value']

    # Handle summary_count (formerly msg_retention)
    if 'summary_count' not in app_defaults:
        app_defaults['summary_count'] = 100  # Default value if not set

    # Store merged settings in session
    session['user_settings'] = app_defaults

        # Load user subscription info
    cursor.execute(
        "SELECT plan_type, end_date, billing_cycle, is_active FROM subscriptions WHERE user_id = %s",
        (user_id,)
    )
    subscription_row = cursor.fetchone()

    if subscription_row:
        session['user_subscription'] = {
            'plan_type': subscription_row['plan_type'],
            'end_date': subscription_row['end_date'],
            'billing_cycle': subscription_row['billing_cycle'],
            'is_active': subscription_row['is_active'],
        }
    else:
        session['user_subscription'] = None

    conn.close()


def dumpConfig():
    for k, v in session['user_settings'].items():
        print(f"{k}={v}")

def get_next_session_name(user_id):
    
    conn = get_db_connection()
    with conn:
        cursor = conn.cursor()
        # Retrieve the current session counter without incrementing
        cursor.execute('''
            SELECT setting_value FROM user_settings 
            WHERE user_id = %s AND setting_key = 'session_counter'
        ''', (user_id,))
        result = cursor.fetchone()
        if result is None:
            # Initialize session_counter if not present
            cursor.execute('''
                INSERT INTO user_settings (user_id, setting_key, setting_value)
                VALUES (%s, 'session_counter', '1')
            ''', (user_id,))
            conn.commit()
            return "session-1"
        else:
            session_counter = int(result['setting_value'])
            return f"session-{session_counter}"

def increment_session_counter(user_id):

    conn = get_db_connection()
    with conn:
        cursor = conn.cursor()
        # Increment the session counter
        cursor.execute('''
            UPDATE user_settings
            SET setting_value = setting_value + 1
            WHERE user_id = %s AND setting_key = 'session_counter'
        ''', (user_id,))
        conn.commit()

def get_next_session_name_api(user_id):
    session_name = get_next_session_name(user_id)
    return jsonify({"defaultName": session_name})

def get_last_summary(user_id, session):
    conn = get_db_connection()
    try:
        query = """
            SELECT summary FROM summaries
            WHERE user_id = %s AND session = %s
            ORDER BY last_message_id DESC
            LIMIT 1
        """
        with conn.cursor() as cursor:
            cursor.execute(query, (user_id, session))
            row = cursor.fetchone()
            return row["summary"] if row else None
    finally:
        conn.close()


def get_last_summary_checkpoint(user_id, session):
    conn = get_db_connection()
    try:
        query = """
            SELECT last_message_id FROM summaries
            WHERE user_id = %s AND session = %s
            ORDER BY last_message_id DESC
            LIMIT 1
        """
        with conn.cursor() as cursor:
            cursor.execute(query, (user_id, session))
            row = cursor.fetchone()
            return row["last_message_id"] if row else 0
    finally:
        conn.close()


def get_messages_after(user_id, session, last_msg_id):
    conn = get_db_connection()
    try:
        query = """
            SELECT role, message FROM conversations
            WHERE user_id = %s AND session = %s AND id > %s
            ORDER BY id ASC
        """
        with conn.cursor() as cursor:
            cursor.execute(query, (user_id, session, last_msg_id))
            rows = cursor.fetchall()
            return [{"role": r["role"], "content": r["message"]} for r in rows]
    finally:
        conn.close()


def save_summary(user_id, session, summary_text, last_msg_id):
    conn = get_db_connection()
    try:
        query = """
            INSERT INTO summaries (user_id, session, summary, last_message_id, created_at)
            VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
        """
        with conn.cursor() as cursor:
            cursor.execute(query, (user_id, session, summary_text, last_msg_id))
            conn.commit()
    finally:
        conn.close()

def get_journals_by_days(user_id, days):
    conn = get_db_connection()
    try:
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        cursor.execute("""
            SELECT entry_date, mood, entry
            FROM journals
            WHERE user_id = %s AND entry_date >= CURDATE() - INTERVAL %s DAY
            ORDER BY entry_date
        """, (user_id, days))
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

def verify_user_email(token):
    """Verify a user's email using their verification token"""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # First check if token exists and user isn't already verified
        cursor.execute("""
            SELECT id, verified 
            FROM users 
            WHERE email_token = %s
        """, (token,))
        user = cursor.fetchone()
        
        if not user:
            return False
            
        if user['verified']:
            return True
            
        # Update user to verified
        cursor.execute("""
            UPDATE users
            SET verified = TRUE, email_token = NULL
            WHERE id = %s
        """, (user['id'],))
        
        conn.commit()
        return True
        
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cursor.close()
        conn.close()

def check_user_exists(email):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
    exists = cursor.fetchone() is not None
    cursor.close()
    conn.close()
    return exists

def create_user(username, email, password_hash, email_token):
    """Create a new user and initialize their settings"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Create user with NULL reset_token to ensure field is properly initialized
        cursor.execute(
            "INSERT INTO users (username, email, password, email_token, verified, reset_token) VALUES (%s, %s, %s, %s, %s, NULL)",
            (username, email, password_hash, email_token, False)
        )
        user_id = cursor.lastrowid
        
        if not user_id:
            raise Exception("Failed to create user - no ID returned")
            
        # Initialize default settings
        default_settings = [
            ('model', 'gpt-3.5-turbo'),
            ('typing_delay', '1000'),
            ('voice', 'en-US'),
            ('msg_retention', '50'),
            ('theme', 'default'),
            ('summary_count', '100')
        ]
        
        cursor.executemany(
            "INSERT INTO user_settings (user_id, setting_key, setting_value) VALUES (%s, %s, %s)",
            [(user_id, key, value) for key, value in default_settings]
        )
        
        # Create basic subscription
        cursor.execute("""
            INSERT INTO subscriptions (user_id, plan_type, is_active)
            VALUES (%s, 'basic', TRUE)
        """, (user_id,))
        
        conn.commit()
        return user_id
        
    except Exception as e:
        if conn:
            conn.rollback()
        raise e
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def get_user_profile(email):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id, username, age, sex, bio, password, verified FROM users WHERE email = %s', (email,))
    profile = cursor.fetchone()
    cursor.close()
    conn.close()
    return profile

def update_user_profile(user_id, username, age, sex, occupation, bio):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE users SET username = %s, age = %s, sex = %s, occupation = %s, bio = %s
        WHERE id = %s
    """, (username, age, sex, occupation, bio, user_id))
    conn.commit()
    cursor.close()
    conn.close()

def save_user_reset_token(email, token):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # First check if user exists
    cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
    user = cursor.fetchone()
    
    if user:
        # Token expires in 1 hour
        from datetime import datetime, timedelta
        expires_at = datetime.utcnow() + timedelta(hours=1)
        
        # Only update token if user exists
        cursor.execute(
            "UPDATE users SET reset_token = %s, reset_token_expires = %s WHERE email = %s", 
            (token, expires_at, email)
        )
        conn.commit()
        cursor.close()
        conn.close()
        return True
    else:
        cursor.close()
        conn.close()
        return False

def update_user_password(token, password_hash):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Check if token exists and is not expired
    from datetime import datetime
    cursor.execute(
        "SELECT id FROM users WHERE reset_token = %s AND reset_token_expires > %s", 
        (token, datetime.utcnow())
    )
    user = cursor.fetchone()
    
    if user:
        cursor.execute(
            "UPDATE users SET password = %s, reset_token = NULL, reset_token_expires = NULL WHERE reset_token = %s", 
            (password_hash, token)
        )
        affected = cursor.rowcount
        conn.commit()
        cursor.close()
        conn.close()
        return affected > 0
    else:
        cursor.close()
        conn.close()
        return False

def get_current_session(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT session_name, persona FROM sessions WHERE user_id = %s AND current = TRUE
    ''', (user_id,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    return row

def archive_session(user_id, session_name=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    if session_name:
        cursor.execute("""
            UPDATE conversations
            SET archive = 1, session = %s
            WHERE user_id = %s AND archive = 0
        """, (session_name, user_id))
    else:
        cursor.execute("""
            UPDATE conversations
            SET archive = 1
            WHERE user_id = %s AND archive = 0
        """, (user_id,))
    conn.commit()
    cursor.close()
    conn.close()

def delete_current_chat(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM conversations WHERE user_id = %s AND archive = 0', (user_id,))
    conn.commit()
    cursor.close()
    conn.close()

def get_chat_history(user_id):
    """Get all chat sessions for a user (excluding current active session)"""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT DISTINCT 
                s.session_name,
                s.persona as type,
                s.start_date,
                MAX(c.timestamp) as last_message,
                COUNT(c.id) as message_count
            FROM sessions s
            LEFT JOIN conversations c ON s.user_id = c.user_id AND s.session_name = c.session
            WHERE s.user_id = %s AND s.current = 0
            GROUP BY s.session_name, s.persona, s.start_date
            ORDER BY last_message DESC
        """, (user_id,))
        sessions = cursor.fetchall()
        return sessions or []
    finally:
        cursor.close()
        conn.close()

def restore_chat(user_id, session_name):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # First check if the target session exists
        cursor.execute('SELECT id FROM sessions WHERE user_id = %s AND session_name = %s', (user_id, session_name))
        session_exists = cursor.fetchone()
        
        if not session_exists:
            return False  # Session doesn't exist
        
        # Set all existing sessions to not current
        cursor.execute('UPDATE sessions SET current = 0 WHERE user_id = %s AND current = 1', (user_id,))
        
        # Set the specific session to current  
        cursor.execute('UPDATE sessions SET current = 1 WHERE user_id = %s AND session_name = %s', (user_id, session_name))
        
        conn.commit()
        return True  # Successfully restored
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cursor.close()
        conn.close()

def rename_session(user_id, old_name, new_name):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Update sessions table
    cursor.execute("""
        UPDATE sessions SET session_name = %s 
        WHERE user_id = %s AND session_name = %s
    """, (new_name, user_id, old_name))
    
    # Update conversations table
    cursor.execute("""
        UPDATE conversations SET session = %s 
        WHERE user_id = %s AND session = %s
    """, (new_name, user_id, old_name))
    
    # Update summaries table
    cursor.execute("""
        UPDATE summaries SET session = %s 
        WHERE user_id = %s AND session = %s
    """, (new_name, user_id, old_name))
    
    conn.commit()
    cursor.close()
    conn.close()

def create_new_session(user_id, session_name, persona):
    """Create a new chat session"""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Set all existing sessions to not current
        cursor.execute("""
            UPDATE sessions 
            SET current = FALSE 
            WHERE user_id = %s
        """, (user_id,))
        
        # Create new session
        cursor.execute("""
            INSERT INTO sessions (user_id, session_name, persona, current)
            VALUES (%s, %s, %s, TRUE)
        """, (user_id, session_name, persona))
        
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cursor.close()
        conn.close()

def update_session_persona(user_id, session_name, new_persona):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE sessions SET persona = %s WHERE user_id = %s AND session_name = %s",
        (new_persona, user_id, session_name)
    )
    conn.commit()
    cursor.close()
    conn.close()

def get_session_types():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT persona FROM session_types ORDER BY persona')
    types = [row['persona'] for row in cursor.fetchall()]
    cursor.close()
    conn.close()
    return types

def save_journal_entry(user_id, entry_date, entry_text, mood=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Check if entry exists
    cursor.execute('SELECT id FROM journals WHERE user_id = %s AND entry_date = %s', (user_id, entry_date))
    exists = cursor.fetchone()
    
    if exists:
        # Update existing entry
        update_fields = []
        params = []
        if entry_text is not None:
            update_fields.append("entry = %s")
            params.append(entry_text)
        if mood is not None:
            update_fields.append("mood = %s")
            params.append(mood)
        if update_fields:
            update_fields.append("updated_at = CURRENT_TIMESTAMP")
            params.extend([user_id, entry_date])
            cursor.execute(f'''
                UPDATE journals 
                SET {', '.join(update_fields)}
                WHERE user_id = %s AND entry_date = %s
            ''', params)
    else:
        # Create new entry
        cursor.execute('''
            INSERT INTO journals (user_id, entry_date, entry, mood)
            VALUES (%s, %s, %s, %s)
        ''', (user_id, entry_date, entry_text, mood))
    
    conn.commit()
    cursor.close()
    conn.close()

def get_journal_entry(user_id, entry_date):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT entry, mood FROM journals WHERE user_id = %s AND entry_date = %s', 
                  (user_id, entry_date))
    entry = cursor.fetchone()
    cursor.close()
    conn.close()
    return entry

def delete_journal_entry(user_id, entry_date):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM journals WHERE user_id = %s AND entry_date = %s", 
                  (user_id, entry_date))
    conn.commit()
    cursor.close()
    conn.close()

def get_journal_dates(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT entry_date FROM journals WHERE user_id = %s', (user_id,))
    dates = [row['entry_date'].strftime('%Y-%m-%d') for row in cursor.fetchall()]
    cursor.close()
    conn.close()
    return dates

def create_subscription(user_id, plan_type, billing_cycle=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Set any existing active subscriptions to inactive
        cursor.execute("""
            UPDATE subscriptions 
            SET is_active = FALSE, updated_at = NOW() 
            WHERE user_id = %s AND is_active = TRUE
        """, (user_id,))

        # Create new subscription
        cursor.execute("""
            INSERT INTO subscriptions (user_id, plan_type, billing_cycle, is_active) 
            VALUES (%s, %s, %s, TRUE)
        """, (user_id, plan_type, billing_cycle))
        
        subscription_id = cursor.lastrowid
        conn.commit()
        return subscription_id
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cursor.close()
        conn.close()

def update_subscription(user_id, plan_type):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Set old subscription to inactive
        cursor.execute("""
            UPDATE subscriptions 
            SET is_active = FALSE, updated_at = NOW()
            WHERE user_id = %s AND is_active = TRUE
        """, (user_id,))

        # Create new active subscription
        billing_cycle = 'monthly' if plan_type != 'basic' else None
        cursor.execute("""
            INSERT INTO subscriptions (user_id, plan_type, billing_cycle, is_active)
            VALUES (%s, %s, %s, TRUE)
        """, (user_id, plan_type, billing_cycle))
        
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cursor.close()
        conn.close()

def save_user_settings(user_id, settings):
    conn = get_db_connection()
    cursor = conn.cursor()
    for key, value in settings.items():
        cursor.execute('''
            INSERT INTO user_settings (user_id, setting_key, setting_value)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE setting_value = %s
        ''', (user_id, key, str(value), str(value)))
    conn.commit()
    cursor.close()
    conn.close()

def update_monthly_tokens(user_id, total_tokens, month_year):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE user_tokens SET month_tokens = month_tokens + %s
        WHERE user_id = %s AND token_month = %s
    """, (total_tokens, user_id, month_year))
    if cursor.rowcount == 0:
        cursor.execute("""
            INSERT INTO user_tokens (user_id, token_month, month_tokens)
            VALUES (%s, %s, %s)
        """, (user_id, month_year, total_tokens))
    conn.commit()
    cursor.close()
    conn.close()

def get_monthly_tokens(user_id, month_year):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT month_tokens FROM user_tokens
        WHERE user_id = %s AND token_month = %s
    """, (user_id, month_year))
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    return result.get("month_tokens", 0) if result else 0

def get_session_messages(user_id, session_name, limit=20):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT role, message FROM conversations 
        WHERE user_id = %s AND session = %s 
        ORDER BY timestamp ASC LIMIT %s
    ''', (user_id, session_name, limit))
    messages = cursor.fetchall()
    cursor.close()
    conn.close()
    return messages

def get_user_info(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()
    return user

def get_user_by_email_for_verification(email):
    """Get user info needed for verification process"""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT id, username, verified, email_token 
            FROM users 
            WHERE email = %s
        """, (email,))
        user = cursor.fetchone()
        return user
    finally:
        cursor.close()
        conn.close()

def save_chat_message(user_id, role, message, session_name, archive=0):
    """Save a chat message to the conversations table"""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            'INSERT INTO conversations (user_id, role, message, archive, session) VALUES (%s, %s, %s, %s, %s)',
            (user_id, role, message, archive, session_name)
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cursor.close()
        conn.close()

def update_verification_token(user_id, token):
    """Update a user's email verification token"""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE users 
            SET email_token = %s 
            WHERE id = %s
        """, (token, user_id))
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cursor.close()
        conn.close()

def get_chat_session(user_id, session_name):
    """Get a specific chat session's details"""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT session_name, persona, current
            FROM sessions
            WHERE user_id = %s AND session_name = %s
        """, (user_id, session_name))
        return cursor.fetchone()
    finally:
        cursor.close()
        conn.close()

def get_chat_thread(user_id, session_name):
    """Get all messages from a specific chat session"""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT role, message, timestamp
            FROM conversations
            WHERE user_id = %s AND session = %s
            ORDER BY timestamp ASC
        """, (user_id, session_name))
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

def track_token_usage(user_id, tokens, month_year):
    """Track token usage for a user in a specific month"""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Check if entry exists
        cursor.execute("""
            SELECT tokens 
            FROM token_usage 
            WHERE user_id = %s AND month_year = %s
        """, (user_id, month_year))
        
        row = cursor.fetchone()
        
        if row:
            # Update existing record
            cursor.execute("""
                UPDATE token_usage 
                SET tokens = tokens + %s 
                WHERE user_id = %s AND month_year = %s
            """, (tokens, user_id, month_year))
        else:
            # Create new record
            cursor.execute("""
                INSERT INTO token_usage (user_id, month_year, tokens) 
                VALUES (%s, %s, %s)
            """, (user_id, month_year, tokens))
        
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cursor.close()
        conn.close()

def delete_session(user_id, session_name):
    """Delete a chat session and its conversations"""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Delete conversations associated with the session
        cursor.execute("""
            DELETE FROM conversations 
            WHERE user_id = %s AND session = %s
        """, (user_id, session_name))
        
        # Delete the session itself
        cursor.execute("""
            DELETE FROM sessions 
            WHERE user_id = %s AND session_name = %s
        """, (user_id, session_name))
        
        # Delete any summaries associated with the session
        cursor.execute("""
            DELETE FROM summaries 
            WHERE user_id = %s AND session = %s
        """, (user_id, session_name))
        
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cursor.close()
        conn.close()

def clear_chat_history(user_id):
    """Clear all chat messages for a user"""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Delete all conversations for the user
        cursor.execute("""
            DELETE FROM conversations 
            WHERE user_id = %s
        """, (user_id,))
        
        # Delete all summaries for the user
        cursor.execute("""
            DELETE FROM summaries 
            WHERE user_id = %s
        """, (user_id,))
        
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cursor.close()
        conn.close()

def delete_user_data(user_id):
    """Delete all data associated with a user"""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Delete all user conversations and summaries
        cursor.execute("DELETE FROM conversations WHERE user_id = %s", (user_id,))
        cursor.execute("DELETE FROM summaries WHERE user_id = %s", (user_id,))
        
        # Delete sessions
        cursor.execute("DELETE FROM sessions WHERE user_id = %s", (user_id,))
        
        # Delete user settings
        cursor.execute("DELETE FROM user_settings WHERE user_id = %s", (user_id,))
        
        # Delete journal entries
        cursor.execute("DELETE FROM journals WHERE user_id = %s", (user_id,))
        
        # Delete token usage records
        cursor.execute("DELETE FROM token_usage WHERE user_id = %s", (user_id,))
        
        # Delete subscription
        cursor.execute("DELETE FROM subscriptions WHERE user_id = %s", (user_id,))
        
        # Finally delete the user
        cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
        
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cursor.close()
        conn.close()

def shutdown_connection_pool():
    """Shutdown the database connection pool. Call this when shutting down the application."""
    global _connection_pool
    if _connection_pool is not None:
        try:
            _connection_pool.close()
        except Exception as e:
            print(f"Error closing connection pool: {e}")
        finally:
            _connection_pool = None

def get_pool_info():
    """Get information about the current connection pool status (for debugging/monitoring)."""
    global _connection_pool
    if _connection_pool is None:
        return {"status": "not_initialized"}
    
    # Note: PooledDB doesn't expose all stats, but we can provide basic info
    return {
        "status": "initialized",
        "pool_type": "dbutils.pooled_db.PooledDB"
    }

def get_stats():
    """Get basic database statistics."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        # Get conversation count
        cursor.execute("SELECT COUNT(*) as count FROM conversations")
        conversation_count = cursor.fetchone()['count']
        
        # Get user count
        cursor.execute("SELECT COUNT(*) as count FROM users")
        user_count = cursor.fetchone()['count']
        
        return {
            'conversations': conversation_count,
            'users': user_count
        }
    finally:
        cursor.close()
        conn.close()

def cleanup_expired_reset_tokens():
    """Remove expired reset tokens from the database"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    from datetime import datetime
    cursor.execute(
        "UPDATE users SET reset_token = NULL, reset_token_expires = NULL WHERE reset_token_expires < %s",
        (datetime.utcnow(),)
    )
    affected = cursor.rowcount
    conn.commit()
    cursor.close()
    conn.close()
    return affected

