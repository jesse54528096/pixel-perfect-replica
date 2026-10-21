import json, os
import boto3

_s3 = boto3.client("s3")


def routes():
    # Same list the parser wrapper uses, so a new route needs no change here.
    obj = _s3.get_object(Bucket=os.environ["CONFIG_BUCKET"], Key="flight-routes.json")
    return [f"{r['origin']}-{r['destination']}" for r in json.loads(obj["Body"].read())]


def handler(event, context):
    items = []
    for route in routes():
        try:
            obj = _s3.get_object(Bucket=os.environ["CONFIG_BUCKET"], Key=f"prices/{route}.json")
            items.append(json.loads(obj["Body"].read()))
        except _s3.exceptions.ClientError:  # not written yet (AccessDenied without ListBucket)
            continue
    return {"statusCode": 200, "headers": {"content-type": "application/json"},
            "body": json.dumps({"items": items})}
