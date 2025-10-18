
import json, os, boto3

bedrock_rt = boto3.client("bedrock-runtime")

def main(event, context):
    doc_id = event.get("docId","demo-doc")
    text = event.get("text","Summarize the document in 5 bullet points.")
    model_id = os.environ.get("BEDROCK_MODEL", "anthropic.claude-3-sonnet-20240229-v1:0")
    payload = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 400,
        "temperature": 0.2,
        "messages": [{"role":"user","content":[{"type":"text","text": text}]}]
    }
    resp = bedrock_rt.invoke_model(modelId=model_id, body=json.dumps(payload))
    out = json.loads(resp["body"].read())
    parts = out.get("content", [])
    summary = "".join([p.get("text","") for p in parts if p.get("type")=="text"])
    return {"docId": doc_id, "summary": summary}
