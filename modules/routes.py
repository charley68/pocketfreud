from flask import render_template, request, jsonify, redirect, url_for, session, flash
import datetime
import requests
import traceback
import os

from modules.db import get_db_connection, save_message_for_user
from modules.helpers import inject_base_url, inject_env, is_valid_email, pick_initial_greeting

def register_routes(app, PROMPTS):
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
                flash('Login successful!')
                return redirect(url_for('home'))
            else:
                flash('Invalid credentials.')
                return redirect(url_for('signin'))

        return render_template('signin.html')

    # -------------------- CHAT --------------------
    @app.route('/chat')
    def chat():
        if 'user_id' not in session:
            return redirect(url_for('signin'))

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT groupTitle FROM conversations WHERE user_id = %s AND archive = 0 ORDER BY timestamp DESC LIMIT 1
        ''', (session['user_id'],))
        row = cursor.fetchone()
        groupTitle = row['groupTitle'] if row else None

        cursor.execute('''
            SELECT sender, message FROM conversations WHERE user_id = %s AND archive = 0 ORDER BY timestamp ASC LIMIT 20
        ''', (session['user_id'],))
        messages = cursor.fetchall()
        conn.close()

        return render_template('chat.html', messages=messages, username=session.get('username'), groupTitle=groupTitle)

    @app.route('/api/chat', methods=['POST'])
    def chat_write():
        if 'user_id' not in session:
            return jsonify({'error': 'Unauthorized'}), 401

        data = request.get_json(force=True)
        messages = data.get('messages', [])
        group_title = data.get('groupTitle')

        conv_history = [{"role": "system", "content": PROMPTS.get("counsellor") or "You are PocketFreud..."}]

        profile = session.get('user_profile')
        if profile:
            intro = f"My name is {profile['username']}."
            if profile.get('age'):
                intro += f" I am {profile['age']} years old."
            if profile.get('sex'):
                intro += f" I am {profile['sex'].lower()}."
            if profile.get('bio'):
                intro += f" A bit about me: {profile['bio']}"
            conv_history.append({"role": "system", "content": intro})

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT sender, message FROM conversations WHERE user_id = %s AND archive = 0 ORDER BY timestamp ASC LIMIT 20
        ''', (session['user_id'],))
        past = cursor.fetchall()
        conn.close()

        for msg in past:
            conv_history.append({"role": "user" if msg["sender"] == "user" else "assistant", "content": msg["message"]})

        user_input = messages[-1]['content']
        conv_history.append({"role": "user", "content": user_input})

        try:
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}",
                    "Content-Type": "application/json",
                },
                json={"model": "gpt-3.5-turbo", "messages": conv_history}
            )
            result = response.json()
            ai_msg = result['choices'][0]['message']['content']

            save_message_for_user(session['user_id'], 'user', user_input, group_title)
            save_message_for_user(session['user_id'], 'bot', ai_msg, group_title)

            return jsonify({"response": ai_msg})
        except Exception as e:
            traceback.print_exc()
            return jsonify({"error": str(e)}), 500

    @app.route('/api/demo_chat', methods=['POST'])
    def demo_chat():
        data = request.json
        messages = data.get("messages", [])
        prompt = PROMPTS["demo"]

        full_prompt = [{"role": "system", "content": prompt}] + messages

        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}",
                "Content-Type": "application/json",
            },
            json={"model": "gpt-3.5-turbo", "messages": full_prompt, "temperature": 0.7}
        )

        reply = response.json()["choices"][0]["message"]["content"].strip()
        return jsonify({"response": reply})


    @app.route('/api/chat_history')
    def chat_history():
        if 'user_id' not in session:
            return jsonify([])

        conn = get_db_connection()
        with conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT groupTitle, MAX(timestamp) as latest FROM conversations
                WHERE user_id = %s AND archive = 1 GROUP BY groupTitle ORDER BY latest DESC
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
            cursor.execute('UPDATE conversations SET archive = 1 WHERE user_id = %s AND archive = 0', (session['user_id'],))
            cursor.execute('UPDATE conversations SET archive = 0 WHERE user_id = %s AND groupTitle = %s', (session['user_id'], restore_group))
            conn.commit()

        return '', 204

    @app.route('/api/unlabled_message_count')
    def unlabled_message_count():
        if 'user_id' not in session:
            return jsonify({"count": 0})

        conn = get_db_connection()
        with conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) as count FROM conversations WHERE user_id = %s AND groupTitle IS NULL', (session['user_id'],))
            row = cursor.fetchone()

        return jsonify({"count": row["count"]})

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
            cursor.execute('UPDATE conversations SET archive = 1, groupTitle = %s WHERE user_id = %s AND archive = 0', (group_title, user_id))
            conn.commit()

        return '', 204

    @app.route('/api/delete_chat', methods=['POST'])
    def delete_chat():
        if 'user_id' not in session:
            return jsonify({'error': 'Unauthorized'}), 401

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM conversations WHERE user_id = %s AND archive = 0', (session['user_id'],))
        conn.commit()
        conn.close()
        return jsonify({'status': 'deleted'})

    @app.route('/log_mood', methods=['POST'])
    def log_mood():
        if 'user_id' not in session:
            return 'Unauthorized', 401

        user_id = session['user_id']
        data = request.get_json()
        mood = data.get('mood')

        if not mood:
            return 'Invalid data', 400

        today = datetime.date.today()
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
    def journal():
        if 'user_id' not in session:
            return redirect(url_for('signin'))

        user_id = session['user_id']
        date_param = request.args.get('date') or request.form.get('date')
        if date_param:
            entry_date = datetime.datetime.strptime(date_param, "%Y-%m-%d").date()
        else:
            entry_date = datetime.date.today()

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
                               show_saved_popup=show_saved_popup)

    @app.route('/delete_journal', methods=['POST'])
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
    def journal_calendar():
        if 'user_id' not in session:
            return redirect(url_for('signin'))

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
        return render_template("demo.html")
