## 🚀 Quickstart — Run This Project

### 1) Prerequisites

- An **AWS account** (Free Tier is fine)
- **Permissions**: enough to create S3, Lambda, Step Functions, EventBridge, DynamoDB, IAM
- Installed locally:
  - [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
  - [Terraform ≥ 1.6](https://developer.hashicorp.com/terraform/tutorials/aws-get-started/install-cli)
  - Python 3.11, Git (any recent version)

Configure AWS credentials (once):
```bash
aws configure
# Set your Access Key, Secret, region (e.g. ap-south-1), output json
```

---

### 2) Repo Layout

```
infra/
  main.tf       # Terraform for AWS resources
  dev.tfvars    # Project/env/region/profile settings
lambdas/
  writer/app.py # Lambda code that writes metadata
README.md
```

---

### 3) Set Your Project Names (optional)

Open `infra/dev.tfvars` and adjust if you like:
```hcl
project     = "media-vault"   # becomes part of bucket names
env         = "dev"           # dev/stage/prod
region      = "ap-south-1"    # change if needed
aws_profile = "default"       # your AWS CLI profile name
```

> S3 buckets must be **globally unique**. If apply fails with “Bucket already exists”, change `project` or `env` and re-apply.

---

### 4) Deploy

From the repo root:
```bash
cd infra
terraform init
terraform apply -var-file=dev.tfvars -auto-approve
```

Terraform will create:
- S3 buckets: `${project}-${env}-raw`, `${project}-${env}-processed`, `${project}-${env}-logs`
- DynamoDB table: `${project}-${env}-files`
- Lambda function: `${project}-${env}-writer`
- Step Functions state machine: `${project}-${env}-pipeline`
- EventBridge rule: triggers pipeline on S3 “Object Created”

---

### 5) Test the Pipeline

Define the raw bucket name (optional helper):
```bash
PROJECT=media-vault
ENV=dev
RAW_BUCKET="${PROJECT}-${ENV}-raw"
```

Upload any file:
```bash
echo "hello world" > hello.txt
aws s3 cp hello.txt s3://${RAW_BUCKET}/hello.txt
```

---

### 6) Verify It Worked

**A. Step Functions**
- Console ➜ *AWS Step Functions* ➜ state machine `${PROJECT}-${ENV}-pipeline`
- You should see an **Execution** with status **SUCCEEDED**
- Click it to view **Input** `{ "bucket": "...-raw", "key": "hello.txt" }` and **Output** `{ "status": "ok", ... }`

**B. DynamoDB**
- Console ➜ *DynamoDB* ➜ Tables ➜ `${PROJECT}-${ENV}-files` ➜ **Explore table items**
- You should see an item like:
  - `pk = FILE#hello.txt`
  - `sk = META#<timestamp>`
  - plus `bucket`, `key`, `ts`, `type`

**C. S3 (processed)**
- Console ➜ *S3* ➜ bucket `${PROJECT}-${ENV}-processed` ➜ folder `mvp/`
- A JSON file like `<timestamp>.json` should exist with the same metadata

CLI quick checks:
```bash
aws s3 ls s3://${PROJECT}-${ENV}-processed/mvp/
aws dynamodb scan --table-name ${PROJECT}-${ENV}-files --output table
```

If those three checks pass, the MVP is **working** ✅

---

### 7) Troubleshooting

- **Bucket name in use**: change `project`/`env` in `infra/dev.tfvars`, re-apply.
- **No execution in Step Functions**: confirm raw bucket has **EventBridge enabled** (Terraform sets it), and the EventBridge rule is **Enabled**.
- **AccessDenied in Lambda**: open **CloudWatch Logs** for the writer function, note the missing permission, update IAM in Terraform, `terraform apply`.
- **CLI uses wrong account/region**: set the right profile/region:
  ```bash
  export AWS_PROFILE=default
  export AWS_REGION=ap-south-1
  ```

---

### 8) Cleanup (avoid charges)

```bash
# Empty S3 buckets first if needed
aws s3 rm s3://${PROJECT}-${ENV}-raw --recursive
aws s3 rm s3://${PROJECT}-${ENV}-processed --recursive
aws s3 rm s3://${PROJECT}-${ENV}-logs --recursive

# Destroy infrastructure
cd infra
terraform destroy -var-file=dev.tfvars -auto-approve
```

---

### 9) What’s Next (optional)

- Add **Dispatcher + Rekognition/Textract/Transcribe/Comprehend**
- Add **Glue + Athena + QuickSight** for analytics
- Add **CloudWatch Alarms**, DLQs (SQS), retries, and KMS encryption

---
