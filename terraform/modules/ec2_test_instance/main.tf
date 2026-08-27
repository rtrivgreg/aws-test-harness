data "aws_subnets" "available" {
  filter {
    name   = "state"
    values = ["available"]
  }
}

locals {
  subnet_id = var.subnet_id != "" ? var.subnet_id : try(data.aws_subnets.available.ids[0], "")
}

data "aws_subnet" "chosen" {
  id = local.subnet_id
}

data "aws_ami" "al2023" {
  most_recent = true
  owners      = ["amazon"]
  filter {
    name   = "name"
    values = ["al2023-ami-*-x86_64"]
  }
  filter {
    name   = "state"
    values = ["available"]
  }
}

resource "aws_security_group" "harness" {
  name        = "cfg-ec2-${var.test_run_id}"
  description = "Harness EC2 test instance - no inbound"
  vpc_id      = data.aws_subnet.chosen.vpc_id
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  tags = merge(var.tags, {
    Name        = "cfg-ec2-${var.test_run_id}"
    test-run-id = var.test_run_id
  })
}

resource "aws_instance" "harness" {
  ami                         = data.aws_ami.al2023.id
  instance_type               = "t3.nano"
  subnet_id                   = data.aws_subnet.chosen.id
  vpc_security_group_ids      = [aws_security_group.harness.id]
  associate_public_ip_address = false

  metadata_options {
    http_endpoint = "enabled"
    http_tokens   = "optional"
  }

  tags = merge(var.tags, {
    Name        = "cfg-ec2-${var.test_run_id}"
    test-run-id = var.test_run_id
  })
}
