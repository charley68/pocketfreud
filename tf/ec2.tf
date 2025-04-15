
resource "aws_instance" "app_server" {

  ami           = data.aws_ami.ubuntu.id
  #instance_type = "t3.medium"
  instance_type = "t3.micro"


  subnet_id     = aws_subnet.public.id
  vpc_security_group_ids = [aws_security_group.web_sg.id]
  associate_public_ip_address = true
  key_name      = var.key_pair_name
  #root_block_device {
  # volume_size = 30             # <-- THIS ensures 30 GB disk size
  #   volume_type = "gp2"          # General Purpose SSD
  #}

user_data = <<-EOF
  #!/bin/bash
  exec > /var/log/user-data.log 2>&1

  apt-get update -y
  apt-get upgrade -y
  apt-get install -y python3 python3-pip python3-venv nginx git curl software-properties-common


  # === Install Certbot ===
  add-apt-repository ppa:certbot/certbot -y
  apt-get update -y
  apt-get install -y certbot python3-certbot-nginx

  # === Set domain (update to your real domain) ===
  DOMAIN_NAME="pocketfreud.com"



  cd /opt
  rm -rf pocketfreud
  git clone https://github.com/charley68/pocketfreud.git

  cd /opt/pocketfreud
  python3 -m venv venv
  source venv/bin/activate
  pip install --upgrade pip
  pip install -r requirements.txt

  # Environment variables
  export FLASK_SECRET_KEY=$(python3 -c 'import secrets; print(secrets.token_hex(32))')
  export USE_OLLAMA=false
  export OPENAI_API_KEY="${var.openai_api_key}"

  # --- Create systemd service for PocketFreud Gunicorn ---
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
  systemctl start pocketfreud

  # --- Setup Nginx ---
  cat <<NGINXCONF > /etc/nginx/sites-available/default
server {
    listen 80;
    server_name $DOMAIN_NAME;

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
  NGINXCONF

  sudo chown -R ubuntu:ubuntu /opt/pocketfreud
  systemctl restart nginx

  === Request SSL Certificate ===
  certbot --nginx --non-interactive --agree-tos --email sclane68@yahoo.co.uk -d $DOMAIN_NAME

  # === Optional: Auto renew via cron ===
  #echo "0 3 * * * root certbot renew --quiet && systemctl reload nginx" > /etc/cron.d/certbot-auto-renew

  echo "=== PocketFreud Setup Complete ==="
EOF


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