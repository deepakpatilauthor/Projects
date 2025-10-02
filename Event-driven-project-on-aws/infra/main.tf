terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.60"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.4"
    }
  }
}

provider "aws" {
  region  = var.region
  profile = var.aws_profile
}

variable "project"     { type = string }
variable "env"         { type = string }
variable "region"      { type = string  default = "ap-south-1" }
variable "aws_profile" { type = string  default = "default" }

locals {
  raw_bucket       = "${var.project}-${var.env}-raw"
  processed_bucket = "${var.project}-${var.env}-processed"
  logs_bucket      = "${var.project}-${var.env}-logs"
}

# ---------------- S3 Buckets ----------------
resource "aws_s3_bucket" "raw"       { bucket = local.raw_bucket }
resource "aws_s3_bucket" "processed" { bucket = local.processed_bucket }
resource "aws_s3_bucket" "logs"      { bucket = local.logs_bucket }

resource "aws_s3_bucket_versioning" "raw" {
  bucket = aws_s3_bucket.raw.id
  versioning_configuration { status = "Enabled" }
}
resource "aws_s3_bucket_versioning" "processed" {
  bucket = aws_s3_bucket.processed.id
  versioning_configuration { status = "Enabled" }
}
resource "aws_s3_bucket_notification" "raw_events" {
  bucket      = aws_s3_bucket.raw.id
  eventbridge = true
}

# ---------------- DynamoDB ----------------
resource "aws_dynamodb_table" "files" {
  name         = "${var.project}-${var.env}-files"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "pk"
  range_key    = "sk"

  attribute { name = "pk" type = "S" }
  attribute { name = "sk" type = "S" }

  attribute { name = "type" type = "S" }
  attribute { name = "ts"   type = "N" }

  global_secondary_index {
    name            = "GSI1"
    hash_key        = "type"
    range_key       = "ts"
    projection_type = "ALL"
  }
}

# ---------------- IAM Roles ----------------
data "aws_iam_policy_document" "lambda_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals { type="Service" identifiers=["lambda.amazonaws.com"] }
  }
}
resource "aws_iam_role" "lambda_exec" {
  name               = "${var.project}-${var.env}-lambda-exec"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
}
resource "aws_iam_role_policy_attachment" "lambda_logs" {
  role       = aws_iam_role.lambda_exec.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}
data "aws_iam_policy_document" "writer_inline" {
  statement {
    actions   = ["dynamodb:PutItem"]
    resources = [aws_dynamodb_table.files.arn]
  }
  statement {
    actions   = ["s3:PutObject"]
    resources = ["${aws_s3_bucket.processed.arn}/*"]
  }
}
resource "aws_iam_policy" "writer_policy" {
  name   = "${var.project}-${var.env}-writer-policy"
  policy = data.aws_iam_policy_document.writer_inline.json
}
resource "aws_iam_role_policy_attachment" "writer_attach" {
  role       = aws_iam_role.lambda_exec.name
  policy_arn = aws_iam_policy.writer_policy.arn
}

# Step Functions role
data "aws_iam_policy_document" "sfn_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals { type="Service" identifiers=["states.amazonaws.com"] }
  }
}
resource "aws_iam_role" "sfn_role" {
  name               = "${var.project}-${var.env}-sfn-role"
  assume_role_policy = data.aws_iam_policy_document.sfn_assume.json
}
data "aws_iam_policy_document" "sfn_invoke" {
  statement {
    actions   = ["lambda:InvokeFunction"]
    resources = ["*"]
  }
}
resource "aws_iam_policy" "sfn_invoke_policy" {
  name   = "${var.project}-${var.env}-sfn-invoke"
  policy = data.aws_iam_policy_document.sfn_invoke.json
}
resource "aws_iam_role_policy_attachment" "sfn_invoke_attach" {
  role       = aws_iam_role.sfn_role.name
  policy_arn = aws_iam_policy.sfn_invoke_policy.arn
}

# Events → StepFn role
data "aws_iam_policy_document" "events_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals { type="Service" identifiers=["events.amazonaws.com"] }
  }
}
resource "aws_iam_role" "events_to_sfn" {
  name               = "${var.project}-${var.env}-events-to-sfn"
  assume_role_policy = data.aws_iam_policy_document.events_assume.json
}
data "aws_iam_policy_document" "events_start_exec" {
  statement {
    actions   = ["states:StartExecution"]
    resources = ["*"]
  }
}
resource "aws_iam_policy" "events_start_exec_policy" {
  name   = "${var.project}-${var.env}-events-start-exec"
  policy = data.aws_iam_policy_document.events_start_exec.json
}
resource "aws_iam_role_policy_attachment" "events_attach" {
  role       = aws_iam_role.events_to_sfn.name
  policy_arn = aws_iam_policy.events_start_exec_policy.arn
}

# ---------------- Lambda Writer ----------------
data "archive_file" "writer_zip" {
  type        = "zip"
  source_dir  = "${path.module}/../lambdas/writer"
  output_path = "${path.module}/../lambdas/writer.zip"
}
resource "aws_lambda_function" "writer" {
  function_name    = "${var.project}-${var.env}-writer"
  role             = aws_iam_role.lambda_exec.arn
  handler          = "app.handler"
  runtime          = "python3.11"
  filename         = data.archive_file.writer_zip.output_path
  source_code_hash = data.archive_file.writer_zip.output_base64sha256
  environment {
    variables = {
      TABLE_NAME       = aws_dynamodb_table.files.name
      PROCESSED_BUCKET = aws_s3_bucket.processed.bucket
    }
  }
  timeout = 60
}

# ---------------- Step Functions ----------------
locals {
  sfn_def = jsonencode({
    Comment = "Media Vault MVP",
    StartAt = "Writer",
    States  = {
      Writer = {
        Type     = "Task",
        Resource = aws_lambda_function.writer.arn,
        End      = true
      }
    }
  })
}
resource "aws_sfn_state_machine" "pipeline" {
  name       = "${var.project}-${var.env}-pipeline"
  role_arn   = aws_iam_role.sfn_role.arn
  definition = local.sfn_def
}

# ---------------- EventBridge Rule ----------------
resource "aws_cloudwatch_event_rule" "s3_put" {
  name = "${var.project}-${var.env}-s3put"
  event_pattern = jsonencode({
    "source": ["aws.s3"],
    "detail-type": ["Object Created"],
    "detail": { "bucket": { "name": [aws_s3_bucket.raw.bucket] } }
  })
}
resource "aws_cloudwatch_event_target" "start_sfn" {
  rule     = aws_cloudwatch_event_rule.s3_put.name
  arn      = aws_sfn_state_machine.pipeline.arn
  role_arn = aws_iam_role.events_to_sfn.arn
  input_transformer {
    input_paths = { "bucket" = "$.detail.bucket.name", "key" = "$.detail.object.key" }
    input_template = <<EOF
{"bucket": <bucket>, "key": <key>}
EOF
  }
}
