import os
import requests
import traceback
from datetime import datetime, date, timedelta
from functools import wraps
from flask import (
    render_template, request, jsonify, redirect,
    url_for, session, flash, current_app
)


from werkzeug.security import generate_password_hash, check_password_hash


from modules.db import (
    get_db_connection,
    save_message_for_user,
    load_user_settings,
    get_last_summary,
    get_last_summary_checkpoint,
    get_messages_after,
    save_summary,
    dumpConfig,
    get_journals_by_days
)

from modules.helpers import (
    inject_base_url,
    inject_env,
    is_valid_email,
    pick_initial_greeting,
    get_setting,
    call_llm_api,
    build_conv_history,
    detect_crisis_response,
    generate_incremental_summary,
    extract_top_themes,
    generate_monthly_summary,
    send_verification_email,
    generate_email_token
)



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
            if not session.get('username'):
                session.clear()  # wipe corrupt session
                return redirect(url_for('home'))
            return render_template('home.html', username=session['username'])
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


    @app.route('/signin', methods=['GET', 'POST'])
    def signin():
        if request.method == 'POST':
            email = request.form['email'].strip().lower()
            password = request.form['password']

            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT id, username, age, sex, bio, password, verified FROM users WHERE email = %s', (email,))
            profile = cursor.fetchone()
            cursor.close()

            if not profile:
                flash("No account found with that email.")
                return redirect(url_for('signin'))
        
            if not profile['verified']:
                flash(f"Please verify your email before signing in. " f"<a href='{url_for('resend_verification', email=email)}'>Resend verification email</a>.")
                return redirect(url_for('signin'))
        
            if  check_password_hash(profile['password'], password):
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


    @app.route('/resend_verification')
    def resend_verification():
        email = request.args.get('email', '').strip().lower()
        if not email:
            flash("Missing email address.")
            return redirect(url_for('signin'))

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, verified FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()

        if not user:
            flash("No account found with that email.")
            return redirect(url_for('signin'))

        if user['verified']:
            flash("Your email is already verified.")
            return redirect(url_for('signin'))

        # Generate new token and update DB
        token = generate_email_token()
        cursor.execute("UPDATE users SET email_token = %s WHERE id = %s", (token, user['id']))
        conn.commit()
        cursor.close()

        send_verification_email(email, user['username'], token)
        flash("A new verification email has been sent.")
        return redirect(url_for('signin'))



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
            SELECT role, message FROM conversations WHERE user_id = %s AND session = %s ORDER BY timestamp ASC LIMIT 20
        ''',  (session['user_id'], sessionName))
        messages = cursor.fetchall()
        conn.close()

        return render_template('bot-chat.html',  is_therapy=True, is_casual = False, messages=messages, username=session.get('username'), sessionName=sessionName, sessionType=persona, user_settings=session.get('user_settings', {}))


    @app.route('/api/chat', methods=['POST'])
    @login_required()
    def chat_write():

        data = request.get_json(force=True)
        messages = data.get('messages', [])
        session_name = data.get('session_name')
        persona = data.get('session_type')
        model = session.get('user_settings', {}).get('model')

        user_id = session["user_id"]
        user_input = messages[-1]['content']
        responses = []

        try:
            # === Detect and respond to crisis if needed ===
            crisis_msg = detect_crisis_response(user_input)
            if crisis_msg:
                #save_message_for_user(user_id, 'assistant', crisis_msg, session_name)
                responses.append(crisis_msg)

            # === Build conversation history ===
            summary = get_last_summary(user_id, session_name)
            last_checkpoint = get_last_summary_checkpoint(user_id, session_name)
            recent_msgs = get_messages_after(user_id, session_name, last_checkpoint)

            conv_history = []

            if summary:
                conv_history.append({"role": "system", "content": f"Summary so far: {summary}"})
                conv_history += recent_msgs
                print("[SUMMARY] Using summary in system prompt")
            else:
                conv_history += build_conv_history(messages[:-1], persona)

            # Append current user message
            conv_history.append({"role": "user", "content": user_input})

            # === Call OpenAI ===
            ai_msg, usage = call_llm_api(model, conv_history)

            # === Token tracking ===
            total_tokens = usage.get("total_tokens", 0)
            mmYY = datetime.now().strftime("%m%y")
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

            # === Save messages to DB ===
            save_message_for_user(user_id, 'user', user_input, session_name)
            save_message_for_user(user_id, 'assistant', ai_msg, session_name)

            # === Trigger summarisation if needed ===
            SUMMARY_TRIGGER = session.get('user_settings', {}).get('summary_trigger', 10)

            if len(recent_msgs) >= SUMMARY_TRIGGER:
                updated_summary = generate_incremental_summary(summary, recent_msgs)
                save_summary(user_id, session_name, updated_summary, last_checkpoint + len(recent_msgs))
                print(f"[SUMMARY] Generating summary after {len(recent_msgs)} messages")
                print(f"[SUMMARY] New summary: {updated_summary[:100]}...")

            # Return response to frontend
            responses.append(ai_msg)
            return jsonify({"responses": responses})

        except Exception as e:
            traceback.print_exc()
            return jsonify({"error": str(e)}), 500

 
    @app.route('/api/casual_chat', methods=['POST'])
    @login_required()
    def casual_chat_api():

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

    """
    @app.route('/api/demo_chat', methods=['POST'])
    def demo_chat():

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
    """

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
        session_name = data.get('restore')

        conn = get_db_connection()
        with conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE sessions SET current = 0 WHERE user_id = %s AND current = 1', (session['user_id'],))
            cursor.execute('UPDATE sessions SET current = 1 WHERE user_id = %s AND session_name  = %s', (session['user_id'], session_name))
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

        cursor.execute("""
            UPDATE summaries SET session = %s WHERE user_id = %s AND session = %s
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
        session_name = data.get('session_name')  # This might be None

        user_id = session['user_id']
        conn = get_db_connection()
        cur = conn.cursor()

        if session_name:
            cur.execute("""
                UPDATE conversations
                SET archive = 1, session = %s
                WHERE user_id = %s AND archive = 0
            """, (session_name, user_id))
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

    """@app.route('/demo')
    def demo():
        return render_template("bot-chat.html", is_demo=True, is_casual=False, is_therapy=False, sessionName="Demo", sessionType="Demo",  user_settings=current_app.config.get("APP_CONFIG", {}))
    """


    @app.route('/casual')
    @login_required()
    def casual_chat():
        return render_template("bot-chat.html", is_casual=True, is_therapy=False, sessionName="Casual", sessionType="Casual Chat",user_settings=session.get('user_settings', {}))

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



    @app.route('/api/delete_session', methods=['POST'])
    @login_required()
    def delete_session():

        data = request.get_json()
        session_name = data.get('session_name')

        if not session_name:
            return jsonify({"error": "Missing required fields"}), 400

        conn = get_db_connection()
        with conn:
            cursor = conn.cursor()
            # Mark existing sessions as not current
            cursor.execute('DELETE from sessions WHERE user_id = %s and session_name = %s', (session['user_id'],session_name))
            conn.commit()

        return jsonify({"status": "deleted", "session_name": session_name})






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
    

    @app.route('/insights')
    def insights():
        user_id = session.get('user_id')
        days = int(request.args.get('days', 30))

        journals = get_journals_by_days(user_id, days)
        mood_data = [(j['entry_date'], j['mood']) for j in journals if j['mood']]
        top_themes = extract_top_themes(journals)
        summary = generate_monthly_summary(journals)

        return render_template('insights.html', moods=mood_data, themes=top_themes, summary=summary, selected_days=days)

    @app.route('/api/insights_summary')
    def api_insights_summary():
        user_id = session.get('user_id')
        days = int(request.args.get('days', 30))

        journals = get_journals_by_days(user_id, days)
        summary = generate_monthly_summary(journals)
        themes = extract_top_themes(journals)

        return jsonify({
            'summary': summary,
            'themes': themes
        })


    @app.route('/api/mood_data')
    def api_mood_data():
        user_id = session.get('user_id')
        days = int(request.args.get('days', 30))

        journals = get_journals_by_days(user_id, days)
        moods = [(j['entry_date'], j['mood']) for j in journals if j['mood']]

        return jsonify(moods)



    @app.route('/signup_with_plan', methods=['GET', 'POST'])
    def signup_with_plan():

        plan = request.args.get('plan')
        print(f"PLAN SELECTED: {plan}")
        if request.method == 'GET':
            # User came from /subscribe
            if plan not in ['basic', 'professional', 'premium']:
                flash(f"Invalid plan {plan} selected.")
                return redirect(url_for('show_subscription_options'))
            return render_template('signup_with_plan.html', selected_plan=plan)



        # POST method - handle form submission
        plan = request.form.get('plan')  # From hidden input field

        name = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')

        conn = get_db_connection()
        cursor = conn.cursor()


        # Check if email already exists
        cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
        if cursor.fetchone():
            flash("Email already registered.")
            return redirect(url_for('signup_with_plan', plan=plan))

        # Create user
        hashed_pw = generate_password_hash(password)
        token = generate_email_token()
        cursor.execute(
            "INSERT INTO users (username, email, password, email_token) VALUES (%s, %s, %s, %s)",
            (name, email, hashed_pw, token)
        )
        user_id = cursor.lastrowid

        # Create subscription
        billing_cycle = None
        if plan != 'basic':
            billing_cycle = 'monthly'  # or ask for this later in profile/settings

        cursor.execute(
            "INSERT INTO subscriptions (user_id, plan_type, billing_cycle) VALUES (%s, %s, %s)",
            (user_id, plan, billing_cycle)
        )

        conn.commit()
        conn.close()

        print(f"Send email with verification token {token}")
        send_verification_email(email, name, token)
        
        return render_template('signup_success.html', username=name)
    


    @app.route('/subscribe')
    def show_subscription_options():
        return render_template('subscription.html', change_mode=False)
    

    @app.route('/change_subscription')
    def change_subscription():
        if 'user_id' not in session:
            flash("Please log in to change your subscription.")
            return redirect(url_for('signin'))
        return render_template(
            'subscription.html',
            change_mode=True,
            current_plan=session['user_subscription']['plan_type'],
            available_plans=['basic', 'professional', 'premium'])



    @app.route('/update_subscription/<plan>')
    def update_subscription(plan):
        if plan not in ['basic', 'professional', 'premium']:
            flash("Invalid plan selected.")
            return redirect(url_for('change_subscription'))

        user_id = session.get('user_id')

        conn = get_db_connection()
        cursor = conn.cursor()

        # Update the subscription
        cursor.execute("""
            UPDATE subscriptions
            SET plan_type = %s, updated_at = NOW()
            WHERE user_id = %s
        """, (plan, user_id))
        conn.commit()
        conn.close()

        # Update session
        session['user_subscription']['plan_type'] = plan

        flash(f"Subscription updated to {plan.upper()}")
        return redirect(url_for('home'))

    @app.route('/verify_email')
    def verify_email():
        token = request.args.get('token')
        if not token:
            flash("Invalid verification link.")
            return redirect(url_for('signin'))

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
            conn.close()

            flash("Email confirmed. You can now log in.")
            return redirect(url_for('signin'))
        else:
            flash("Verification failed or already completed.")
            return redirect(url_for('signin'))



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