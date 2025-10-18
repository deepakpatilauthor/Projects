
import json, os, boto3, logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

bedrock_rt = boto3.client("bedrock-runtime")

def build_prompt(question: str, retrieved: list) -> str:
    context_lines = [f"(p.{r.get('page','?')}) {r.get('text','')}" for r in retrieved]
    context_str = "\n".join(context_lines)
    return f"""You are a helpful assistant that ONLY answers from the provided context.
If the answer cannot be found in the context, say you don't know.

Context:
{context_str}

Question: {question}

Answer with short bullet points and include citation brackets like [p.X]."""

def main(event, context):
    try:
        body = json.loads(event.get("body","{}"))
    except Exception:
        body = {}
    question = body.get("question", "What is AWS Lambda?")
    doc_id = body.get("docId", "demo-doc")

    # TODO: Retrieve top-k from vector store; for now, mocked passages
    retrieved = [
        {"text": "AWS Lambda lets you run code without provisioning or managing servers.", "page": 3},
        {"text": "Integrate Lambda with API Gateway to build RESTful APIs.", "page": 5}
    ]

    prompt = build_prompt(question, retrieved)
    model_id = os.environ.get("BEDROCK_MODEL", "anthropic.claude-3-sonnet-20240229-v1:0")

    payload = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 400,
        "temperature": 0.2,
        "messages": [
            {"role":"user","content":[{"type":"text","text": prompt}]}
        ]
    }

    resp = bedrock_rt.invoke_model(
        modelId=model_id,
        body=json.dumps(payload)
    )
    out = json.loads(resp["body"].read())

    # Anthropic format
    answer = ""
    try:
        parts = out.get("content", [])
        answer = "".join([p.get("text","") for p in parts if p.get("type")=="text"])
    except Exception:
        answer = out

    return {
        "statusCode": 200,
        "headers": {"Access-Control-Allow-Origin": "*"},
        "body": json.dumps({
            "docId": doc_id,
            "answer": answer,
            "citations": [{"page": r["page"]} for r in retrieved]
        })
    }
