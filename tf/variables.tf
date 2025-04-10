
variable "aws_region" {
  default = "eu-west-2"
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
