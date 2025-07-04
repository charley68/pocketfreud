import os
import re
import secrets
import threading
import traceback
from datetime import datetime, date, timedelta
from functools import wraps
from flask import (
    request, session, redirect, url_for, render_template,
    flash, jsonify, current_app, send_from_directory
)
from werkzeug.security import generate_password_hash, check_password_hash
from flask_mail import Message

from modules.extensions import mail

from modules.db import (
    create_user,
    get_user_profile,
    verify_user_email,
    check_user_exists,
    get_session_types,
    get_user_by_email_for_verification,
    update_verification_token,
    create_subscription,
    update_subscription,
    save_user_settings,
    get_chat_history,
    get_chat_thread,
    create_new_session,
    save_chat_message,
    get_user_info,
    update_user_profile,
    save_user_reset_token,
    update_user_password,
    get_current_session,
    get_session_messages,
    get_last_summary,
    get_last_summary_checkpoint,
    get_messages_after,
    track_token_usage,
    save_summary,
    restore_chat,
    rename_session,
    update_session_persona,
    get_monthly_tokens,
    archive_session,
    delete_current_chat,
    save_journal_entry,
    get_journal_entry,
    delete_journal_entry,
    get_journal_dates,
    get_session_types,
    delete_session,
    get_journals_by_days,
    load_user_settings,
    get_stats,
    get_next_session_name_api,
    increment_session_counter
)

from modules.helpers import (
    inject_base_url,
    inject_env,
    is_valid_email,
    send_verification_email,
    generate_email_token,
    send_reset_email,
    check_captcha,
    call_llm_api,
    build_conv_history,
    detect_crisis_response,
    generate_incremental_summary,
    generate_monthly_summary,
    extract_top_themes
)



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

    @app.route('/terms')
    def terms():
        return render_template("terms.html")    

    @app.route('/logout')
    def logout():
        session.clear()
        flash('You have been logged out.')
        return redirect(url_for('home'))

    @app.route('/privacy')
    def privacy():
        return render_template('privacy.html')

    @app.route('/faq')
    def faq():
        return render_template('faq.html')

    @app.route('/debug')
    def debug():
        try:
            stats_data = get_stats()
            return jsonify({
                'status': 'success',
                'data': {
                    'conversations': stats_data['conversations'],
                    'users': stats_data['users']
                }
            })
        except Exception as e:
            return jsonify({
                'status': 'error',
                'message': str(e)
            }), 500


    @app.route('/signin', methods=['GET', 'POST'])
    def signin():
        if request.method == 'POST':
            email = request.form['email'].strip().lower()
            password = request.form['password']
            
            profile = get_user_profile(email)
            
            if not profile:
                flash("No account found with that email.")
                return redirect(url_for('signin'))
            
            if not profile['verified']:
                flash(f"Please verify your email before signing in. " f"<a href='{url_for('resend_verification', email=email)}'>Resend verification email</a>.")
                return redirect(url_for('signin'))
            
            if check_password_hash(profile['password'], password):
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

        user = get_user_by_email_for_verification(email)

        if not user:
            flash("No account found with that email.")
            return redirect(url_for('signin'))

        if user['verified']:
            flash("Your email is already verified.")
            return redirect(url_for('signin'))

        # Generate new token and update DB
        token = generate_email_token()
        update_verification_token(user['id'], token)

        send_verification_email(email, user['username'], token)
        flash(f"A new verification email has been sent to {email}. Please check your inbox.")
        return redirect(url_for('signin'))

    @app.route('/forgot_password', methods=['GET', 'POST'])
    def forgot_password():
        if request.method == 'POST':
            email = request.form['email'].strip().lower()
            
            # Generate and save token
            token = secrets.token_urlsafe(32)
            save_user_reset_token(email, token)
            
            # Build reset link
            reset_link = url_for('reset_password', token=token, _external=True, _scheme='https')
            
            # Send the email
            send_reset_email(email, reset_link)
            
            flash("If your email is registered, a reset link has been sent.")
            return redirect(url_for('signin'))

        return render_template("forgot_password.html")

    @app.route('/reset_password', methods=['GET', 'POST'])
    def reset_password():
        token = request.args.get('token')

        if request.method == 'POST':
            new_password = request.form['password']
            hashed = generate_password_hash(new_password)
            
            if update_user_password(token, hashed):
                flash("Your password has been updated. Please sign in.")
                return redirect(url_for('signin'))
            else:
                flash("Invalid or expired reset token.")
                return redirect(url_for('forgot_password'))

        return render_template("reset_password.html", token=token)



    # -------------------- CHAT --------------------
    @app.route('/therapy')
    @login_required()
    def therapy():
        current_session = get_current_session(session['user_id'])
        sessionName = current_session['session_name'] if current_session else None
        persona = current_session['persona'] if current_session else None
        
        messages = get_session_messages(session['user_id'], sessionName) if sessionName else []

        return render_template('bot-chat.html',  
                             is_therapy=True, 
                             is_casual=False, 
                             messages=messages, 
                             username=session.get('username'), 
                             sessionName=sessionName, 
                             sessionType=persona, 
                             user_settings=session.get('user_settings', {}))


    @app.route('/api/chat', methods=['POST'])
    @login_required()
    def chat_write():

        data = request.get_json(force=True)
        messages = data.get('messages', [])
        session_name = data.get('session_name')
        persona = data.get('session_type')
        model = session.get('user_settings', {}).get('model')

        # Validate required fields
        if not messages or not session_name:
            return jsonify({'error': 'Missing required fields'}), 400

        user_id = session["user_id"]
        user_input = messages[-1]['content']
        responses = []

        try:
            # Detect and respond to crisis if needed
            crisis_msg = detect_crisis_response(user_input)
            if crisis_msg:
                responses.append(crisis_msg)

            # Build conversation history
            summary = get_last_summary(user_id, session_name)
            last_checkpoint = get_last_summary_checkpoint(user_id, session_name)
            recent_msgs = get_messages_after(user_id, session_name, last_checkpoint)

            conv_history = []

            if summary:
                conv_history.append({"role": "system", "content": f"Summary so far: {summary}"})
                conv_history += recent_msgs
            else:
                conv_history += build_conv_history(messages[:-1], persona)

            # Append current user message
            conv_history.append({"role": "user", "content": user_input})

            # Call LLM API
            ai_msg, usage = call_llm_api(model, conv_history)

            # Track token usage
            total_tokens = usage.get("total_tokens", 0)
            mmYY = datetime.now().strftime("%m%y")
            track_token_usage(user_id, total_tokens, mmYY)

            # Save messages to DB
            save_chat_message(user_id, 'user', user_input, session_name)
            save_chat_message(user_id, 'assistant', ai_msg, session_name)

            # Handle summarization
            SUMMARY_TRIGGER = session.get('user_settings', {}).get('summary_trigger', 10)
            if len(recent_msgs) >= SUMMARY_TRIGGER:
                updated_summary = generate_incremental_summary(summary, recent_msgs)
                save_summary(user_id, session_name, updated_summary, last_checkpoint + len(recent_msgs))

            # Return response
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
        user_id = session['user_id']
        session_name = "Casual"

        conv_history = build_conv_history(messages[:-1], persona)
        user_input = messages[-1]['content']
        conv_history.append({"role": "user", "content": user_input})

        responses = []

        try:
            crisis_msg = detect_crisis_response(user_input)
            if crisis_msg:
                responses.append(crisis_msg)

            ai_msg, usage = call_llm_api(model, conv_history)
            
            # Save messages
            save_chat_message(user_id, 'user', user_input, session_name)
            save_chat_message(user_id, 'assistant', ai_msg, session_name)
            
            # Track token usage
            total_tokens = usage.get("total_tokens", 0)
            mmYY = datetime.now().strftime("%m%y")
            track_token_usage(user_id, total_tokens, mmYY)
            
            responses.append(ai_msg)
            return jsonify({"responses": responses})

        except Exception as e:
            traceback.print_exc()
            return jsonify({"error": str(e)}), 500


    @app.route('/settings', methods=['GET', 'POST'])
    @login_required()
    def settings():
        if 'user_id' not in session:
            return redirect(url_for('signin'))
        
        if request.method == 'POST':
            # Update settings
            user_id = session['user_id']
            settings = {
                'typing_delay': request.form.get('typing_delay'),
                'voice': request.form.get('voice'),
                'msg_retention': request.form.get('msg_retention'),
                'model': request.form.get('model'),
                'theme': request.form.get('theme'),
                'summary_count': request.form.get('summary_count')
            }
            save_user_settings(user_id, settings)

            # Update in-session overrides
            updated_settings = session.get('user_settings', {})
            updated_settings.update({k: str(v) for k, v in settings.items() if v is not None})
            session['user_settings'] = updated_settings
            
            flash("Settings updated successfully!")
            return redirect(url_for('settings'))
        
        # GET request - show settings page
        settings = session.get('user_settings', {})
        if not settings:
            settings = {
                'typing_delay': 1000,
                'voice': 'en-US',
                'msg_retention': 50,
                'model': 'gpt-3.5-turbo',
                'theme': 'default',
                'summary_count': 100
            }
        return render_template('settings.html', 
                             username=session.get('username'),
                             settings=settings)


    @app.route('/api/config', methods=['GET'])
    def get_config():
        return jsonify(app.config["APP_CONFIG"])
    

    @app.route('/api/chat_history')
    @login_required()
    def chat_history():
        rows = get_chat_history(session['user_id'])
        return jsonify(rows)

    @app.route('/api/restore_chat', methods=['POST'])
    @login_required()
    def restore_chat_route():
        data = request.get_json()
        session_name = data.get('restore')
        
        if not session_name:
            return jsonify({'error': 'Missing session name'}), 400
        
        try:
            success = restore_chat(session['user_id'], session_name)
            if success:
                return '', 204
            else:
                return jsonify({'error': 'Session not found'}), 404
        except Exception as e:
            app.logger.error(f"Error restoring chat session: {str(e)}")
            return jsonify({'error': 'Failed to restore session'}), 500


    @app.route("/api/rename_session", methods=["POST"])
    @login_required()
    def rename_session_route():
        data = request.get_json()
        old_name = data.get("old_name")
        new_name = data.get("new_name")
        user_id = session["user_id"]

        if not old_name or not new_name:
            return jsonify({"error": "Missing fields"}), 400

        rename_session(user_id, old_name, new_name)
        return jsonify({"status": "renamed"})
    
    
    @app.route('/change_persona', methods=['POST'])
    @login_required()
    def change_persona():
        data = request.get_json()
        current_session_name = data.get('current_session_name')
        new_persona = data.get('persona')

        update_session_persona(session['user_id'], current_session_name, new_persona)
        return jsonify({'success': True})

    

    @app.route("/api/token_usage", methods=["GET"])
    @login_required()
    def get_token_usage():
        user_id = session["user_id"]
        mmYY = datetime.now().strftime("%m%y")
        
        print(f"Fetching tokens for user {user_id}, month {mmYY}")
        token_count = get_monthly_tokens(user_id, mmYY)
        print("Token count:", token_count)
        
        return jsonify({"month_tokens": token_count})




    @app.route('/api/new_chat', methods=['POST'])
    @login_required()
    def new_chat():
        data = request.get_json()
        session_name = data.get('session_name')  # This might be None
        user_id = session['user_id']
        
        archive_session(user_id, session_name)
        return jsonify({'status': 'archived and ready'})


    @app.route('/api/delete_chat', methods=['POST'])
    @login_required()
    def delete_chat():
        delete_current_chat(session['user_id'])
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
        save_journal_entry(user_id, today, None, mood)
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

            update_user_profile(user_id, username, age, sex, occupation, bio)
            return redirect(url_for("home"))

        user = get_user_info(user_id)

        return render_template("profile.html", user=user)

    @app.route('/journal', methods=['GET', 'POST'])
    @login_required()
    def journal():
        user_id = session['user_id']
        date_param = request.args.get('date') or request.form.get('date')
        if date_param:
            try:
                entry_date = datetime.strptime(date_param, "%Y-%m-%d").date()
            except ValueError:
                flash("Invalid date format. Please use YYYY-MM-DD format.")
                return redirect(url_for('journal')), 400
        else:
            entry_date = date.today()

        prev_date = (entry_date - timedelta(days=1)).strftime("%Y-%m-%d")
        next_date = (entry_date + timedelta(days=1)).strftime("%Y-%m-%d")

        if request.method == 'POST':
            journal_text = request.form.get('journalText', '').strip()
            save_journal_entry(user_id, entry_date, journal_text)
            return redirect(url_for('journal', date=entry_date.strftime("%Y-%m-%d"), saved='true'))

        entry = get_journal_entry(user_id, entry_date)
        journal_text = entry['entry'] if entry and 'entry' in entry else ''
        mood = entry['mood'] if entry and 'mood' in entry else None

        show_saved_popup = request.args.get('saved') == 'true'
        return render_template('journal_entry.html', 
                             journal_text=journal_text, 
                             mood=mood,
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
            delete_journal_entry(user_id, date)
            return '', 200

        return '', 400

    @app.route('/journal_calendar')
    @login_required()
    def journal_calendar():
        journal_dates = get_journal_dates(session['user_id'])
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
        
        current = get_current_session(session['user_id'])
        return jsonify({"session_name": current['session_name']} if current else {"session_name": None})
    

    @login_required()
    @app.route('/api/session_types')
    def session_types():
        types = get_session_types()
        return jsonify(types)
    
    @app.route('/api/new_session', methods=['POST'])
    def new_session():
        if 'user_id' not in session:
            return jsonify({'error': 'Not logged in'}), 401
            
        data = request.get_json()
        session_name = data.get('session_name')
        persona = data.get('persona')
        
        if not session_name or not persona:
            return jsonify({'error': 'Missing required fields'}), 400
            
        # Validate persona type
        valid_personas = get_session_types()
        if persona not in valid_personas:
            return jsonify({'error': 'Invalid persona type'}), 400
            
        try:
            create_new_session(session['user_id'], session_name, persona)
            return jsonify({'status': 'success'})
        except Exception as e:
            app.logger.error(f"Error creating session: {str(e)}")
            return jsonify({'error': 'Failed to create session'}), 500

    @app.route('/api/chat_thread/<session_name>')
    @login_required()
    def get_chat_thread_route(session_name):
        if not session_name:
            return jsonify({"error": "Missing session name"}), 400
            
        try:
            thread = get_chat_thread(session['user_id'], session_name)
            thread_data = [{"role": msg['role'], "content": msg['message']} for msg in thread]
            return jsonify(thread_data)
        except Exception as e:
            app.logger.error(f"Error getting chat thread: {str(e)}")
            return jsonify({"error": "Failed to get chat thread"}), 500


    


    @app.route('/api/delete_session', methods=['POST'])
    @login_required()
    def delete_session_route():
        data = request.get_json()
        session_name = data.get('session_name')

        if not session_name:
            return jsonify({"error": "Missing required fields"}), 400

        delete_session(session['user_id'], session_name)
        return jsonify({"status": "deleted", "session_name": session_name})






    @app.route('/api/user_settings', methods=['GET', 'POST'])
    @login_required()
    def user_settings():
        user_id = session['user_id']

        if request.method == 'GET':
            settings = session.get('user_settings', {})
            if not settings:
                # Load default settings
                settings = {
                    'typing_delay': 1000,
                    'voice': 'en-US',
                    'msg_retention': 50,
                    'model': 'gpt-3.5-turbo',
                    'theme': 'default',
                    'summary_count': 100
                }
            return jsonify(settings)

        # POST method
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        save_user_settings(user_id, data)

        # Update in-session overrides 
        updated_settings = session.get('user_settings', {})
        updated_settings.update({k: str(v) for k, v in data.items()})
        session['user_settings'] = updated_settings

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
        days = int(request.args.get('days', 7))

        journals = get_journals_by_days(user_id, days)
        mood_data = [(j['entry_date'], j['mood']) for j in journals if j['mood']]
        top_themes = extract_top_themes(journals)
        summary = generate_monthly_summary(journals)

        return render_template('insights.html', moods=mood_data, themes=top_themes, summary=summary, selected_days=days)

    @app.route('/api/insights_summary')
    def api_insights_summary():
        user_id = session.get('user_id')
        days = int(request.args.get('days', 7))

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
        days = int(request.args.get('days', 7))

        journals = get_journals_by_days(user_id, days)
        moods = [(j['entry_date'], j['mood']) for j in journals if j['mood']]

        return jsonify(moods)



    @app.route('/signup_with_plan', methods=['GET', 'POST'])
    def signup_with_plan():
        if request.method == 'GET':
            plan = request.args.get('plan')
            if plan not in ['basic', 'professional', 'premium']:
                flash(f"Invalid plan {plan} selected.")
                return redirect(url_for('show_subscription_options'))
            return render_template('signup_with_plan.html', selected_plan=plan)

        # POST method - handle form submission
        try:
            name = request.form.get('username')
            email = request.form.get('email').lower()
            password = request.form.get('password')
            plan = request.form.get('plan')
            
            if not all([name, email, password, plan]):
                flash('All fields are required.')
                return redirect(url_for('signup_with_plan', plan=plan))

            if not is_valid_email(email):
                flash('Invalid email format.')
                return redirect(url_for('signup_with_plan', plan=plan))

            # Check if email already exists
            if check_user_exists(email):
                flash("Email already registered.")
                return redirect(url_for('signup_with_plan', plan=plan))
                
            # Now validate CAPTCHA
            captcha_result = check_captcha(request)
            if captcha_result:  # If not None, it's an error string
                return redirect(url_for('signup_with_plan', plan=plan))

            # Create user
            hashed_pw = generate_password_hash(password)
            token = generate_email_token()
            
            try:
                # Use db.py functions to create user and subscription with proper transaction handling
                user_id = create_user(name, email, hashed_pw, token)
                if not user_id:
                    raise Exception("Failed to create user - no ID returned")
                    
                billing_cycle = 'monthly' if plan != 'basic' else None
                subscription_id = create_subscription(user_id, plan, billing_cycle)
                if not subscription_id:
                    raise Exception("Failed to create subscription")
                    
            except Exception as e:
                app.logger.error(f"Error in signup process: {str(e)}")
                flash("Error creating account. Please try again.")
                return redirect(url_for('signup_with_plan', plan=plan))

            print(f"Send email with verification token {token}")
            send_verification_email(email, name, token)
            
            return render_template('signup_success.html', username=name)
            
        except Exception as e:
            app.logger.error(f"Error in signup: {str(e)}")
            flash("An error occurred. Please try again.")
            return redirect(url_for('signup_with_plan', plan=plan))
    


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
    @app.route('/update_user_subscription/<plan>')  # Adding alias for compatibility
    def update_user_subscription(plan):
        if 'user_id' not in session:
            return redirect(url_for('signin'))
            
        if plan not in ['basic', 'professional', 'premium']:
            flash("Invalid plan selected.")
            return redirect(url_for('change_subscription')), 400

        try:
            user_id = session['user_id']
            update_subscription(user_id, plan)
            
            # Update session
            session['user_subscription'] = {
                'plan_type': plan,
                'is_active': True
            }
            
            flash(f"Successfully updated to {plan.upper()} plan!")
            return redirect(url_for('home'))
        except Exception as e:
            app.logger.error(f"Error updating subscription: {str(e)}")
            flash("Error updating subscription. Please try again.")
            return redirect(url_for('change_subscription')), 500

    @app.before_request
    def require_login():
        """Require login for protected routes"""
        protected_paths = ['/profile', '/settings', '/journal', '/api/chat', '/insights']
        public_paths = ['/', '/signin', '/signup_with_plan', '/verify_email', '/resend_verification',
                       '/forgot_password', '/reset_password', '/about', '/terms', '/privacy', '/faq', 
                       '/contact', '/debug']
        
        # Check if path is protected or not in public paths
        needs_auth = (request.path in protected_paths or 
                     (request.path not in public_paths and 
                      not any(request.path.startswith(p) for p in ['/static/', '/api/public/'])))
        
        if needs_auth and 'user_id' not in session and request.method != 'OPTIONS':
            if request.path.startswith('/api/'):
                return jsonify({'error': 'unauthorized'}), 401
            return redirect(url_for('signin'))

    @app.route('/verify_email')
    def verify_email():
        token = request.args.get('token')
        if not token:
            flash("Invalid verification link.")
            return redirect(url_for('signin'))

        if verify_user_email(token):
            flash("Email confirmed! You can now log in.")
            return redirect(url_for('signin'))
        else:
            flash("Verification failed or already completed.")
            return redirect(url_for('signin'))

    def send_async_email(app, msg):
        with app.app_context():
            mail.send(msg)


    @app.route('/contact', methods=['GET', 'POST'])
    def contact():
        if request.method == 'POST':
            name = request.form.get('name')
            email = request.form.get('email')
            message = request.form.get('message')

            if not is_valid_email(email):
                return jsonify({'status': 'error', 'message': 'Invalid email format'}), 400

            check_captcha(request)

            subject = f"New contact form message from {name}"
            body = f"""
            You received a new message via the PocketFreud contact form:

            Name: {name}
            Email: {email}

            Message:
            {message}
            """

            msg = Message(subject,
                        recipients=['admin@pocketfreud.com'],
                        body=body)
            msg.reply_to = email

            # 🔁 Send email in background thread
            threading.Thread(target=send_async_email, args=(current_app._get_current_object(), msg)).start()

            return jsonify({'status': 'success'})
        
        return render_template('contact.html')

    # Session management API routes
    @app.route('/api/get-next-session-name', methods=['GET'])
    @login_required()
    def api_get_next_session_name():
        user_id = session.get('user_id')  # Ensure user_id is retrieved from the session
        if not user_id:
            return jsonify({"error": "Unauthorized"}), 401
        return get_next_session_name_api(user_id)

    @app.route('/api/increment-session-counter', methods=['POST'])
    @login_required()
    def api_increment_session_counter():
        user_id = session.get('user_id')  # Ensure user_id is retrieved from the session
        if not user_id:
            return jsonify({"error": "Unauthorized"}), 401
        increment_session_counter(user_id)
        return jsonify({"success": True})
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

def lookup_hotline(country_code):
    return HOTLINES.get(country_code.upper(), "N/A")

# Crisis hotlines by country
HOTLINES = {
    "US": "988",
    "AU": "13 11 14",
    "CA": "1-833-456-4566",
    "UK": "116 123",
    "FR": "01 45 39 40 00",
    "DE": "0800 111 0 111",
    "JP": "03-5286-9090",
    "IN": "91-22-2754-6669"
}