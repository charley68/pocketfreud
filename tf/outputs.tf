

output "elastic_ip" {
  value = aws_eip.my_elastic_ip.public_ip
}

output "instance_url" {
  value = "http://${aws_instance.app_server.public_ip}"
}
