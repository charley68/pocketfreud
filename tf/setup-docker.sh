#!/bin/bash

# Log all output to a file
exec > /var/log/user-data.log 2>&1

# 1. Update system
apt-get update -y
apt-get upgrade -y

# 2. Install dependencies
apt-get install -y python3 python3-venv python3-pip git curl nginx

# 3. Install Ollama
curl -fsSL https://ollama.com/install.sh | sh
sleep 10
systemctl enable ollama
systemctl start ollama

# 4. Clone your repo
git clone https://github.com/charley68/pocketfreud.git /opt/pocketfreud

# 5. Setup Python virtual environment and install dependencies
cd /opt/pocketfreud/server
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# 6. Start Flask app with Gunicorn
gunicorn --workers 1 --bind 0.0.0.0:5000 app:app &

# 7. Configure Nginx
cat <<EOF > /etc/nginx/sites-available/default
server {
    listen 80 default_server;
    listen [::]:80 default_server;

    server_name _;

    location / {
        root /opt/pocketfreud/server/static;
        index index.html;
        try_files \$uri /index.html;
    }

    location /chat {
        root /opt/pocketfreud/server/static;
        index chat.html;
        try_files \$uri /chat.html;
    }

    location /api/ {
        proxy_pass http://localhost:5000/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_cache_bypass \$http_upgrade;
    }

    error_page 404 /index.html;
}
EOF

# 8. Restart Nginx
systemctl restart nginx

