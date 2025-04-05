#!/bin/bash

# Log all output
exec > /var/log/user-data.log 2>&1

# 1. Update system
apt-get update -y
apt-get upgrade -y

# 2. Install dependencies
apt-get install -y python3 python3-venv python3-pip git curl

# 3. Install Ollama
curl -fsSL https://ollama.com/install.sh | sh
sleep 10
ollama run mistral &

# 4. Clone your repo
git clone https://github.com/charley68/pocketfreud.git /opt/pocketfreud

# 5. Setup Python virtual environment
cd /opt/pocketfreud/server
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# 6. Start Flask app with PM2
pip install pm2-py
pm2 start venv/bin/python3 --name pocketfreud-api -- app.py

# 7. DONE!

