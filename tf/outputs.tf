
output "instance_url" {
  value = "http://${aws_eip.persistent_ip.public_ip}"
}

output "rds_endpoint" {
  description = "The endpoint of the RDS instance"
  value = aws_db_instance.freud.address
}