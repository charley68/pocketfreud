from flask import Flask, request, jsonify, send_from_directory, redirect, url_for, render_template, session, flash
import sqlite3
import os
import requests

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

# -------------------- Routes --------------------

# Home route
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
        email = request.form['email']
        password = request.form['password']

        conn = get_db_connection()  # ✅ use helper!
        cursor = conn.cursor()
        try:
            cursor.execute('INSERT INTO users (username, email, password) VALUES (?, ?, ?)', (username, email, password))
            conn.commit()
            flash('Account created successfully! Please log in.')
        except sqlite3.IntegrityError:
            flash('Email already exists. Please use a different email.')
        finally:
            conn.close()
        return redirect(url_for('signin'))
    return render_template('signup.html')



@app.route('/signin', methods=['GET', 'POST'])
def signin():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        conn = get_db_connection()  # ✅ use helper!
        cursor = conn.cursor()
        cursor.execute('SELECT id, username FROM users WHERE email = ? AND password = ?', (email, password))
        user = cursor.fetchone()
        conn.close()

        if user:
            session['user_id'] = user[0]
            session['username'] = user[1]
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
    messages = conn.execute(
        '''
        SELECT sender, message FROM conversations 
        WHERE user_id = ? 
        ORDER BY timestamp ASC
        LIMIT 20
        ''',
        (session['user_id'],)
    ).fetchall()
    conn.close()

    return render_template('chat.html', messages=messages, username=session['username'])


@app.route('/api/chat', methods=['POST'])
def chat():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.json
    messages = data.get('messages', [])
    if not messages:
        return jsonify({"error": "No messages provided"}), 400

    user_prompt = messages[-1]['content']

    # ✨ Prepare the conversation history
    conv_history = []

    # Always start with system prompt
    conv_history.append({
        "role": "system",
        "content": "You are PocketFreud, a gentle, empathetic AI who helps users reflect on their emotions and feel supported. You speak in a calming, non-judgmental tone."
    })

    # Fetch last 20 conversation pairs from DB (if any)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT sender, message FROM conversations 
        WHERE user_id = ? 
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

    # Add the latest user message
    conv_history.append({
        "role": "user",
        "content": user_prompt
    })

    try:
        if USE_OLLAMA:
            response = requests.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": "mistral",
                    "prompt": user_prompt  # (Ollama doesn't handle conversation history yet the same way)
                }
            )
            response.raise_for_status()
            result = response.json()
            ai_message = result["response"]

        else:
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {openai_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "gpt-3.5-turbo",
                    "messages": conv_history
                }
            )
            response.raise_for_status()
            result = response.json()
            ai_message = result["choices"][0]["message"]["content"]

        # Save to conversation DB
        conn = get_db_connection()
        with conn:
            conn.execute('INSERT INTO conversations (user_id, message, sender) VALUES (?, ?, ?)',
                         (session['user_id'], user_prompt, 'user'))
            conn.execute('INSERT INTO conversations (user_id, message, sender) VALUES (?, ?, ?)',
                         (session['user_id'], ai_message, 'bot'))

        return jsonify({"response": ai_message})

    except Exception as e:
        return jsonify({"error": str(e)}), 500



init_db()

# -------------------- Run app --------------------
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
