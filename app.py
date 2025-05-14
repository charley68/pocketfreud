import os
import logging
from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix

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

# ----------------- 3. CONFIGURE APP -----------------
app_root = "/test" if is_test else "/"
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'fallback_secret_key')

app.config.update(
    BASE_URL=app_root,
    APPLICATION_ROOT=app_root,
    SESSION_COOKIE_NAME="pocketfreud_test" if is_test else "pocketfreud_prod",
    TEMPLATES_AUTO_RELOAD=True  # remove in production
)

# ----------------- 4. LOG FILE PATHS -----------------
logging.info(f"[STATIC FOLDER] {app.static_folder}")
logging.info(f"[TEMPLATE FOLDER] {app.template_folder}")

# ----------------- 5. LOAD PROMPTS -----------------
from modules.helpers import load_prompts
PROMPTS = load_prompts("prompts")

# ----------------- 6. INIT DB + ROUTES -----------------
from modules.db import init_db
from modules.routes import register_routes

init_db()
register_routes(app, PROMPTS)

# ----------------- 7. DEV ENTRY -----------------
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5050)
