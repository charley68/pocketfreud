
output "instance_url" {
  value = "http://${aws_eip.persistent_ip.public_ip}"
}

output "rds_endpoint" {
  description = "The endpoint of the RDS instance"
  value = aws_db_instance.freud.endpoint
}

output "rds_port" {
  description = "The port the RDS instance is listening on"
      value = aws_db_instance.freud.port
}