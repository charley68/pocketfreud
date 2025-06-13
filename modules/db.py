import os
import pymysql
from flask import session, current_app, jsonify

def get_db_connection():
    return pymysql.connect(
        host=os.environ['DB_HOST'],
        user=os.environ['DB_USER'],
        password=os.environ['DB_PASS'],
        database=os.environ['DB_NAME'],
        cursorclass=pymysql.cursors.DictCursor
    )

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
                persona VARCHAR(255),   -- CHANGE THIS TO SESSION_NAME
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

def save_message_for_user(user_id, role, message, session):
    conn = get_db_connection()
    with conn:
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO conversations (user_id, role, message, archive, session) VALUES (%s, %s, %s, %s, %s)',
            (user_id, role, message, 0, session)
        )
        conn.commit()

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


def get_last_summary_checkpoint(user_id, session):

    conn = get_db_connection()
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


def get_messages_after(user_id, session, last_msg_id):

    conn = get_db_connection()
    query = """
        SELECT role, message FROM conversations
        WHERE user_id = %s AND session = %s AND id > %s
        ORDER BY id ASC
    """
    with conn.cursor() as cursor:
        cursor.execute(query, (user_id, session, last_msg_id))
        rows = cursor.fetchall()
        return [{"role": r["role"], "content": r["message"]} for r in rows]


def save_summary(user_id, session, summary_text, last_msg_id):

    conn = get_db_connection()
    query = """
        INSERT INTO summaries (user_id, session, summary, last_message_id, created_at)
        VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
    """
    with conn.cursor() as cursor:
        cursor.execute(query, (user_id, session, summary_text, last_msg_id))
        conn.commit()

def get_journals_by_days(user_id, days):
    conn = get_db_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute("""
        SELECT entry_date, mood, entry
        FROM journals
        WHERE user_id = %s AND entry_date >= CURDATE() - INTERVAL %s DAY
        ORDER BY entry_date
    """, (user_id, days))
    return cursor.fetchall()

def verify_user_email(token):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE email_token = %s", (token,))
    user = cursor.fetchone()

    if user:
        cursor.execute("""
            UPDATE users
            SET verified = TRUE, email_token = NULL
            WHERE id = %s
        """, (user['id'],))
        conn.commit()
        cursor.close()
        conn.close()
        return True
    return False

def check_user_exists(email):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
    exists = cursor.fetchone() is not None
    cursor.close()
    conn.close()
    return exists

def create_user(username, email, password_hash, email_token):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO users (username, email, password, email_token) VALUES (%s, %s, %s, %s)",
        (username, email, password_hash, email_token)
    )
    user_id = cursor.lastrowid
    conn.commit()
    cursor.close()
    conn.close()
    return user_id

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
    cursor.execute("UPDATE users SET reset_token = %s WHERE email = %s", (token, email))
    conn.commit()
    cursor.close()
    conn.close()

def update_user_password(token, password_hash):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET password = %s, reset_token = NULL WHERE reset_token = %s", (password_hash, token))
    affected = cursor.rowcount
    conn.commit()
    cursor.close()
    conn.close()
    return affected > 0

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
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT session_name, start_date FROM sessions 
        WHERE user_id = %s AND current = 0  
        ORDER BY start_date DESC
    ''', (user_id,))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows

def restore_chat(user_id, session_name):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('UPDATE sessions SET current = 0 WHERE user_id = %s AND current = 1', (user_id,))
    cursor.execute('UPDATE sessions SET current = 1 WHERE user_id = %s AND session_name = %s', (user_id, session_name))
    conn.commit()
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
    conn = get_db_connection()
    cursor = conn.cursor()
    # Mark existing sessions as not current
    cursor.execute('UPDATE sessions SET current = FALSE WHERE user_id = %s', (user_id,))
    # Create new session
    cursor.execute('''
        INSERT INTO sessions (user_id, session_name, persona, current)
        VALUES (%s, %s, %s, TRUE)
    ''', (user_id, session_name, persona))
    conn.commit()
    cursor.close()
    conn.close()

def delete_session(user_id, session_name):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE from sessions WHERE user_id = %s and session_name = %s', 
                  (user_id, session_name))
    conn.commit()
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
    cursor.execute(
        "INSERT INTO subscriptions (user_id, plan_type, billing_cycle) VALUES (%s, %s, %s)",
        (user_id, plan_type, billing_cycle)
    )
    conn.commit()
    cursor.close()
    conn.close()

def update_subscription(user_id, plan_type):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE subscriptions
        SET plan_type = %s, updated_at = NOW()
        WHERE user_id = %s
    """, (plan_type, user_id))
    conn.commit()
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
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, verified FROM users WHERE email = %s", (email,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()
    return user

def update_verification_token(user_id, token):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET email_token = %s WHERE id = %s", (token, user_id))
    conn.commit()
    cursor.close()
    conn.close()

def save_chat_message(user_id, role, message, session_name, archive=0):
    """Save a chat message to the conversations table"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO conversations (user_id, role, message, archive, session) VALUES (%s, %s, %s, %s, %s)',
        (user_id, role, message, archive, session_name)
    )
    conn.commit()
    cursor.close()
    conn.close()

def track_token_usage(user_id, total_tokens, month_year):
    """Track token usage for a user for the current month"""
    conn = get_db_connection()
    cursor = conn.cursor() 
    cursor.execute("""
        INSERT INTO user_tokens (user_id, token_month, month_tokens)
        VALUES (%s, %s, %s)
        ON DUPLICATE KEY UPDATE month_tokens = month_tokens + %s
    """, (user_id, month_year, total_tokens, total_tokens))
    conn.commit()
    cursor.close()
    conn.close()

def get_chat_sessions(user_id):
    """Get all chat sessions for a user"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT DISTINCT session, timestamp 
        FROM conversations 
        WHERE user_id = %s
        ORDER BY timestamp DESC
    ''', (user_id,))
    sessions = cursor.fetchall()
    cursor.close()
    conn.close()
    return sessions

def get_chat_session(user_id, session_name):
    """Get all messages from a specific chat session"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT role, message, timestamp 
        FROM conversations 
        WHERE user_id = %s AND session = %s
        ORDER BY timestamp ASC
    ''', (user_id, session_name))
    messages = cursor.fetchall()
    cursor.close()
    conn.close()
    return messages

def get_payment_status(subscription_id):
    """Get the payment status for a subscription"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT status, payment_method, last_payment_date, next_billing_date 
        FROM payment_status 
        WHERE subscription_id = %s
    """, (subscription_id,))
    status = cursor.fetchone()
    cursor.close()
    conn.close()
    return status

def get_active_subscription(user_id):
    """Get the active subscription details for a user"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, plan_type, billing_cycle, start_date, end_date, is_active
        FROM subscriptions 
        WHERE user_id = %s AND is_active = TRUE
    """, (user_id,))
    subscription = cursor.fetchone()
    cursor.close()
    conn.close()
    return subscription

def cancel_subscription(subscription_id):
    """Cancel a subscription by marking it as inactive"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE subscriptions 
        SET is_active = FALSE, updated_at = NOW()
        WHERE id = %s
    """, (subscription_id,))
    conn.commit()
    cursor.close()
    conn.close()

def update_payment_status(subscription_id, status, payment_method=None):
    """Update the payment status for a subscription"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE payment_status 
        SET status = %s, payment_method = %s, last_payment_date = CURDATE()
        WHERE subscription_id = %s
    """, (status, payment_method, subscription_id))
    if cursor.rowcount == 0:
        cursor.execute("""
            INSERT INTO payment_status (subscription_id, status, payment_method, last_payment_date)
            VALUES (%s, %s, %s, CURDATE())
        """, (subscription_id, status, payment_method))
    conn.commit()
    cursor.close()
    conn.close()

def save_chat_thread(user_id, messages, session_name, persona=""):
    """Save a complete chat thread to the database"""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Create or update session
        cursor.execute("""
            INSERT INTO sessions (user_id, session_name, persona, current)
            VALUES (%s, %s, %s, TRUE)
            ON DUPLICATE KEY UPDATE 
                persona = VALUES(persona),
                current = VALUES(current)
        """, (user_id, session_name, persona))

        # Save each message
        for msg in messages:
            cursor.execute("""
                INSERT INTO conversations 
                (user_id, role, message, session, timestamp) 
                VALUES (%s, %s, %s, %s, NOW())
            """, (user_id, msg['role'], msg['content'], session_name))
        
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cursor.close()
        conn.close()

def get_chat_thread(user_id, session_name, limit=None):
    """Get all messages in a chat thread"""
    conn = get_db_connection()
    cursor = conn.cursor()
    if limit:
        cursor.execute("""
            SELECT role, message, timestamp 
            FROM conversations 
            WHERE user_id = %s AND session = %s
            ORDER BY timestamp DESC LIMIT %s
        """, (user_id, session_name, limit))
    else:
        cursor.execute("""
            SELECT role, message, timestamp 
            FROM conversations 
            WHERE user_id = %s AND session = %s
            ORDER BY timestamp
        """, (user_id, session_name))
    messages = cursor.fetchall()
    cursor.close()
    conn.close()
    return messages

def clear_chat_history(user_id, session_name=None):
    """Clear chat history for a user, optionally for a specific session"""
    conn = get_db_connection()
    cursor = conn.cursor()
    if session_name:
        cursor.execute("""
            DELETE FROM conversations 
            WHERE user_id = %s AND session = %s
        """, (user_id, session_name))
    else:
        cursor.execute("DELETE FROM conversations WHERE user_id = %s", (user_id,))
    conn.commit()
    cursor.close()
    conn.close()

def get_user_settings_value(user_id, setting_key, default=None):
    """Get a specific setting value for a user"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT setting_value 
        FROM user_settings 
        WHERE user_id = %s AND setting_key = %s
    """, (user_id, setting_key))
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    return result['setting_value'] if result else default

def save_user_setting(user_id, setting_key, setting_value):
    """Save a single setting for a user"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO user_settings (user_id, setting_key, setting_value)
        VALUES (%s, %s, %s)
        ON DUPLICATE KEY UPDATE setting_value = VALUES(setting_value)
    """, (user_id, setting_key, setting_value))
    conn.commit()
    cursor.close()
    conn.close()

def delete_user_data(user_id):
    """Delete all data associated with a user"""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Delete in correct order to respect foreign key constraints
        cursor.execute("DELETE FROM conversations WHERE user_id = %s", (user_id,))
        cursor.execute("DELETE FROM summaries WHERE user_id = %s", (user_id,))
        cursor.execute("DELETE FROM journals WHERE user_id = %s", (user_id,))
        cursor.execute("DELETE FROM user_settings WHERE user_id = %s", (user_id,))
        cursor.execute("DELETE FROM user_tokens WHERE user_id = %s", (user_id,))
        cursor.execute("DELETE FROM sessions WHERE user_id = %s", (user_id,))
        cursor.execute("DELETE FROM subscriptions WHERE user_id = %s", (user_id,))
        cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cursor.close()
        conn.close()

def merge_user_accounts(source_user_id, target_user_id):
    """Merge data from source user into target user"""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Update foreign keys in all related tables
        tables = ['conversations', 'summaries', 'journals', 'user_settings',
                 'user_tokens', 'sessions', 'subscriptions']
        for table in tables:
            cursor.execute(f"""
                UPDATE {table} 
                SET user_id = %s 
                WHERE user_id = %s
            """, (target_user_id, source_user_id))
        
        # Delete the source user
        cursor.execute("DELETE FROM users WHERE id = %s", (source_user_id,))
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cursor.close()
        conn.close()

