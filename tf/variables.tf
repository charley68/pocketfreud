
variable "aws_region" {
  default = "eu-west-2"
}

variable "aws_azs" {
  type        = list(string)
  default = ["eu-west-2a", "eu-west-2b"]
}

variable "instance_type" {
  default = "t3.micro"
}

variable "key_pair_name" {
  default = "freud"
}

variable "openai_api_key" {
  description = "Your OpenAI API key"
  type        = string
  sensitive   = true
}

variable "catchpha_key" {
  description = "Your Google Catchpa Secret key"
  type        = string
  sensitive   = true
}


variable "db_username" {
  description = "user for rds"
  type        = string
  sensitive   = true
}


variable "db_password" {
  description = "password for rds"
  type        = string
  sensitive   = true
}

variable "db_name" {
  description = "DB Name for app"
  type        = string
}

variable "db_instance" {
  description = "DB Instance Size"
  type        = string
}