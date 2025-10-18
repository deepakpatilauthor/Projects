
# AI-Powered Document Summarizer + Chat (AWS, CDK Python)

A serverless,**RAG** (retrieval-augmented generation) skeleton that lets users upload documents, then **chat with them** using **Amazon Bedrock** (Claude/Llama) and a vector store (placeholder). It includes:
- S3 for raw/processed docs
- DynamoDB for documents & chunks metadata
- Step Functions pipeline: **extract → chunk → embed → upsert** (vector store placeholder)
- API Gateway + Lambda for **/chat**
- Cognito for authentication (optional in API for MVP)
- IaC via **AWS CDK (Python)**

> This is an MVP skeleton to deploy quickly and extend. You can wire in OpenSearch Serverless (KNN) or Aurora Postgres + pgvector later.

---

## 🧱 Architecture (MVP)
```
S3 (raw) --(EventBridge)--> Step Functions
   -> Lambda: extract text (Textract for scanned, library for native PDF)
   -> Lambda: chunk text
   -> Lambda: embed (Bedrock Titan Embeddings) [placeholder]
   -> (Upsert vectors to your store) [placeholder]
DynamoDB: documents, chunks
API Gateway --> Lambda: /chat (retrieves relevant chunks [placeholder], calls Bedrock LLM)
S3 (processed): cleaned text, artifacts
```

---

## 🚀 Quickstart (Step-by-step)

### 0) Prerequisites
- Python 3.11 (recommended)
- Node.js 18+ (for CDK CLI)
- AWS CLI configured with credentials+default region
- CDK CLI: `npm i -g aws-cdk`
- Permissions for Amazon Bedrock (enable models in your account/region)

### 1) Set up the project
```bash
# from the repo root
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

### 2) Bootstrap (first time per account/region)
```bash
cdk bootstrap
```

### 3) Deploy
```bash
cdk deploy
```
Copy the printed outputs: **API URL**, **User Pool ID**, **App Client ID**.

### 4) Test the chat endpoint
```bash
# Replace <api-url> with the printed RestApi endpoint, e.g., https://abc123.execute-api.us-east-1.amazonaws.com/prod
curl -X POST "<api-url>/chat"   -H "Content-Type: application/json"   -d '{"docId":"demo-doc","question":"What does Lambda do?"}'
```

You should see a JSON result with an `answer` (the retrieval is mocked for now).

### 5) Ingest a document (MVP flow)
For demo, upload any file to the **raw bucket** (name will be in the CloudFormation outputs or the AWS console). The upload event is wired to **Step Functions**, which will run the 3 Lambdas (extract → chunk → embed). The current code stores and logs metadata; vector indexing is a placeholder.

### 6) Wire in a vector store (next steps)
Pick one:
- **OpenSearch Serverless KNN**: create a collection + index; upsert vectors in the `embed` Lambda; query in `chat` Lambda.
- **Aurora Postgres + pgvector**: create a Serverless cluster + table; upsert/query via psycopg in Lambdas (with RDS Proxy).

---

## 🔧 Configure Bedrock model
The `chat` Lambda reads env `BEDROCK_MODEL` (default: `anthropic.claude-3-sonnet-20240229-v1:0` if available). Ensure the model is enabled in your region. You can change to a different Bedrock model ID in `cdk/stacks/ai_doc_chat_stack.py` or Lambda env.

---

## 📦 Project structure
```
.
├── README.md
├── requirements.txt
├── cdk.json
├── app.py
├── .gitignore
├── cdk/
│   └── stacks/
│       └── ai_doc_chat_stack.py
└── lambda/
    ├── chat/handler.py
    ├── extract/handler.py
    ├── chunk/handler.py
    ├── embed/handler.py   # vector upsert placeholder
    └── summarize/handler.py
```

---

## 🔐 Security notes
- S3 buckets are private; presigned uploads recommended (add a `presign` Lambda if you need).
- Use **SSE-S3 / SSE-KMS** for encryption (can be toggled in the CDK).
- Lambdas follow least-privilege grants to buckets/tables.
- If you add OpenSearch/Aurora, place Lambdas in a VPC and set security groups accordingly.

---

## 🧪 Local development tips
- Use `sam local invoke` or `pytest` for unit tests (you can add later).
- For PDF text, this repo uses a simple PyMuPDF-based extractor for native PDFs; Textract is used if the doc appears scanned (configurable).

---

## 🗺️ Roadmap / TODO
- [ ] Add vector DB (OpenSearch Serverless or Aurora+pgvector) and upsert/query logic
- [ ] Add `/presign-upload` API
- [ ] Add WebSocket streaming for chat
- [ ] Add front-end (S3+CloudFront React app)
- [ ] Add summarization Step Functions mini-flow
- [ ] Add CloudWatch dashboards & alarms

---

## ❓Troubleshooting
- **AccessDenied on Bedrock**: enable the model in your account/region or change `BEDROCK_MODEL` to one available.
- **CDK diff/deploy errors**: try `cdk bootstrap` again or delete stale stacks in the console if a previous deploy failed.
- **Lambda timeouts**: increase timeouts in the CDK file for heavy PDFs.
