#!/bin/bash

# Log everything
exec > /var/log/user-data.log 2>&1

# 1. Update system
apt-get update -y
apt-get upgrade -y

# 2. Install basic dependencies
apt-get install -y docker.io docker-compose git curl nginx python3-pip

# 3. Enable Docker
systemctl enable docker
systemctl start docker

# 4. Install Node version manager and Node 18 for building frontend (optional)
npm install -g n
n 18
export PATH="/usr/local/bin:$PATH"
hash -r

# 5. Install Ollama
curl -fsSL https://ollama.com/install.sh | sh
sleep 10
ollama run mistral &

# 6. Clone your Git repo
git clone https://github.com/charley68/pocketfreud.git /opt/pocketfreud

# 7. Set up Flask backend
cd /opt/pocketfreud/backend
pip3 install -r requirements.txt

# Start Flask backend with Gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app --daemon

# 8. Build React frontend (or use plain HTML/JS later if you prefer)
cd /opt/pocketfreud/client
npm install
npm run build

# 9. Deploy static landing page
cp /opt/pocketfreud/index.html /var/www/html/index.html
cp /opt/pocketfreud/logo.png /var/www/html/logo.png
cp /opt/pocketfreud/background.jpg /var/www/html/background.jpg

# 10. Deploy frontend app to /chat
mkdir -p /var/www/html/chat
cp -r build/* /var/www/html/chat/

# 11. Configure Nginx
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

    location /chat/ {
        root /var/www/html;
        index index.html;
        try_files $uri /chat/index.html;
    }

    location / {
        try_files \$uri /index.html;
    }

    location /static/ {
        expires 30d;
        add_header Cache-Control "public";
    }

    error_page 404 /index.html;
}
EOF

# 12. Restart Nginx
systemctl restart nginx

