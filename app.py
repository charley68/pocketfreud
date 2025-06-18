import os
import logging
import json
from flask import Flask, session, jsonify, request, redirect
from werkzeug.middleware.proxy_fix import ProxyFix
from modules.db import load_prompts_from_db, init_db
from modules.routes import register_routes
from modules.extensions import mail
from werkzeug.middleware.proxy_fix import ProxyFix



# Function to load properties file
def load_properties(filepath):
    properties = {}
    with open(filepath, "r") as file:
        for line in file:
            line = line.strip()
            if line and not line.startswith("#"):  # Ignore empty lines and comments
                key, value = line.split("=", 1)
                # Replace msg_retention with summary_count
                if key == "msg_retention":
                    key = "summary_count"
                properties[key.strip()] = value.strip()
    return properties

def is_testing():
    return os.environ.get('TEST_MODE') == '1' or os.environ.get('FLASK_ENV') == 'testing'

# ----------------- 1. INIT LOGGING & ENV -----------------
logging.basicConfig(level=logging.INFO)

env = os.getenv("ENV", "prod")
is_test = env == "test" or is_testing()

logging.info(f"Started Environment: {env}")

# ----------------- 2. CREATE FLASK APP -----------------
app = Flask(
    __name__,
    static_folder=os.path.join(os.path.dirname(__file__), 'static'),
    static_url_path="/test/static" if is_test else "/static"
)

app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# ----------------- 3. LOAD CONFIGURATION -----------------
app.config["APP_CONFIG"] = load_properties("config.properties")


# ----------------- 4. CONFIGURE APP -----------------
app_root = "/test" if is_test else "/"
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'fallback_secret_key')

app.config['PREFERRED_URL_SCHEME'] = 'https'

app.config.update(
    BASE_URL=app_root,
    APPLICATION_ROOT=app_root,
    SESSION_COOKIE_NAME="pocketfreud_test" if is_test else "pocketfreud_prod",
    TEMPLATES_AUTO_RELOAD=True  # remove in production
)

app.config.update(
    MAIL_SERVER='smtp.hostinger.com',
    MAIL_PORT=465,
    MAIL_USE_SSL=True,         # ✅ MUST be True for Port 465
    MAIL_USE_TLS=False,   
    MAIL_USERNAME='admin@pocketfreud.com',
    MAIL_PASSWORD='Freud2306!',
    MAIL_DEFAULT_SENDER='PocketFreud <admin@pocketfreud.com>',
    MAIL_DEBUG=True 
)

mail.init_app(app)

# ----------------- 5. LOG FILE PATHS -----------------
logging.info(f"[STATIC FOLDER] {app.static_folder}")
logging.info(f"[TEMPLATE FOLDER] {app.template_folder}")

# ----------------- 6. INIT DB + ROUTES -----------------
if not is_testing():
    init_db()

register_routes(app)
    
# ----------------- 8. DEV ENTRY -----------------
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5050)
