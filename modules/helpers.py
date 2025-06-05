import re
import datetime
import requests
from flask import session
from flask import url_for
from flask_mail import Mail, Message
from datetime import datetime
from openai import OpenAI
import os
import secrets

from modules.extensions import mail
from modules.db import load_prompts_from_db
from flask import session, current_app
from flask import render_template


EMAIL_REGEX = re.compile(r"[^@]+@[^@]+\.[^@]+")
PROMPTS = load_prompts_from_db()
client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

def is_valid_email(email):
    return bool(EMAIL_REGEX.match(email))

def inject_base_url():
    return dict(BASE_URL=current_app.config.get('BASE_URL', ''))

def inject_env():
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
        # Claude logic here (future)
        raise NotImplementedError("Claude support not implemented yet.")

    elif model.startswith("ollama:"):
        # Local Ollama support (optional)
        raise NotImplementedError("Ollama support not implemented yet.")

    elif model.startswith("gpt-"):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=2000
            )
            content = response.choices[0].message.content
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            }
            return content, usage
        except Exception as e:
            raise RuntimeError(f"OpenAI SDK call failed: {e}")

    else:
        raise ValueError(f"Unsupported model: {model}")



def generate_incremental_summary(previous_summary, new_messages):
    prompt = []

    if previous_summary:
        prompt.append({
            "role": "system",
            "content": f"The previous summary was: \"{previous_summary}\". Update or extend it based on the following new messages."
        })
    else:
        prompt.append({
            "role": "system",
            "content": "Summarise the following conversation in 1–2 sentences, focusing on the user's emotional themes."
        })

    prompt += new_messages
    prompt.append({
        "role": "system",
        "content": "Provide a concise updated summary."
    })

    message, _ = call_llm_api(get_setting("model"), prompt)
    return message


def generate_monthly_summary(journals):
    entries = [j['entry'] for j in journals if j['entry']]
    if not entries:
        return "No journal entries found for this period."

    text_block = "\n".join(entries[-10:])
    messages = [
        {"role": "system", "content": "You are a gentle, empathetic mental health assistant who summarizes journals with care and insight."},
        {"role": "user", "content": f"Summarize the following journal entries and offer a gentle reflection:\n\n{text_block}"}
    ]

    content, usage = call_llm_api("gpt-3.5-turbo", messages)
    return content  # ✅ content is already the final string you want




def extract_top_themes(journals):
    keywords = {"stress": 0, "work": 0, "family": 0, "anxiety": 0, "tired": 0}
    for j in journals:
        entry = (j.get('entry') or '').lower()
        for k in keywords:
            if k in entry:
                keywords[k] += 1
    return [k.capitalize() for k, v in sorted(keywords.items(), key=lambda x: -x[1]) if v > 0]


def generate_email_token():
    return secrets.token_urlsafe(32)

def send_verification_email(user_email, username, token):
    confirm_url = url_for('verify_email', token=token, _external=True)
    subject = "Welcome to PocketFreud – Confirm Your Email"
    
    html = render_template("emails/welcome_email.html", username=username, confirm_url=confirm_url)
    
    msg = Message(subject, recipients=[user_email], html=html)
    mail.send(msg)