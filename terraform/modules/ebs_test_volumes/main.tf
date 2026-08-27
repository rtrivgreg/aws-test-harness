# Minimal EBS pair + tiny instance.
# No default-VPC assumption: pick an explicit subnet or the first available one.

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
  name        = "cfg-ebs-${var.test_run_id}"
  description = "Harness EBS test instance – no inbound"
  vpc_id      = data.aws_subnet.chosen.vpc_id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(var.tags, {
    Name        = "cfg-ebs-${var.test_run_id}"
    test-run-id = var.test_run_id
  })
}

resource "aws_instance" "harness" {
  ami                         = data.aws_ami.al2023.id
  instance_type               = "t3.nano"
  subnet_id                   = data.aws_subnet.chosen.id
  vpc_security_group_ids      = [aws_security_group.harness.id]
  associate_public_ip_address = false

  tags = merge(var.tags, {
    Name        = "cfg-ebs-${var.test_run_id}"
    test-run-id = var.test_run_id
  })
}

resource "aws_ebs_volume" "unencrypted" {
  availability_zone = aws_instance.harness.availability_zone
  size              = var.volume_size_gb
  type              = "gp3"
  encrypted         = false

  tags = merge(var.tags, {
    Name             = "cfg-ebs-unenc-${var.test_run_id}"
    test-run-id      = var.test_run_id
    harness-expected = "NON_COMPLIANT"
  })
}

resource "aws_ebs_volume" "encrypted" {
  availability_zone = aws_instance.harness.availability_zone
  size              = var.volume_size_gb
  type              = "gp3"
  encrypted         = true

  tags = merge(var.tags, {
    Name             = "cfg-ebs-enc-${var.test_run_id}"
    test-run-id      = var.test_run_id
    harness-expected = "COMPLIANT"
  })
}

resource "aws_volume_attachment" "unencrypted" {
  device_name = "/dev/sdf"
  volume_id   = aws_ebs_volume.unencrypted.id
  instance_id = aws_instance.harness.id
}

resource "aws_volume_attachment" "encrypted" {
  device_name = "/dev/sdg"
  volume_id   = aws_ebs_volume.encrypted.id
  instance_id = aws_instance.harness.id
}
