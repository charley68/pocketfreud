
output "instance_public_ip" {
  value = aws_instance.app_server.public_ip
}

output "instance_url" {
  value = "http://${aws_instance.app_server.public_ip}"
}
