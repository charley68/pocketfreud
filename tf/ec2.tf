
resource "aws_instance" "app_server" {

  ami           = data.aws_ami.ubuntu.id
  #instance_type = "t3.medium"
  instance_type = "t3.micro"


  subnet_id     = aws_subnet.public1.id
  vpc_security_group_ids = [aws_security_group.web_sg.id]
  associate_public_ip_address = true
  key_name      = var.key_pair_name
  #root_block_device {
  # volume_size = 30             # <-- THIS ensures 30 GB disk size
  #   volume_type = "gp2"          # General Purpose SSD
  #}

user_data = <<-EOT
#!/bin/bash
exec > /var/log/user-data.log 2>&1

DOMAIN_NAME="pocketfreud.com"
EMAIL="sclane68@yahoo.co.uk"

# Update system and install dependencies
apt-get update -y
apt-get upgrade -y
apt-get install -y python3 python3-pip python3-venv nginx git curl software-properties-common


# Install Certbot
add-apt-repository ppa:certbot/certbot -y
apt-get update -y
apt-get install -y certbot python3-certbot-nginx

# --- Clone your app ---
cd /opt
rm -rf pocketfreud
git clone https://github.com/charley68/pocketfreud.git

# --- Set up Python virtual environment and install requirements ---
cd /opt/pocketfreud
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# --- Environment variables ---
export FLASK_SECRET_KEY=$(python3 -c 'import secrets; print(secrets.token_hex(32))')
export USE_OLLAMA=false

export OPENAI_API_KEY="${var.openai_api_key}"
export DB_USER="${var.db_username}"  
export DB_PASS="${var.db_password}"  
export DB_NAME="${var.db_name}"  
export DB_HOST="${aws_db_instance.freud.endpoint}" 



# --- Create systemd service for Gunicorn ---
cat <<SERVICE > /etc/systemd/system/pocketfreud.service
[Unit]
Description=Gunicorn to serve PocketFreud Flask App
After=network.target

[Service]
User=ubuntu
Group=www-data
WorkingDirectory=/opt/pocketfreud
Environment="PATH=/opt/pocketfreud/venv/bin"
Environment="FLASK_SECRET_KEY=$FLASK_SECRET_KEY"
Environment="USE_OLLAMA=$USE_OLLAMA"
Environment="OPENAI_API_KEY=$OPENAI_API_KEY"
ExecStart=/opt/pocketfreud/venv/bin/gunicorn --workers 2 --bind 127.0.0.1:5000 app:app

[Install]
WantedBy=multi-user.target
SERVICE

systemctl daemon-reload
systemctl enable pocketfreud
chown -R ubuntu:www-data /opt/pocketfreud
chmod -R 775 /opt/pocketfreud
systemctl start pocketfreud

# --- Stage 1: Temporary HTTP-only config for Certbot ---
cat <<EOF > /etc/nginx/sites-available/default
server {
    listen 80;
    server_name $DOMAIN_NAME www.$DOMAIN_NAME;

    location / {
        root /var/www/html;
        index index.html;
    }
}
EOF

systemctl restart nginx
sleep 5

# --- Stage 2: Request SSL certificate from Let's Encrypt ---
certbot --nginx --non-interactive --agree-tos --email $EMAIL -d $DOMAIN_NAME -d www.$DOMAIN_NAME

# --- Stage 3: Final secure Nginx config ---
cat <<EOF > /etc/nginx/sites-available/default
server {
    listen 80;
    server_name $DOMAIN_NAME www.$DOMAIN_NAME;
    return 301 https://\$host\$request_uri;
}

server {
    listen 443 ssl;
    server_name $DOMAIN_NAME www.$DOMAIN_NAME;

    ssl_certificate /etc/letsencrypt/live/$DOMAIN_NAME/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/$DOMAIN_NAME/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

    location / {
        proxy_pass http://127.0.0.1:5000/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_cache_bypass \$http_upgrade;
    }

    location /test {
        rewrite ^/test$ / break;
        proxy_pass http://127.0.0.1:5001;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;

        # Remove `/test` from the path before passing to Flask
        rewrite ^/test(/.*)$ $1 break;
    }

}
EOF

systemctl reload nginx
echo "✅ Setup complete with HTTPS!"
EOT



  tags = {
    Name = "pocketfreud-app-server"
  }
}

data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"] # Canonical

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }
}


resource "aws_eip" "persistent_ip" {
  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_eip_association" "app_server_ip" {
  instance_id   = aws_instance.app_server.id
  allocation_id = aws_eip.persistent_ip.id
}