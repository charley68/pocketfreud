from flask import render_template, request, jsonify, redirect, url_for, session, flash
from datetime import datetime, date, timedelta
import requests
import traceback
import os
from functools import wraps
from flask import current_app
from modules.db import get_db_connection, save_message_for_user, load_user_settings, dumpConfig
from modules.helpers import inject_base_url, inject_env, is_valid_email, pick_initial_greeting, get_setting, call_llm_api

HOTLINES = {
    "GB": "0800 689 5652",
    "UK": "0800 689 5652",
    "US": "988",
    "USA": "988",
    "CA": "1-833-456-4566",
    "AU": "13 11 14",
    "IN": "91-22-27546669"
    # Add more...
}

def register_routes(app):
    # -------------------- CONTEXT PROCESSORS --------------------
    app.context_processor(inject_base_url)
    app.context_processor(inject_env)


    # -------------------- HOME & INFO --------------------
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

    @app.route('/privacy')
    def privacy():
        return render_template('privacy.html')

    @app.route('/debug')
    def debug():
        return "DEBUG ROUTE OK", 200

    # -------------------- AUTH --------------------
    @app.route('/signup', methods=['GET', 'POST'])
    def signup():
        if request.method == 'POST':
            username = request.form['username']
            email = request.form['email'].strip().lower()
            password = request.form['password']
            captcha_response = request.form.get("g-recaptcha-response")

            if not is_valid_email(email):
                flash('Invalid email format.')
                return redirect(url_for('signup'))
            if not captcha_response:
                flash("Please complete the CAPTCHA.")
                return redirect(url_for("signup"))

            r = requests.post("https://www.google.com/recaptcha/api/siteverify", data={
                "secret": os.getenv("RECAPTCHA_SECRET_KEY"),
                "response": captcha_response,
                "remoteip": request.remote_addr
            })
            if not r.json().get("success"):
                flash("CAPTCHA failed.")
                return redirect(url_for("signup"))

            conn = get_db_connection()
            try:
                cursor = conn.cursor()
                cursor.execute('INSERT INTO users (username, email, password) VALUES (%s, %s, %s)',
                               (username, email, password))
                conn.commit()
                return render_template('signup_success.html', username=username)
            except Exception:
                flash('Email already exists.')
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
            cursor.execute('SELECT id, username, age, sex, bio FROM users WHERE email = %s AND password = %s',
                           (email, password))
            profile = cursor.fetchone()
            conn.close()

            if profile:
                session['user_id'] = profile['id']
                session['username'] = profile['username']
                session['user_profile'] = {
                    'username': profile['username'],
                    'age': profile['age'],
                    'sex': profile['sex'],
                    'bio': profile['bio']
                }
                
                load_user_settings(profile['id'])
                
                flash('Login successful!')
                return redirect(url_for('home'))
            else:
                flash('Invalid credentials.')
                return redirect(url_for('signin'))

        return render_template('signin.html')

    # -------------------- CHAT --------------------
    @app.route('/therapy')
    @login_required()
    def therapy():

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT session_name, persona FROM sessions WHERE user_id = %s AND current = TRUE
        ''', (session['user_id'],))
        row = cursor.fetchone()
        sessionName = row['session_name'] if row else None
        persona = row['persona'] if row else None

        cursor.execute('''
            SELECT sender, message FROM conversations WHERE user_id = %s AND session = %s ORDER BY timestamp ASC LIMIT 20
        ''',  (session['user_id'], sessionName))
        messages = cursor.fetchall()
        conn.close()

        return render_template('bot-chat.html',  is_demo=False, is_therapy=True, is_casual = False, messages=messages, username=session.get('username'), sessionName=sessionName, sessionType=persona, user_settings=session.get('user_settings', {}))


    @app.route('/api/chat', methods=['POST'])
    @login_required()
    def chat_write():
        from modules.helpers import build_conv_history, detect_crisis_response

        data = request.get_json(force=True)
        messages = data.get('messages', [])
        session_name = data.get('session_name')
        persona = data.get('session_type')
        model = session.get('user_settings', {}).get('model')

        conv_history = build_conv_history(messages[:-1], persona)
        user_input = messages[-1]['content']
        conv_history.append({"role": "user", "content": user_input})

        responses = []

        try:
            crisis_msg = detect_crisis_response(user_input)
            if crisis_msg:
                save_message_for_user(session['user_id'], 'bot', crisis_msg, session_name)
                responses.append(crisis_msg)

            # Call OpenAI
            ai_msg, usage = call_llm_api(model, conv_history)

            total_tokens = usage.get("total_tokens", 0)
            mmYY = datetime.now().strftime("%m%y")
            user_id = session["user_id"]

            # Update token tracking
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE user_tokens SET month_tokens = month_tokens + %s
                WHERE user_id = %s AND token_month = %s
            """, (total_tokens, user_id, mmYY))
            if cursor.rowcount == 0:
                cursor.execute("""
                    INSERT INTO user_tokens (user_id, token_month, month_tokens)
                    VALUES (%s, %s, %s)
                """, (user_id, mmYY, total_tokens))
            conn.commit()
            conn.close()

            save_message_for_user(user_id, 'user', user_input, session_name)
            save_message_for_user(user_id, 'bot', ai_msg, session_name)

            responses.append(ai_msg)
            return jsonify({"responses": responses})

        except Exception as e:
            traceback.print_exc()
            return jsonify({"error": str(e)}), 500
    

    @app.route('/api/casual_chat', methods=['POST'])
    @login_required()
    def casual_chat_api():
        from modules.helpers import build_conv_history, detect_crisis_response

        model = session.get('user_settings', {}).get('model')
        data = request.get_json(force=True)
        messages = data.get('messages', [])
        persona = "Casual Chat"

        conv_history = build_conv_history(messages[:-1], persona)
        user_input = messages[-1]['content']
        conv_history.append({"role": "user", "content": user_input})

        responses = []

        try:
            crisis_msg = detect_crisis_response(user_input)
            if crisis_msg:
                responses.append(crisis_msg)

            ai_msg, usage = call_llm_api(model, conv_history)
            responses.append(ai_msg)
            return jsonify({"responses": responses})

        except Exception as e:
            traceback.print_exc()
            return jsonify({"error": str(e)}), 500

        
    @app.route('/api/demo_chat', methods=['POST'])
    def demo_chat():
        from modules.helpers import build_conv_history, detect_crisis_response

        data = request.get_json(force=True)
        messages = data.get("messages", [])
        persona = "DEMO"
        model = app.config["APP_CONFIG"]["model"]

        conv_history = build_conv_history(messages[:-1], persona)
        user_input = messages[-1]['content']
        conv_history.append({"role": "user", "content": user_input})

        responses = []

        try:
            crisis_msg = detect_crisis_response(user_input)
            if crisis_msg:
                responses.append(crisis_msg)

            ai_msg, usage = call_llm_api(model, conv_history)
            responses.append(ai_msg)
            return jsonify({"responses": responses})

        except Exception as e:
            traceback.print_exc()
            return jsonify({"error": str(e)}), 500

        
    @app.route('/settings')
    @login_required()
    def settings():
        return render_template('settings.html', username=session.get('username'),
                settings={
                    "typing_delay": get_setting("typing_delay", int),
                    "voice": get_setting("voice", str),
                    "msg_retention": get_setting("msg_retention", int),
                    "model": get_setting("model", str)
                })
    
    @app.route('/api/config', methods=['GET'])
    def get_config():
        return jsonify(app.config["APP_CONFIG"])
    

    @app.route('/api/chat_history')
    @login_required()
    def chat_history():

        conn = get_db_connection()
        with conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT session_name, start_date  FROM sessions WHERE user_id = %s AND current = 0  ORDER BY start_date DESC
            ''', (session['user_id'],))
            rows = cursor.fetchall()

        return jsonify(rows)

    @app.route('/api/restore_chat', methods=['POST'])
    @login_required()
    def restore_chat():

        data = request.get_json()
        restore_group = data.get('restore')

        conn = get_db_connection()
        with conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE sessions SET current = 0 WHERE user_id = %s AND current = 1', (session['user_id'],))
            cursor.execute('UPDATE sessions SET current = 1 WHERE user_id = %s AND session_name  = %s', (session['user_id'], restore_group))
            conn.commit()

        return '', 204


    @app.route("/api/rename_session", methods=["POST"])
    @login_required()
    def rename_session():

        data = request.get_json()
        old_name = data.get("old_name")
        new_name = data.get("new_name")
        user_id = session["user_id"]

        if not old_name or not new_name:
            return jsonify({"error": "Missing fields"}), 400

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE sessions SET session_name = %s WHERE user_id = %s AND session_name = %s
        """, (new_name, user_id, old_name))
        cursor.execute("""
            UPDATE conversations SET session = %s WHERE user_id = %s AND session = %s
        """, (new_name, user_id, old_name))
        conn.commit()
        conn.close()

        return jsonify({"status": "renamed"})
    
    
    @app.route('/change_persona', methods=['POST'])
    @login_required()
    def change_persona():

        data = request.get_json()
        current_session_name = data.get('current_session_name')
        new_persona = data.get('persona')

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "UPDATE sessions SET persona = %s WHERE user_id = %s AND session_name = %s",
            (new_persona, session['user_id'], current_session_name)
        )
        conn.commit()
        cur.close()
        conn.close()

        return jsonify({'success': True})

    

    @app.route("/api/token_usage", methods=["GET"])
    @login_required()
    def get_token_usage():

        user_id = session["user_id"]
        mmYY = datetime.now().strftime("%m%y")

        print(f"Fetching tokens for user {user_id}, month {mmYY}")

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT month_tokens FROM user_tokens
            WHERE user_id = %s AND token_month = %s
        """, (user_id, mmYY))
        result = cursor.fetchone()

        print("SQL result:", result)
        token_count = result.get("month_tokens", 0) if result else 0

        cursor.close()
        conn.close()

        return jsonify({"month_tokens": token_count})




    @app.route('/api/new_chat', methods=['POST'])
    @login_required()
    def new_chat():


        data = request.get_json()
        new_group_title = data.get('session_name')  # This might be None

        # Archive current messages, but only set groupTitle if one was given
        user_id = session['user_id']
        conn = get_db_connection()
        cur = conn.cursor()

        if new_group_title:
            cur.execute("""
                UPDATE conversations
                SET archive = 1, session = %s
                WHERE user_id = %s AND archive = 0
            """, (new_group_title, user_id))
        else:
            cur.execute("""
                UPDATE conversations
                SET archive = 1
                WHERE user_id = %s AND archive = 0
            """, (user_id,))

        conn.commit()
        cur.close()
        conn.close()

        return jsonify({'status': 'archived and ready'})


    @app.route('/api/delete_chat', methods=['POST'])
    @login_required()
    def delete_chat():

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM conversations WHERE user_id = %s AND archive = 0', (session['user_id'],))
        conn.commit()
        conn.close()
        return jsonify({'status': 'deleted'})

    @app.route('/log_mood', methods=['POST'])
    @login_required()
    def log_mood():

        user_id = session['user_id']
        data = request.get_json()
        mood = data.get('mood')

        if not mood:
            return 'Invalid data', 400

        today = date.today()
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT id FROM journals WHERE user_id = %s AND entry_date = %s', (user_id, today))
        row = cursor.fetchone()

        if row:
            cursor.execute('UPDATE journals SET mood = %s, updated_at = CURRENT_TIMESTAMP WHERE user_id = %s AND entry_date = %s', (mood, user_id, today))
        else:
            cursor.execute('INSERT INTO journals (user_id, entry_date, mood) VALUES (%s, %s, %s)', (user_id, today, mood))

        conn.commit()
        conn.close()
        return '', 204

    @app.route('/suggestions')
    def suggestions():
        return jsonify([
            "What's a good way to calm my anxiety?",
            "I feel stuck lately.",
            "My partner or kids are driving me crazy!",
            "I feel overwhelmed with everything today.",
            "How can I be more mindful today?",
            "I need to find a new hobby.",
            "I feel like I'm not good enough.",
            "I feel like I'm not being heard."
        ])

    @app.route('/profile', methods=['GET', 'POST'])
    @login_required()
    def profile():
        user_id = session.get("user_id")
        conn = get_db_connection()
        cursor = conn.cursor()

        if request.method == "POST":
            username = request.form.get("username")
            age = request.form.get("age")
            sex = request.form.get("sex")
            occupation = request.form.get("occupation")
            bio = request.form.get("bio")

            session['user_profile'] = {
                'username': username,
                'age': age,
                'sex': sex,
                'bio': bio
            }

            cursor.execute("""
                UPDATE users SET username = %s, age = %s, sex = %s, occupation = %s, bio = %s
                WHERE id = %s
            """, (username, age, sex, occupation, bio, user_id))
            conn.commit()
            cursor.close()
            conn.close()
            return redirect(url_for("home"))

        cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        return render_template("profile.html", user=user)

    @app.route('/journal', methods=['GET', 'POST'])
    @login_required()
    def journal():

        user_id = session['user_id']
        date_param = request.args.get('date') or request.form.get('date')
        if date_param:
            entry_date = datetime.strptime(date_param, "%Y-%m-%d").date()
        else:
            entry_date = date.today()

        prev_date = (entry_date - timedelta(days=1)).strftime("%Y-%m-%d")
        next_date = (entry_date + timedelta(days=1)).strftime("%Y-%m-%d")
        conn = get_db_connection()
        cursor = conn.cursor()

        if request.method == 'POST':
            journal_text = request.form.get('journalText', '').strip()
            cursor.execute('''
                INSERT INTO journals (user_id, entry_date, entry)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE entry = %s, updated_at = CURRENT_TIMESTAMP
            ''', (user_id, entry_date, journal_text, journal_text))
            conn.commit()
            conn.close()
            return redirect(url_for('journal', date=entry_date.strftime("%Y-%m-%d"), saved='true'))

        cursor.execute('SELECT entry, mood FROM journals WHERE user_id = %s AND entry_date = %s', (user_id, entry_date))
        row = cursor.fetchone()

        journal_text = row['entry'] if row and 'entry' in row else ''
        mood = row['mood'] if row and 'mood' in row else None
        conn.close()

        show_saved_popup = request.args.get('saved') == 'true'
        return render_template('journal_entry.html', journal_text=journal_text, mood=mood,
                               today=entry_date.strftime("%B %d, %Y"),
                               date_param=entry_date.strftime("%Y-%m-%d"),
                               show_saved_popup=show_saved_popup,
                               prev_date=prev_date,
                               next_date=next_date)


    @app.route('/delete_journal', methods=['POST'])
    @login_required()
    def delete_journal():
        date = request.args.get('date')
        user_id = session.get('user_id')

        if user_id and date:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM journals WHERE user_id = %s AND entry_date = %s", (user_id, date))
            conn.commit()
            conn.close()
            return '', 200

        return '', 400

    @app.route('/journal_calendar')
    @login_required()
    def journal_calendar():

        user_id = session['user_id']
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT entry_date FROM journals WHERE user_id = %s', (user_id,))
        rows = cursor.fetchall()
        journal_dates = [row['entry_date'].strftime('%Y-%m-%d') for row in rows]
        conn.close()

        return render_template('journal_calendar.html', journal_dates=journal_dates)

    @app.route('/demo')
    def demo():
        return render_template("bot-chat.html", is_demo=True, is_casual=False, is_therapy=False, sessionName="Demo", sessionType="Demo",  user_settings=current_app.config.get("APP_CONFIG", {}))
    


    @app.route('/casual')
    @login_required()
    def casual_chat():
        return render_template("bot-chat.html", is_casual=True, is_demo=False, is_therapy=False, sessionName="Casual", sessionType="Casual Chat",user_settings=session.get('user_settings', {}))

    @app.route('/api/current_session')
    def current_session():
        if 'user_id' not in session:
            return jsonify({"error": "Unauthorized"}), 401

        conn = get_db_connection()
        with conn:
            cursor = conn.cursor()
            cursor.execute('SELECT session_name FROM sessions WHERE user_id = %s AND current = TRUE', (session['user_id'],))
            row = cursor.fetchone()
        return jsonify({"session_name": row['session_name']} if row else {"session_name": None})
    

    @login_required()
    @app.route('/api/session_types')
    def session_types():

        conn = get_db_connection()
        with conn:
            cursor = conn.cursor()
            cursor.execute('SELECT persona FROM session_types ORDER BY persona')
            types = [row['persona'] for row in cursor.fetchall()]
        return jsonify(types)
    
    @app.route('/api/new_session', methods=['POST'])
    @login_required()
    def new_session():

        data = request.get_json()
        session_name = data.get('session_name')
        persona = data.get('persona')

        if not session_name or not persona:
            return jsonify({"error": "Missing required fields"}), 400

        conn = get_db_connection()
        with conn:
            cursor = conn.cursor()
            # Mark existing sessions as not current
            cursor.execute('UPDATE sessions SET current = FALSE WHERE user_id = %s', (session['user_id'],))
            # Create new session
            cursor.execute('''
                INSERT INTO sessions (user_id, session_name, persona, current)
                VALUES (%s, %s, %s, TRUE)
            ''', (session['user_id'], session_name, persona))
            conn.commit()

        return jsonify({"status": "created", "session_name": session_name})


    @app.route('/api/user_settings', methods=['POST'])
    @login_required()
    def user_settings():

        user_id = session['user_id']
        data = request.get_json()

        conn = get_db_connection()
        cursor = conn.cursor()

        for key, value in data.items():
            cursor.execute('''
                INSERT INTO user_settings (user_id, setting_key , setting_value )
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE `setting_value` = %s
            ''', (user_id, key, str(value), str(value)))

        conn.commit()
        conn.close()

        # Update in-session overrides
        updated_settings = session.get('user_settings', {})
        updated_settings.update({k: str(v) for k, v in data.items()})
        session['user_settings'] = updated_settings


        dumpConfig()

        return jsonify({'status': 'ok'})
    
    @app.route("/set_country", methods=["POST"])
    def set_country():
        data = request.get_json()
        if data and "country" in data:
            session['country_code'] = data['country']
            session['hotline'] = lookup_hotline(data['country'])
            return {"status": "ok"}, 200
        return {"error": "invalid"}, 400


def login_required():
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if 'user_id' not in session:
                if request.path.startswith('/api/'):
                    return jsonify({'error': 'unauthorized'}), 401
                else:
                    return redirect(url_for('signin'))
            return f(*args, **kwargs)
        return wrapped
    return decorator


def user_is_in_crisis(text):
    crisis_keywords = [
        "kill myself", "suicidal", "end it all", "can't go on",
        "want to die", "hurt myself", "ending my life", "give up"
    ]
    return any(keyword in text.lower() for keyword in crisis_keywords)

def lookup_hotline(country_code):
    return HOTLINES.get(country_code.upper(), "N/A")