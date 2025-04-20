from flask import Flask, request, jsonify, send_from_directory, redirect, url_for, render_template, session, flash
import os
import requests
import random
import datetime
import traceback
import uuid
import pymysql
import pymysql.err

app = Flask(__name__, static_folder='static')
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'fallback_secret_key')

# Environment-based model selector
USE_OLLAMA = os.getenv('USE_OLLAMA', 'false').lower() == 'true'
openai_api_key = os.getenv("OPENAI_API_KEY")

# -------------------- Helper functions --------------------

def get_db_connection():
    conn = pymysql.connect(
        host=os.environ['DB_HOST'],
        user=os.environ['DB_USER'],
        password=os.environ['DB_PASS'],
        database=os.environ['DB_NAME'],
        cursorclass=pymysql.cursors.DictCursor
    )
    return conn

def init_db():
    conn = get_db_connection()
    with conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(255) NOT NULL,
                email VARCHAR(255) NOT NULL UNIQUE,
                password VARCHAR(255) NOT NULL
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
            CREATE TABLE IF NOT EXISTS mood_logs (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                mood VARCHAR(50) NOT NULL,
                note TEXT,
                timestamp DATETIME NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );
        ''')
        conn.commit()

def save_message_for_user(user_id, sender, message):
    conn = get_db_connection()
    with conn:
        cursor = conn.cursor()
        cursor.execute('INSERT INTO conversations (user_id, sender, message, archive) VALUES (%s, %s, %s, %s)',
                       (user_id, sender, message, 0))
        conn.commit()

def pick_initial_greeting(username):
    now = datetime.datetime.now()
    hour = now.hour

    if 5 <= hour < 12:
        greetings = [
            f"Good morning, {username}! How are you feeling today?",
            f"Morning {username}! Anything on your mind?",
            f"Hi {username}, wishing you a peaceful start to your day. How are you?"
        ]
    elif 12 <= hour < 18:
        greetings = [
            f"Good afternoon, {username}! How's your day going?",
            f"Hey {username}, how are you doing this afternoon?",
            f"Hello {username}! Need a mid-day check-in?"
        ]
    else:
        greetings = [
            f"Good evening, {username}. How was your day?",
            f"Hi {username}, how are you feeling tonight?",
            f"Hey {username}, anything you'd like to talk about before the day ends?"
        ]

    return random.choice(greetings)

# -------------------- Routes --------------------

@app.route('/')
def home():
    if 'user_id' in session:
        return render_template('home.html', username=session.get('username'))
    else:
        return render_template('index.html')

@app.route('/about')
def about():
    return render_template('learn_more.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.')
    return redirect(url_for('home'))

@app.route('/api/chat_history')
def chat_history():
    if 'user_id' not in session:
        return jsonify([])

    conn = get_db_connection()
    with conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT groupTitle, MAX(timestamp) as latest
            FROM conversations
            WHERE user_id = %s AND archive = 1
            GROUP BY groupTitle
            ORDER BY latest DESC
        ''', (session['user_id'],))
        rows = cursor.fetchall()

    return jsonify(rows)

@app.route('/api/restore_chat', methods=['POST'])
def restore_chat():
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json()
    new_label = data.get('label', 'Untitled')
    restore_group = data.get('restore')

    conn = get_db_connection()
    with conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE conversations
            SET archive = 1, groupTitle = %s
            WHERE user_id = %s AND archive = 0
        ''', (new_label, session['user_id']))

        cursor.execute('''
            UPDATE conversations
            SET archive = 0
            WHERE user_id = %s AND groupTitle = %s
        ''', (session['user_id'], restore_group))

        conn.commit()

    return '', 204

@app.route('/api/unarchived_message_count')
def unarchived_message_count():
    if 'user_id' not in session:
        return jsonify({"count": 0})

    conn = get_db_connection()
    with conn:
        cursor = conn.cursor()
        cursor.execute(
            'SELECT COUNT(*) as count FROM conversations WHERE user_id = %s AND archive = 0',
            (session['user_id'],)
        )
        row = cursor.fetchone()

    return jsonify({"count": row["count"]})

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email'].strip().lower()
        password = request.form['password']

        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('INSERT INTO users (username, email, password) VALUES (%s, %s, %s)',
                           (username, email, password))
            conn.commit()
            return render_template('signup_success.html', username=username)
        except pymysql.err.IntegrityError:
            flash('Email already exists. Please use a different email.')
            return redirect(url_for('signup'))
        finally:
            conn.close()
    return render_template('signup.html')

@app.route('/signin', methods=['GET', 'POST'])
def signin():
    if request.method == 'POST':
        email = request.form['email'].strip().lower()
        password = request.form['password']

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT id, username FROM users WHERE email = %s AND password = %s',
                        (email, password))
        user = cursor.fetchone()
        conn.close()

        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            flash('Login successful!')
            return redirect(url_for('home'))
        else:
            flash('Invalid credentials. Please try again.')
            return redirect(url_for('signin'))
    return render_template('signin.html')

@app.route('/chat')
def chat_page():
    if 'user_id' not in session:
        return redirect(url_for('signin'))

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT sender, message FROM conversations
        WHERE user_id = %s AND archive = 0
        ORDER BY timestamp ASC
        LIMIT 20
    ''', (session['user_id'],))
    messages = cursor.fetchall()

    cursor.execute('''
        SELECT groupTitle FROM conversations
        WHERE user_id = %s AND archive = 0
        ORDER BY timestamp DESC LIMIT 1
    ''', (session['user_id'],))
    row = cursor.fetchone()
    group_title = row['groupTitle'] if row else None

    conn.close()

    return render_template('chat.html', messages=messages, username=session['username'], groupTitle=group_title)

@app.route('/api/chat', methods=['POST'])
def chat():
    if 'user_id' not in session:
        print("User not authenticated.")
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        data = request.get_json(force=True)
    except Exception as e:
        print(f"Failed to parse JSON: {str(e)}")
        return jsonify({"error": "Invalid JSON payload"}), 400

    messages = data.get('messages', [])
    if not messages:
        print("No messages in request payload.")
        return jsonify({"error": "No messages provided"}), 400

    user_prompt = messages[-1]['content']

    conv_history = [{
        "role": "system",
        "content": "You are PocketFreud, a gentle, empathetic AI who helps users reflect on their emotions and feel supported. You speak in a calming, non-judgmental tone."
    }]

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT sender, message FROM conversations 
        WHERE user_id = %s AND archive = 0
        ORDER BY timestamp ASC
        LIMIT 20
    ''', (session['user_id'],))
    past_conversations = cursor.fetchall()
    conn.close()

    for conv in past_conversations:
        conv_history.append({
            "role": "user" if conv["sender"] == "user" else "assistant",
            "content": conv["message"]
        })

    conv_history.append({"role": "user", "content": user_prompt})

    try:
        if USE_OLLAMA:
            response = requests.post(
                "http://localhost:11434/api/generate",
                json={"model": "mistral", "prompt": user_prompt}
            )
            result = response.json()
            ai_message = result["response"]

        else:
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {openai_api_key}",
                    "Content-Type": "application/json",
                },
                json={"model": "gpt-3.5-turbo", "messages": conv_history}
            )
            result = response.json()
            if "choices" in result:
                ai_message = result["choices"][0]["message"]["content"]
            else:
                error_message = result.get("error", {}).get("message", "Unknown error from OpenAI API")
                print(f"OpenAI API Error: {error_message}")
                return jsonify({"error": f"OpenAI API Error: {error_message}"}), 500

        save_message_for_user(session['user_id'], 'user', user_prompt)
        save_message_for_user(session['user_id'], 'bot', ai_message)

        return jsonify({
            "response": ai_message
        })

    except Exception as e:
        print("Exception occurred in /api/chat")
        print(traceback.format_exc())
        return jsonify({"error": str(e)}), 500

@app.route('/api/new_chat', methods=['POST'])
def new_chat():
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401

    user_id = session['user_id']
    data = request.get_json()
    group_title = data.get('groupTitle', 'Untitled Chat')

    conn = get_db_connection()
    with conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE conversations
            SET archive = 1, groupTitle = %s
            WHERE user_id = %s AND archive = 0
        ''', (group_title, user_id))
        conn.commit()

    return '', 204

@app.route('/log_mood', methods=['POST'])
def log_mood():
    data = request.get_json()
    user_id = session.get('user_id')

    if user_id:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO mood_logs (user_id, mood, note, timestamp) VALUES (%s, %s, %s, %s)',
            (user_id, data['mood'], data['note'], data['timestamp'])
        )
        conn.commit()
        conn.close()
        return '', 204
    else:
        return 'Unauthorized', 401

# Initialize database
init_db()

# Run app
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
