
#!/bin/bash

# Log output
exec > /var/log/setup-docker.log 2>&1
set -e

echo "==> Updating system and installing dependencies..."
apt-get update -y
apt-get upgrade -y
apt-get install -y docker.io docker-compose git curl nginx nodejs npm

echo "==> Enabling Docker to start on boot..."
systemctl start docker
systemctl enable docker

echo "==> Installing PM2 globally..."
npm install -g pm2

echo "==> Installing Ollama..."
curl -fsSL https://ollama.com/install.sh | sh
sleep 10
ollama run mistral &

echo "==> Cloning PocketFreud repository..."
git clone https://github.com/charley68/pocketfreud.git /opt/pocketfreud

echo "==> Setting up backend..."
cd /opt/pocketfreud/server
npm install
pm2 start server.js --name pocketfreud-api

echo "==> Building frontend..."
cd /opt/pocketfreud/client
npm install
npm run build

echo "==> Deploying landing page..."
cp public/index.html /var/www/html/index.html
cp public/logo.png /var/www/html/logo.png
cp public/background.jpg /var/www/html/background.jpg

echo "==> Deploying React app to /chat..."
mkdir -p /var/www/html/chat
cp -r build/* /var/www/html/chat/

echo "==> Restarting Nginx..."
systemctl restart nginx

echo "==> Setup complete!"
