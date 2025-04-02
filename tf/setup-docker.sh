#!/bin/bash

# Log all output to user-data.log
exec > /var/log/user-data.log 2>&1

# Update and install dependencies
apt-get update -y
apt-get upgrade -y
apt-get install -y docker.io docker-compose git curl nginx nodejs npm

# Enable Docker and Nginx on boot
systemctl enable docker
systemctl enable nginx
systemctl start docker
systemctl start nginx

# Add ubuntu to docker group so we can run without sudo
usermod -aG docker ubuntu

# Install PM2 globally (for Node backend if needed)
npm install -g pm2

# Clone your GitHub repo (adjust if private or different)
cd /opt
git clone https://github.com/charley68/pocketfreud.git
cd pocketfreud

# Start Ollama container and run mistral
docker run -d --name ollama -p 11434:11434 ollama/ollama
sleep 10
docker exec ollama ollama run mistral &

# Backend setup
cd server
npm install
pm2 start server.js --name pocketfreud-api
cd ..

# Frontend build
cd client
npm install
npm run build

# Deploy frontend with Nginx
cp -r build/* /var/www/html/
systemctl restart nginx
