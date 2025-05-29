import os
import logging
import json
from flask import Flask, session, jsonify
from werkzeug.middleware.proxy_fix import ProxyFix
from modules.db import load_prompts_from_db, init_db, get_next_session_name_api, increment_session_counter
from modules.routes import register_routes

# Function to load properties file
def load_properties(filepath):
    properties = {}
    with open(filepath, "r") as file:
        for line in file:
            line = line.strip()
            if line and not line.startswith("#"):  # Ignore empty lines and comments
                key, value = line.split("=", 1)
                properties[key.strip()] = value.strip()
    return properties

# ----------------- 1. INIT LOGGING & ENV -----------------
logging.basicConfig(level=logging.INFO)

env = os.getenv("ENV", "prod")
is_test = env == "test"

# ----------------- 2. CREATE FLASK APP -----------------
app = Flask(
    __name__,
    static_folder=os.path.join(os.path.dirname(__file__), 'static'),
    static_url_path="/test/static" if is_test else "/static"
)

app.wsgi_app = ProxyFix(app.wsgi_app, x_prefix=1)

# ----------------- 3. LOAD CONFIGURATION -----------------
app.config["APP_CONFIG"] = load_properties("config.properties")


# ----------------- 4. CONFIGURE APP -----------------
app_root = "/test" if is_test else "/"
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'fallback_secret_key')

app.config.update(
    BASE_URL=app_root,
    APPLICATION_ROOT=app_root,
    SESSION_COOKIE_NAME="pocketfreud_test" if is_test else "pocketfreud_prod",
    TEMPLATES_AUTO_RELOAD=True  # remove in production
)

# ----------------- 5. LOG FILE PATHS -----------------
logging.info(f"[STATIC FOLDER] {app.static_folder}")
logging.info(f"[TEMPLATE FOLDER] {app.template_folder}")

# ----------------- 6. LOAD PROMPTS -----------------
init_db()

# ----------------- 7. INIT DB + ROUTES -----------------
register_routes(app)

@app.route('/api/get-next-session-name', methods=['GET'])
def api_get_next_session_name():
    user_id = session.get('user_id')  # Ensure user_id is retrieved from the session
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401
    return get_next_session_name_api(user_id)

@app.route('/api/increment-session-counter', methods=['POST'])
def api_increment_session_counter():
    user_id = session.get('user_id')  # Ensure user_id is retrieved from the session
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401
    increment_session_counter(user_id)
    return jsonify({"success": True})

# ----------------- 8. DEV ENTRY -----------------
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5050)
