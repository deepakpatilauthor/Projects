
import json, logging, os

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def main(event, context):
    # Input from previous step: extracted text location
    doc_id = event.get("docId","demo-doc")
    # Create fake chunks (in a real impl, load text and split)
    chunks = [
        {"chunkId": "c1", "page": 3, "text": "AWS Lambda lets you run code without managing servers."},
        {"chunkId": "c2", "page": 5, "text": "You can integrate Lambda with API Gateway for REST APIs."}
    ]
    return {
        "docId": doc_id,
        "chunks": chunks
    }
