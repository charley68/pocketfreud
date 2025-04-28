from flask import Flask, request, jsonify, send_from_directory, redirect, url_for, render_template, session, flash
from werkzeug.middleware.proxy_fix import ProxyFix
import os
import requests
import random
import datetime
import traceback
import uuid
import pymysql
import pymysql.err
import re
import requests
import logging



logging.basicConfig(level=logging.INFO)

env = os.getenv("ENV", "prod")
is_test = env == "test"

EMAIL_REGEX = re.compile(r"[^@]+@[^@]+\.[^@]+")
static_path = "/test/static" if is_test else "/static"
app_root = "/test" if is_test else "/"

app = Flask(
    __name__,
    static_folder=os.path.join(os.path.dirname(__file__), 'static'),
    static_url_path=static_path
)

# Trust the X-Forwarded-Prefix header from Nginx and generate URLs accordingly. (Allows multi environmemnts)
app.wsgi_app = ProxyFix(app.wsgi_app, x_prefix=1)

app.secret_key = os.getenv('FLASK_SECRET_KEY', 'fallback_secret_key')
app.config['BASE_URL'] = app_root
app.config['APPLICATION_ROOT'] = app_root
app.config['SESSION_COOKIE_NAME'] = "pocketfreud_test" if env == "test" else "pocketfreud_prod"
app.config['TEMPLATES_AUTO_RELOAD'] = True # REMOVE THIS IN PROD !!!!!!!!

# Environment-based model selector
USE_OLLAMA = os.getenv('USE_OLLAMA', 'false').lower() == 'true'
openai_api_key = os.getenv("OPENAI_API_KEY")
logging.info(f"[STATIC FOLDER] Flask is serving static files from: {app.static_folder}")
logging.info(f"[TEMPLATE FOLDER] Flask is serving template files from: {app.template_folder}")



# -------------------- Helper functions --------------------

@app.context_processor
def inject_base_url():
    return dict(BASE_URL=app.config.get('BASE_URL', ''))

@app.context_processor
def inject_env():
    return dict(ENV=os.getenv("ENV", "prod"))


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
            CREATE TABLE IF NOT EXISTS mood_logs (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                mood VARCHAR(50) NOT NULL,
                note TEXT,
                timestamp DATETIME NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS journals (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                entry_date DATE NOT NULL,
                entry TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id),
                UNIQUE KEY (user_id, entry_date) 
            );
        ''')
        
        conn.commit()

def save_message_for_user(user_id, sender, message, groupTitle):
    conn = get_db_connection()
    with conn:
        cursor = conn.cursor()
        cursor.execute('INSERT INTO conversations (user_id, sender, message, archive, groupTitle) VALUES (%s, %s, %s, %s, %s)',
                       (user_id, sender, message, 0, groupTitle))
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

@app.route('/debug')
def debug_route():
    return "DEBUG ROUTE OK", 200

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
    restore_group = data.get('restore')

    conn = get_db_connection()
    with conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE conversations
            SET archive = 1
            WHERE user_id = %s AND archive = 0
        ''', ( session['user_id']))

        cursor.execute('''
            UPDATE conversations
            SET archive = 0
            WHERE user_id = %s AND groupTitle = %s
        ''', (session['user_id'], restore_group))

        conn.commit()

    return '', 204

@app.route('/api/unlabled_message_count')
def unlabled_message_count():
    if 'user_id' not in session:
        return jsonify({"count": 0})

    conn = get_db_connection()
    with conn:
        cursor = conn.cursor()
        cursor.execute(
            'SELECT COUNT(*) as count FROM conversations WHERE user_id = %s AND groupTitle IS NULL',
            (session['user_id'],)
        )
        row = cursor.fetchone()

    return jsonify({"count": row["count"]})

def is_valid_email(email):
    return bool(EMAIL_REGEX.match(email))

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email'].strip().lower()
        captcha_response = request.form.get("g-recaptcha-response")

        if not is_valid_email(email):
            flash('Invalid email format. Please enter a valid email address.')
            return redirect(url_for('signup'))
        
        if not captcha_response:
            flash("Please complete the CAPTCHA.")
            return redirect(url_for("signup"))
        
             # ✅ Verify with Google

        secret_key = os.getenv("RECAPTCHA_SECRET_KEY")
        verify_url = "https://www.google.com/recaptcha/api/siteverify"
        payload = {
            "secret": secret_key,
            "response": captcha_response,
            "remoteip": request.remote_addr
        }

        r = requests.post(verify_url, data=payload)
        result = r.json()

        if not result.get("success"):
            flash("CAPTCHA failed. Please try again.")
            return redirect(url_for("signup"))

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
def chat_load():

    if 'user_id' not in session:
        return redirect(url_for('signin'))

    conn = get_db_connection()
    cursor = conn.cursor()


    cursor.execute('''
        SELECT groupTitle FROM conversations
        WHERE user_id = %s AND archive = 0
        ORDER BY timestamp DESC LIMIT 1
    ''', (session['user_id'],))

    row = cursor.fetchone()
    groupTitle = row['groupTitle'] if row else None

    cursor.execute('''
        SELECT sender, message FROM conversations
        WHERE user_id = %s AND archive = 0
        ORDER BY timestamp ASC
        LIMIT 20
    ''', (session['user_id'],))
    messages = cursor.fetchall()

    conn.close()

    return render_template('chat.html', messages=messages, username=session.get('username'), groupTitle=groupTitle)


@app.route('/api/chat', methods=['POST'])
def chat_write():

    if 'user_id' not in session:
        print("User not authenticated.")
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        data = request.get_json(force=True)
    except Exception as e:
        print(f"Failed to parse JSON: {str(e)}")
        return jsonify({"error": "Invalid JSON payload"}), 400

    messages = data.get('messages', [])
    group_title = data.get('groupTitle')
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

        print("SAVE USER MESSAGES", flush=True)

        save_message_for_user(session['user_id'], 'user', user_prompt, group_title)
        save_message_for_user(session['user_id'], 'bot', ai_message, group_title)

        return jsonify({
            "response": ai_message
        })

    except Exception as e:
        print("❌ Exception occurred in /api/chat", flush=True)
        print(traceback.format_exc(), flush=True)
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

        mood = data['mood']
        note = data.get('note', '')
        timestamp = data['timestamp'].replace('T', ' ').replace('Z', '').split('.')[0]  # ✅ FIX HERE

        cursor.execute(
            'INSERT INTO mood_logs (user_id, mood, note, timestamp) VALUES (%s, %s, %s, %s)',
             (user_id, mood, note, timestamp)
        )
        conn.commit()
        conn.close()
        return '', 204
    else:
        return 'Unauthorized', 401
    
@app.route('/suggestions')
def suggestions():
    prompts = [
        "What's a good way to calm my anxiety?",
        "I feel stuck lately.",
        "My partner or kids are driving me crazy!",
        "I feel overwhelmed with everything today.",
        "How can I be more mindful today?",
        "I need to fina a new hobby.",
        "I feel like I'm not good enough.",
        "I feel like I'm not being heard."
    ]
    return jsonify(prompts)

@app.route("/profile", methods=["GET", "POST"])
def profile():
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("signin"))

    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == "POST":
        username = request.form.get("username")
        age = request.form.get("age")
        sex = request.form.get("sex")
        occupation = request.form.get("occupation")
        bio = request.form.get("bio")

        cursor.execute("""
            UPDATE users
            SET username = %s, age = %s, sex = %s, occupation = %s, bio = %s
            WHERE id = %s
        """, (username, age, sex, occupation, bio, user_id))
        conn.commit()
        cursor.close()
        conn.close()  # ✅ safely release DB connection
        return redirect(url_for("home"))

    cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()

    return render_template("profile.html", user=user)


@app.route('/journal', methods=['GET', 'POST'])
def journal():
    if 'user_id' not in session:
        return redirect(url_for('signin'))

    user_id = session['user_id']
    date_param = request.args.get('date')
    month_param = request.args.get('month')
    year_param = request.args.get('year')

    # If date_param exists, load that specific entry
    if date_param:
        date_obj = datetime.datetime.strptime(date_param, "%Y-%m-%d").date()
    else:
        date_obj = datetime.date.today()

    conn = get_db_connection()
    cursor = conn.cursor()

    # Load journal entry
    cursor.execute('''
        SELECT entry FROM journals WHERE user_id = %s AND entry_date = %s
    ''', (user_id, date_obj))
    row = cursor.fetchone()
    journal_text = row['entry'] if row else ''

    conn.close()

    return render_template('journal_entry.html',
                           journal_text=journal_text,
                           today=date_obj.strftime("%B %d, %Y"),
                           back_month=month_param,
                           back_year=year_param)






@app.route('/chat')
def chat():
    return render_template('chat.html')

@app.route('/journal_calendar')
def journal_calendar():
    if 'user_id' not in session:
        return redirect(url_for('signin'))

    user_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT entry_date FROM journals WHERE user_id = %s
    ''', (user_id,))
    rows = cursor.fetchall()

    # Build a list of journal entry dates formatted as 'YYYY-MM-DD'
    journal_dates = [row['entry_date'].strftime('%Y-%m-%d') for row in rows]

    conn.close()

    return render_template('journal_calendar.html', journal_dates=journal_dates)





# Initialize database
init_db()

# # This is only used for local development. In production, use Gunicorn.
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5050)


