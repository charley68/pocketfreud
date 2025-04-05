
resource "aws_instance" "app_server" {

  ami           = data.aws_ami.amazon_linux.id
  instance_type = "t3.micro"


  subnet_id     = aws_subnet.public.id
  vpc_security_group_ids = [aws_security_group.web_sg.id]
  associate_public_ip_address = true
  key_name      = var.key_pair_name
  root_block_device {
    volume_size = 30             # <-- THIS ensures 30 GB disk size
    volume_type = "gp2"          # General Purpose SSD
  }

  user_data = file("setup.sh")

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

output "ami_id" {
  value = data.aws_ami.amazon_linux.id
}

