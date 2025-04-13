
output "instance_url" {
  value = "http://${aws_eip.persistent_ip.public_ip}"
}