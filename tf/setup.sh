#!/bin/bash

# Log output
exec > /var/log/user-data.log 2>&1

# Update system
apt-get update -y
apt-get upgrade -y

# Install dependencies
apt-get install -y python3 python3-pip python3-venv nginx git curl

# Clone your repo
cd /opt
rm -rf pocketfreud
git clone https://github.com/charley68/pocketfreud.git

# Set up Python app
cd /opt/pocketfreud
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Generate random secret key for Flask
export FLASK_SECRET_KEY=$(python3 -c 'import secrets; print(secrets.token_hex(32))')
export USE_OLLAMA=false
export OPENAI_API_KEY="your-openai-api-key-here"

# Start Flask App with Gunicorn
gunicorn --workers 1 --bind 0.0.0.0:5000 app:app &

# Configure Nginx
cat <<EOF > /etc/nginx/sites-available/default
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;

    location /static/ {
        root /opt/pocketfreud/;
    }

    location / {
        proxy_pass http://127.0.0.1:5000/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_cache_bypass \$http_upgrade;
    }
}
EOF

sudo chown -R ubuntu:ubuntu /opt/pocketfreud
sudo chown -R ubuntu:ubuntu /var/www/html

# Restart Nginx
systemctl restart nginx

echo "Setup Complete!"
