#!/bin/bash

exec > /var/log/user-data.log 2>&1

# 1. System update
apt-get update -y
apt-get upgrade -y

# 2. Install dependencies
apt-get install -y docker.io docker-compose git curl nginx nodejs npm

# 3. Enable Docker
systemctl enable docker
systemctl start docker

# 4. Install PM2
npm install -g pm2

# 5. Install Ollama and run model
curl -fsSL https://ollama.com/install.sh | sh
sleep 10
ollama run mistral &

# 6. Clone your repo
git clone https://github.com/charley68/pocketfreud.git /opt/pocketfreud

# 7. Set up backend (Node.js server)
cd /opt/pocketfreud/server
npm install
pm2 start server.js --name pocketfreud-api

# 8. Build React frontend
cd /opt/pocketfreud/client

# Ensure correct homepage in package.json before build (just to be safe)
sed -i '/"name":/a \ \ "homepage": "/chat",' package.json

npm install
CI=false npm run build

# 9. Deploy landing page to /
cp /opt/pocketfreud/index.html /var/www/html/index.html
cp /opt/pocketfreud/logo.png /var/www/html/logo.png
cp /opt/pocketfreud/background.jpg /var/www/html/background.jpg

# 10. Deploy React build to /chat
mkdir -p /var/www/html/chat
cp -r build/* /var/www/html/chat/

# 11. Nginx config
cat <<EOF > /etc/nginx/sites-available/default
server {
    listen 80 default_server;
    listen [::]:80 default_server;

    root /var/www/html;
    index index.html;
    server_name _;

    # Proxy for API
    location /api/ {
       proxy_pass http://localhost:3000/;
       proxy_http_version 1.1;
       proxy_set_header Upgrade \$http_upgrade;
       proxy_set_header Connection "upgrade";
       proxy_set_header Host \$host;
       proxy_cache_bypass \$http_upgrade;
    }

    # Static React app in /chat
    location /chat/ {
        root /var/www/html;
        try_files \$uri /chat/index.html;
    }

    # Root landing page
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

