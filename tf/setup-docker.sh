#!/bin/bash

exec > /var/log/user-data.log 2>&1

# 1. System update
apt-get update -y
apt-get upgrade -y

# 2. Install base dependencies
apt-get install -y docker.io docker-compose git curl nginx nodejs npm

# 3. Enable Docker on boot
systemctl enable docker
systemctl start docker

# 4. Install PM2 globally for Node
npm install -g pm2

# 5. Install Ollama
curl -fsSL https://ollama.com/install.sh | sh
sleep 10
ollama run mistral &

# 6. Clone your repo
git clone https://github.com/charley68/pocketfreud.git /opt/pocketfreud

# 7. Set up server (Node proxy)
cd /opt/pocketfreud/server
npm install
pm2 start server.js --name pocketfreud-api

# 8. Build React chat app
cd /opt/pocketfreud/client
npm install
npm run build

# 9. Deploy landing page to /
cp /opt/pocketfreud/index.html /var/www/html/index.html
cp /opt/pocketfreud/logo.png /var/www/html/logo.png
cp /opt/pocketfreud/background.jpg /var/www/html/background.jpg

# 10. Deploy React chat app to /chat
mkdir -p /var/www/html/chat
cp -r build/* /var/www/html/chat/

# 11. Fix Nginx config
cat <<EOF > /etc/nginx/sites-available/default


server {
    listen 80 default_server;
    listen [::]:80 default_server;

    root /var/www/html;
    index index.html;
    server_name _;

    location /api/ {
       proxy_pass http://localhost:3000/;
       proxy_http_version 1.1;
       proxy_set_header Upgrade $http_upgrade;
       proxy_set_header Connection upgrade;
       proxy_set_header Host $host;
       proxy_cache_bypass $http_upgrade;
    }


    location / {
        try_files $uri /index.html;
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
