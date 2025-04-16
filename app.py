from flask import Flask, request, jsonify, send_from_directory, redirect, url_for, render_template, session, flash
import sqlite3
import os
import requests
import random
import datetime
import traceback

app = Flask(__name__, static_folder='static')
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'fallback_secret_key')

DATABASE = '/opt/pocketfreud/database.db'

# Environment-based model selector
USE_OLLAMA = os.getenv('USE_OLLAMA', 'false').lower() == 'true'
openai_api_key = os.getenv("OPENAI_API_KEY")

# -------------------- Helper functions --------------------

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    with conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                message TEXT NOT NULL,
                sender TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')
        user_count = conn.execute('SELECT COUNT(*) FROM users').fetchone()[0]
        if user_count == 0:
            conn.execute('''
                INSERT INTO users (username, email, password)
                VALUES (?, ?, ?)
            ''', ('Steve', 'sclane68@yahoo.co.uk', 'Twins2018!'))
    conn.close()

def save_message_for_user(user_id, sender, message):
    conn = get_db_connection()
    with conn:
        conn.execute('INSERT INTO conversations (user_id, sender, message) VALUES (?, ?, ?)',
                     (user_id, sender, message))
    conn.close()


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
    return render_template('index.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.')
    return redirect(url_for('home'))

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email'].strip().lower()
        password = request.form['password']

        conn = get_db_connection()
        try:
            conn.execute('INSERT INTO users (username, email, password) VALUES (?, ?, ?)',
                         (username, email, password))
            conn.commit()
            return render_template('signup_success.html', username=username)
        except sqlite3.IntegrityError:
            flash('Email already exists. Please use a different email.')
            return redirect(url_for('signup'))
        finally:
            conn.close()
        return redirect(url_for('signin'))
    return render_template('signup.html')

@app.route('/signin', methods=['GET', 'POST'])
def signin():
    if request.method == 'POST':
        email = request.form['email'].strip().lower()
        password = request.form['password']

        conn = get_db_connection()
        user = conn.execute('SELECT id, username FROM users WHERE email = ? AND password = ?',
                            (email, password)).fetchone()
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

@app.route('/chat.html')
def serve_chat():
    if 'user_id' not in session:
        return redirect('/signin')

    conn = get_db_connection()
    messages = conn.execute('''
        SELECT sender, message FROM conversations 
        WHERE user_id = ? 
        ORDER BY timestamp ASC
        LIMIT 20
    ''', (session['user_id'],)).fetchall()

    # If no conversation yet, insert a dynamic first greeting
    if not messages:
        first_message = pick_initial_greeting(session['username'])
        save_message_for_user(session['user_id'], 'bot', first_message)

        # Re-fetch updated messages
        messages = conn.execute('''
            SELECT sender, message FROM conversations 
            WHERE user_id = ? 
            ORDER BY timestamp ASC
            LIMIT 20
        ''', (session['user_id'],)).fetchall()

    conn.close()

    return render_template('chat.html', messages=messages, username=session['username'])

@app.route('/api/chat', methods=['POST'])
def chat():
    print(">>> /api/chat route hit <<<") 
    if 'user_id' not in session:
        print("User not authenticated.")
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        data = request.get_json(force=True)  # force=True tries even if header wrong
    except Exception as e:
        print(f"Failed to parse JSON: {str(e)}")
        return jsonify({"error": "Invalid JSON payload"}), 400
    
    messages = data.get('messages', [])
    if not messages:
        print("No messages in request payload.")
        return jsonify({"error": "No messages provided"}), 400

    user_prompt = messages[-1]['content']

    # Build conversation history
    conv_history = [{
        "role": "system",
        "content": "You are PocketFreud, a gentle, empathetic AI who helps users reflect on their emotions and feel supported. You speak in a calming, non-judgmental tone."
    }]

    conn = get_db_connection()
    past_conversations = conn.execute('''
        SELECT sender, message FROM conversations 
        WHERE user_id = ? 
        ORDER BY timestamp ASC
        LIMIT 20
    ''', (session['user_id'],)).fetchall()
    conn.close()

    for conv in past_conversations:
        conv_history.append({
            "role": "user" if conv["sender"] == "user" else "assistant",
            "content": conv["message"]
        })

    # Add current user message
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


        # Save user and bot messages
        save_message_for_user(session['user_id'], 'user', user_prompt)
        save_message_for_user(session['user_id'], 'bot', ai_message)

        return jsonify({"response": ai_message})

    except Exception as e:
        print("Exception occurred in /api/chat")
        print(traceback.format_exc())   # <-- this prints the full crash stack
        return jsonify({"error": str(e)}), 500

# Initialize database
init_db()

# Run app
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
