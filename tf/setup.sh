#!/bin/bash

# Log all output to a file
exec > /var/log/user-data.log 2>&1

echo "==== System Update ===="
apt-get update -y
apt-get upgrade -y

echo "==== Install Core Packages ===="
apt-get install -y python3 python3-venv python3-pip git curl nginx

echo "==== Install Ollama ===="
curl -fsSL https://ollama.com/install.sh | sh
sleep 10
systemctl enable ollama
systemctl start ollama

ollama pull mistral

echo "==== Clone Project Repo ===="
git clone https://github.com/charley68/pocketfreud.git /opt/pocketfreud

echo "==== Setup Python Virtual Environment ===="
cd /opt/pocketfreud/server
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo "==== Start Flask App with Gunicorn ===="
gunicorn --workers 1 --bind 0.0.0.0:5000 app:app &

echo "==== Prepare Nginx Static Files ===="
# Copy landing page and static files to /var/www/html
cp /opt/pocketfreud/server/static/* /var/www/html/

echo "==== Configure Nginx ===="
cat <<EOF > /etc/nginx/sites-available/default
server {
    listen 80 default_server;
    listen [::]:80 default_server;

    server_name _;

    root /var/www/html;
    index index.html;

    location / {
        try_files \$uri \$uri/ /index.html;
    }

    location /chat {
        try_files \$uri \$uri/ /chat.html;
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

echo "==== Restart Nginx ===="
systemctl restart nginx

echo "==== Setup Complete! ===="

