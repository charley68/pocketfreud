resource "aws_db_instance" "freud" {
  allocated_storage    = 10
  db_name              = var.db_name
  identifier           = "freud-db"
  engine               = "mysql"
  engine_version       = "8.0"
  instance_class       = var.db_instance
  username             = var.db_username
  password             = var.db_password
  parameter_group_name = "default.mysql8.0"
  skip_final_snapshot  = true
  db_subnet_group_name = aws_db_subnet_group.freudDB.name
  multi_az            = false   # Change this for none dev.
  publicly_accessible = true
  vpc_security_group_ids = [aws_security_group.rds_sg.id]
  apply_immediately = true
  lifecycle {
    prevent_destroy = true
  }
}