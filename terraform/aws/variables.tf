variable "resource-name-prefix"  {
  type = string
  description = "Prefix that will be added to the name of all AWS resources created"
  default = "tboyd"
}

variable "vpc-name" {
  type = string
  description = "Existing VPC Name where instances will be created"
  default = "tboyd-us-east-1-vpc"
}

variable "subnet-names" {
  type = list(string)
  description = "Existing subnet names where instances will be created.  Locust clients will cycle through the list."
  default = [ "tboyd-sn-b"]
}

variable "key-pair-name" {
  type = string
  description = "Existing AWS key pair to use for all instances created"
  default = "tboyd-redis-key-2022-11-08"
}

variable "private-key-location" {
  type = string
  description = "Private key location"
  default = "../../.ssh/mykey.pem"
}

variable "security-group-names" {
  type        = list(string)
  description = "Existing security groups to assign to all instances"
  default     = ["tboyd-security-group-1"]
}

variable "locust-master-instance-type" {
  type = string
  description = "AWS instance type for hosting locust master"
  default = "m5.large"
}

variable "locust-worker-instance-type" {
  type = string
  description = "AWS instance type for hosting locust workers"
  default = "c5.large"
}

variable "prom-grafana-instance-type" {
  type = string
  description = "AWS instance type for hosting prometheus and grafana"
  default = "m5.large"
}

variable "worker-instance-count" {
  type = number
  description = "Number of locust workers instances"
  default = 2
}

variable "route53-name" {
  type = string
  description = "Route 53 domain name"
  default = "redisdemo.com."
}