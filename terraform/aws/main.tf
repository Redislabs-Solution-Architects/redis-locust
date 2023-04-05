terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 4.38"
    }
  }
  required_version = ">= 1.2.0"
}

provider "aws" {
  region  = "us-east-1"
  default_tags {
    tags = {
      owner         = "thomas.boyd"
      skip_deletion = "yes"
      reap_date = "2099-12-31"
    }
  }
}

data "aws_ami" "ubuntu-2004" {
  most_recent      = true
  owners           = ["amazon"]

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-focal-20.04-amd64-server-*"]
  }

  filter {
    name   = "root-device-type"
    values = ["ebs"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

data "aws_ami" "ubuntu-1804" {
  most_recent      = true
  owners           = ["amazon"]

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-bionic-18.04-amd64-server-*"]
  }

  filter {
    name   = "root-device-type"
    values = ["ebs"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

data aws_key_pair "key-pair" {
  key_name = var.key-pair-name
}

data "aws_vpc" "vpc" {
  filter {
    name = "tag:Name"
    values = [var.vpc-name]
  }
}

data aws_subnets "subnets" {
  filter {
    name   = "tag:Name"
    values = var.subnet-names
  }
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.vpc.id]
  }
}

data "aws_security_groups" "security-groups" {
  filter {
    name   = "tag:Name"
    values = var.security-group-names
  }
}

data "aws_route53_zone" "selected" {
  name         = var.route53-name
  private_zone = false
}

resource "aws_instance" "locust-master" {
  ami           = "${data.aws_ami.ubuntu-2004.id}"
  instance_type = var.locust-master-instance-type
  key_name = var.key-pair-name
  subnet_id = data.aws_subnets.subnets.ids[0]
  vpc_security_group_ids = data.aws_security_groups.security-groups.ids
  user_data_replace_on_change = true
  user_data = "${file("locust-install.sh")}"

  root_block_device {
    volume_size = 100
  }

  provisioner "file" {
    source      = "/Users/thomasboyd/re-license-files/poc-license-current.txt"
    destination = "/tmp/poc-license-current.txt"
  }

  provisioner "remote-exec" {
    inline = [
      "cloud-init status --wait > /tmp/cloud-init-wait.out"]
  }

  connection {
    type     = "ssh"
    user     = "ubuntu"
    private_key = "${file("/Users/thomasboyd/.ssh/tboyd-redis-key-2022-11-08.pem")}"
    host     = "${self.public_ip}"
  }

  tags = {
    Name = format("%s-locust-master", var.resource-name-prefix)
  }
}

resource "aws_instance" "locust-workers" {
  count = var.worker-instance-count
  ami           = "${data.aws_ami.ubuntu-2004.id}"
  instance_type = var.locust-worker-instance-type
  key_name = var.key-pair-name
  subnet_id = element(data.aws_subnets.subnets.ids, count.index)
  vpc_security_group_ids = data.aws_security_groups.security-groups.ids
  user_data_replace_on_change = true
  user_data = "${file("locust-install.sh")}"

  root_block_device {
    volume_size = 100
  }

  provisioner "remote-exec" {
    inline = [
      "cloud-init status --wait > /tmp/cloud-init-wait.out"]
  }

  connection {
    type     = "ssh"
    user     = "ubuntu"
    private_key = "${file("/Users/thomasboyd/.ssh/tboyd-redis-key-2022-11-08.pem")}"
    host     = "${self.public_ip}"
  }

  tags = {
    Name = format("%s-locust-worker-%03d", var.resource-name-prefix, count.index + 1)
  }
}

resource "aws_instance" "prom-grafana" {
  ami           = "${data.aws_ami.ubuntu-2004.id}"
  instance_type = var.prom-grafana-instance-type
  key_name = var.key-pair-name
  subnet_id = data.aws_subnets.subnets.ids[0]
  vpc_security_group_ids = data.aws_security_groups.security-groups.ids
  user_data_replace_on_change = true
  user_data = "${file("prom-grafana-install.sh")}"

  root_block_device {
    volume_size = 25
  }

  connection {
    type     = "ssh"
    user     = "ubuntu"
    private_key = "${file("/Users/thomasboyd/.ssh/tboyd-redis-key-2022-11-08.pem")}"
    host     = "${self.public_ip}"
  }

  provisioner "remote-exec" {
    inline = [
      "cloud-init status --wait > /tmp/cloud-init-wait.out"]
  }

  provisioner "file" {
    source      = "./grafana-dashboards/node-exporter-full-dashboard.json"
    destination = "/var/lib/grafana/dashboards/node-exporter-full-dashboard.json"
  }
  provisioner "file" {
    source      = "./grafana-dashboards/rec-database-dashboard.json"
    destination = "/var/lib/grafana/dashboards/rec-database-dashboard.json"
  }
  provisioner "file" {
    source      = "./grafana-dashboards/rec-node-dashboard.json"
    destination = "/var/lib/grafana/dashboards/rec-node-dashboard.json"
  }
  provisioner "file" {
    source      = "grafana-dashboards/rec-cluster-dashboard.json"
    destination = "/var/lib/grafana/dashboards/rec-cluster-dashboard.json"
  }
  provisioner "file" {
    source      = "grafana-dashboards/hpc-node-exporter-server-metrics-v2_rev3.json"
    destination = "/var/lib/grafana/dashboards/hpc-node-exporter-server-metrics-v2_rev3.json"
  }

  provisioner "remote-exec" {
    inline = [
      "sudo chown -R grafana /var/lib/grafana/dashboards"]
  }
  provisioner "remote-exec" {
    inline = [
      "sudo chgrp -R grafana /var/lib/grafana/dashboards"]
  }

  tags = {
    Name = format("%s-prom-grafana", var.resource-name-prefix)
  }
}

resource "aws_route53_record" "locust-master" {
  zone_id = data.aws_route53_zone.selected.zone_id
  name    = format("%s-locust-master.%s", var.resource-name-prefix, data.aws_route53_zone.selected.name)
  type    = "A"
  ttl     = "30"
  records = [aws_instance.locust-master.public_ip]
}

resource "aws_route53_record" "internal-locust-master" {
  zone_id = data.aws_route53_zone.selected.zone_id
  name    = format("intr-%s-locust-master.%s", var.resource-name-prefix, data.aws_route53_zone.selected.name)
  type    = "A"
  ttl     = "30"
  records = [aws_instance.locust-master.private_ip]
}

resource "aws_route53_record" "locust-workers" {
  count = length(aws_instance.locust-workers)
  zone_id = data.aws_route53_zone.selected.zone_id
  name    = format("%s-locust-worker-%03d.%s", var.resource-name-prefix, count.index +1, data.aws_route53_zone.selected.name)
  type    = "A"
  ttl     = "30"
  records = [aws_instance.locust-workers[count.index].public_ip]
}

resource "aws_route53_record" "internal-locust-workers" {
  count = length(aws_instance.locust-workers)
  zone_id = data.aws_route53_zone.selected.zone_id
  name    = format("intr-%s-locust-worker-%03d.%s", var.resource-name-prefix, count.index +1, data.aws_route53_zone.selected.name)
  type    = "A"
  ttl     = "30"
  records = [aws_instance.locust-workers[count.index].private_ip]
}

resource "aws_route53_record" "prom-grafana" {
  zone_id = data.aws_route53_zone.selected.zone_id
  name    = format("%s-prom-grafana.%s", var.resource-name-prefix, data.aws_route53_zone.selected.name)
  type    = "A"
  ttl     = "30"
  records = [aws_instance.prom-grafana.public_ip]
}

resource "aws_route53_record" "internal-prom-grafana" {
  zone_id = data.aws_route53_zone.selected.zone_id
  name    = format("intr-%s.%s", var.resource-name-prefix, data.aws_route53_zone.selected.name)
  type    = "A"
  ttl     = "30"
  records = [aws_instance.prom-grafana.private_ip]
}

output "prom-grafana-external-host-name" {
  value = aws_route53_record.prom-grafana.fqdn
}

output "prom-grafana-internal-host-names" {
  value = aws_route53_record.internal-prom-grafana.fqdn
}

output "locust-master-external-host-name" {
  value = aws_route53_record.locust-master.fqdn
}

output "locust-master-internal-host-names" {
  value = aws_route53_record.internal-locust-master.fqdn
}

output "locust-worker-external-host-names" {
  value = aws_route53_record.locust-workers[*].fqdn
}

output "locust-worker-internal-host-names" {
  value = aws_route53_record.internal-locust-workers[*].fqdn
}