import boto3, json, time, os

ddb = boto3.resource("dynamodb").Table(os.environ["TABLE_NAME"])
s3  = boto3.client("s3")
PROCESSED_BUCKET = os.environ["PROCESSED_BUCKET"]

def handler(event, context):
    # Expected event: {"bucket": "...raw-bucket", "key": "path/filename.ext"}
    ts = int(time.time())
    bucket = event["bucket"]
    key    = event["key"]
    item = {
        "pk": f"FILE#{key}",
        "sk": f"META#{ts}",
        "type": "UNKNOWN",
        "ts": ts,
        "bucket": bucket,
        "key": key,
    }
    # Store metadata row
    ddb.put_item(Item=item)
    # Store a JSON copy for analytics
    s3.put_object(
        Bucket=PROCESSED_BUCKET,
        Key=f"mvp/{ts}.json",
        Body=json.dumps(item).encode("utf-8"),
        ContentType="application/json"
    )
    return {"status": "ok", "pk": item["pk"]}
