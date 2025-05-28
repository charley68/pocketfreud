import re
import datetime
from flask import session, current_app

EMAIL_REGEX = re.compile(r"[^@]+@[^@]+\.[^@]+")

def is_valid_email(email):
    return bool(EMAIL_REGEX.match(email))

def inject_base_url():
    return dict(BASE_URL=current_app.config.get('BASE_URL', ''))

def inject_env():
    import os
    return dict(ENV=os.getenv("ENV", "prod"))

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

    import random
    return random.choice(greetings)


def get_setting(key, cast=str):
    # Check user override in session
    value = session.get("user_settings", {}).get(key)

    if value is None:
        # Fall back to global app config
        value = current_app.config["APP_CONFIG"].get(key)

    return cast(value) if value is not None else None
