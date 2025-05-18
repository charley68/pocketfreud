import os
import pymysql

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
                groupTitle VARCHAR(255),
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

        conn.commit()

def save_message_for_user(user_id, sender, message, groupTitle):
    conn = get_db_connection()
    with conn:
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO conversations (user_id, sender, message, archive, groupTitle) VALUES (%s, %s, %s, %s, %s)',
            (user_id, sender, message, 0, groupTitle)
        )
        conn.commit()