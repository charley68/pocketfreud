
resource "aws_instance" "app_server" {

  ami           = data.aws_ami.amazon_linux.id
  #instance_type = "t3.medium"
  instance_type = "t3.small"


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
    apt-get install -y python3 python3-pip python3-venv nginx git curl

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

    # Start Gunicorn (and keep it alive)
    nohup gunicorn --workers 1 --bind 0.0.0.0:5000 app:app > /var/log/gunicorn.log 2>&1 &

    # Setup Nginx
    cat <<NGINXCONF >/etc/nginx/sites-available/default
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
    NGINXCONF

    sudo chown -R ubuntu:ubuntu /opt/pocketfreud
    systemctl restart nginx
    echo "=== PocketFreud Setup Complete ==="
EOF

  tags = {
    Name = "pocketfreud-app-server"
  }
}

# Fetch latest Amazon Linux 2 AMI for Free Tier
data "aws_ami" "amazon_linux" {
  most_recent = true

  owners      = ["099720109477"] # Canonical (Ubuntu)

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}


resource "aws_eip" "my_elastic_ip" {
  instance = aws_instance.app_server
  vpc      = true
}