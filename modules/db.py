import os
import pymysql
from flask import session, current_app

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
                sender VARCHAR(100) NOT NULL,
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

def save_message_for_user(user_id, sender, message, session):
    conn = get_db_connection()
    with conn:
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO conversations (user_id, sender, message, archive, session) VALUES (%s, %s, %s, %s, %s)',
            (user_id, sender, message, 0, session)
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
        cursor.execute("SELECT setting_key , setting_value  FROM user_settings WHERE user_id = %s", user_id,)
        rows = cursor.fetchall()
        conn.close()

        # Merge user overrides into defaults
        for row in rows:
            app_defaults[row['setting_key']] = row['setting_value']

        # Store merged settings in session
        session['user_settings'] = app_defaults
        dumpConfig()


def dumpConfig():
    for k, v in session['user_settings'].items():
        print(f"{k}={v}")