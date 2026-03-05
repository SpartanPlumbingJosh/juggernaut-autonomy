provider "aws" {
  region = "us-east-1"
}

resource "aws_db_instance" "revenue_db" {
  identifier             = "revenue-db"
  allocated_storage      = 100
  storage_type           = "gp2"
  engine                 = "postgres"
  engine_version         = "13.7"
  instance_class         = "db.t3.medium"
  name                   = "revenue_db"
  username               = "admin"
  password               = var.db_password
  parameter_group_name   = "default.postgres13"
  skip_final_snapshot    = true
  publicly_accessible    = false
  vpc_security_group_ids = [aws_security_group.db.id]
}

resource "aws_security_group" "db" {
  name_prefix = "revenue-db-"

  ingress {
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = ["10.0.0.0/16"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_ecs_cluster" "revenue_api" {
  name = "revenue-api-cluster"
}

resource "aws_ecs_service" "revenue_api" {
  name            = "revenue-api"
  cluster         = aws_ecs_cluster.revenue_api.id
  task_definition = aws_ecs_task_definition.revenue_api.arn
  desired_count   = 3

  load_balancer {
    target_group_arn = aws_lb_target_group.revenue_api.arn
    container_name   = "revenue-api"
    container_port   = 8000
  }
}

resource "aws_lb" "revenue_api" {
  name               = "revenue-api-lb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.lb.id]
  subnets            = var.public_subnets
}

resource "aws_lb_target_group" "revenue_api" {
  name     = "revenue-api-tg"
  port     = 8000
  protocol = "HTTP"
  vpc_id   = var.vpc_id
}

resource "aws_security_group" "lb" {
  name_prefix = "revenue-lb-"

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}
