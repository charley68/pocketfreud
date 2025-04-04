#!/bin/bash

# Log output for troubleshooting
exec > /var/log/user-data.log 2>&1

# 1. Update system
apt-get update -y
apt-get upgrade -y

# 2. Install system dependencies
apt-get install -y docker.io docker-compose git curl nginx npm python3-pip python3-venv

# 3. Enable Docker
systemctl enable docker
systemctl start docker

# 4. Install Node.js v18+
npm install -g n
n 18
export PATH="/usr/local/bin:$PATH"
hash -r

# 5. Install PM2 globally (for Flask app later if needed)
npm install -g pm2

# 6. Install Ollama
curl -fsSL https://ollama.com/install.sh | sh
sleep 10
ollama run mistral &

# 7. Clone your repo
git clone https://github.com/charley68/pocketfreud.git /opt/pocketfreud

# 8. Setup Flask backend
cd /opt/pocketfreud/server
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
deactivate

# 9. Start Flask backend with PM2
pm2 start "venv/bin/python3 app.py" --name pocketfreud-api

# 10. Build React frontend
cd /opt/pocketfreud/client
npm install
npm run build

# 11. Deploy landing page
cp /opt/pocketfreud/index.html /var/www/html/index.html
cp /opt/pocketfreud/logo.png /var/www/html/logo.png
cp /opt/pocketfreud/background.jpg /var/www/html/background.jpg

# 12. Deploy React chat frontend
mkdir -p /opt/pocketfreud/server/static/chat
cp -r build/* /opt/pocketfreud/server/static/chat/

# 13. Nginx config (simple proxy)
cat <<EOF > /etc/nginx/sites-available/default
server {
    listen 80 default_server;
    listen [::]:80 default_server;

    root /var/www/html;
    index index.html;
    server_name _;

    location /api/ {
        proxy_pass http://localhost:5000/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_cache_bypass \$http_upgrade;
    }

    location / {
        try_files \$uri /index.html;
    }

    error_page 404 /index.html;
}
EOF

# 14. Restart Nginx
systemctl restart nginx

