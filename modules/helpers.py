import re
import datetime
import requests
from flask import session
from datetime import datetime
import os
from modules.db import load_prompts_from_db
from flask import session, current_app

EMAIL_REGEX = re.compile(r"[^@]+@[^@]+\.[^@]+")
PROMPTS = load_prompts_from_db()

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

# utils/chat_helpers.py



def build_profile_intro(profile):
    intro = f"My name is {profile['username']}."
    if profile.get('age'):
        intro += f" I am {profile['age']} years old."
    if profile.get('sex'):
        intro += f" I am {profile['sex'].lower()}."
    if profile.get('bio'):
        intro += f" A bit about me: {profile['bio']}"
    return intro

def build_conv_history(messages, persona):
    history = [{"role": "system", "content": PROMPTS.get(persona)}]

    profile = session.get("user_profile")
    if profile:
        history.append({"role": "system", "content": build_profile_intro(profile)})

    history.extend(messages)
    return history

def detect_crisis_response(user_input):
    crisis_keywords = [
        "kill myself", "kill somebody", "suicidal", "end it all", "can't go on",
        "want to die", "hurt myself", "ending my life", "self harm", "overdose"
    ]
    if any(keyword in user_input.lower() for keyword in crisis_keywords):
        hotline = session.get("hotline", "a local support number")
        return (
            f"I'm concerned about your safety. You are not alone. "
            f"If you're in crisis, please call your local support line: {hotline}"
        )
    return None



def call_llm_api(model, messages, temperature=0.7):

    if model.startswith("claude"):
        pass
        # use Anthropic SDK
    else:
        try:
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": messages,
                    "temperature": temperature
                }
            )
            result = response.json()

            # Basic error guard
            if "choices" not in result or not result["choices"]:
                raise ValueError("Invalid OpenAI response")

            message = result["choices"][0]["message"]["content"]
            usage = result.get("usage", {})
            return message, usage

        except Exception as e:
            raise RuntimeError(f"LLM API call failed: {e}")
